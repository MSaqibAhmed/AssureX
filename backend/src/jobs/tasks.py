import asyncio,hashlib,json,logging
from datetime import timedelta,date
from pathlib import Path
from pymongo import AsyncMongoClient
from pymongo.errors import DuplicateKeyError
from src.config import Settings
from src.repositories.mongo import uid,now,change_claim,audit
from src.engines.ocr import extract
from src.engines.rules import Policy,run_rules
from src.engines.comparison import compare
from src.engines.decision import decide
from src.schemas.evaluation import EvaluationRun,Predictions

def perform(job_id):
    asyncio.run(run(job_id))

async def run(job_id):
    settings=Settings()
    async with AsyncMongoClient(settings.mongo_uri,tz_aware=True) as client:
        db=client[settings.mongo_database]; job=await db.jobs.find_one({'_id':job_id})
        if not job or job['status']=='completed': return
        await db.jobs.update_one({'_id':job_id},{'$set':{'status':'running','stage':'loading','started_at':now()}})
        try:
            if job.get('kind')=='summary': await summary_job(db,job,settings)
            elif job.get('document_id'): await ocr_job(db,job,settings)
            else: await evaluate(db,job,settings)
        except Exception:
            await db.jobs.update_one({'_id':job_id,'status':{'$ne':'completed'}},{'$set':{'status':'failed','stage':'failed','error':'Processing failed; retry is safe'}})
            raise

async def ocr_job(db,job,settings):
    document=await db.documents.find_one({'_id':job['document_id']})
    if document['type'] in ('fault_image','fault_video'):
        from src.engines.fault_media import media_review
        async def media_transaction(session):
            await db.documents.update_one({'_id':document['_id']},{'$set':{'media_analysis':media_review(document['type'])}},session=session)
            await db.jobs.update_one({'_id':job['_id']},{'$set':{'status':'completed','stage':'completed'}},session=session)
        async with db.client.start_session() as session: await session.with_transaction(media_transaction)
        return
    path=settings.evidence_root/document['object_key']
    fields=await asyncio.to_thread(extract,path.read_bytes(),document['mime'],settings.max_pdf_pages)
    async def transaction(session):
        current=await db.jobs.find_one({'_id':job['_id']},session=session)
        if current['status']=='completed': return
        await db.ocr_runs.insert_one({'_id':uid(),'document_id':document['_id'],'engine_version':'tesseract-pypdf-v2-layout','status':'completed'},session=session)
        await db.ocr_fields.insert_many([{'_id':uid(),'document_id':document['_id'],**field} for field in fields],session=session)
        await db.jobs.update_one({'_id':job['_id']},{'$set':{'status':'completed','stage':'completed'}},session=session)
    async with db.client.start_session() as session: await session.with_transaction(transaction)

async def evaluate(db,job,settings):
    from src.ml.inference_process import infer
    revision=await db.claim_revisions.find_one({'_id':job['revision_id']})
    facts=revision['facts_json']; models=revision['models']; policy=Policy.model_validate(revision['policy'])
    versions={family:model['_id'] for family,model in models.items()}|{'policy':revision['policy_version_id']}
    raw=json.dumps(facts,sort_keys=True,default=str).encode(); input_hash=hashlib.sha256(raw).hexdigest()
    unique_hash=hashlib.sha256((revision['_id']+input_hash+json.dumps(versions,sort_keys=True)).encode()).hexdigest()
    claim=await db.claims.find_one({'_id':job['claim_id']})
    if claim['status']=='Submitted':
        await change_claim(db,claim,claim['version'],'Submitted',{'status':'Under Evaluation'})
    await db.jobs.update_one({'_id':job['_id']},{'$set':{'stage':'models'}})
    predictions={}; errors={}
    async def run_model(family):
        try:
            model_record=models[family]; root=settings.artifact_root.resolve(); path=(root/model_record['artifact_path']).resolve()
            if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest()!=model_record['sha256']:
                raise ValueError('Artifact integrity error')
            predictions[family]=await asyncio.to_thread(infer,family,path,facts,30)
        except Exception as exc:
            code=str(exc) if str(exc) in ('model_timeout','model_startup_timeout','model_load_failed','model_process_failed') else 'model_unavailable_or_invalid_output'
            logging.getLogger(__name__).error('Inference failed: family=%s code=%s exception=%s',family,code,type(exc).__name__)
            predictions[family]=None; errors[family]=code
    await asyncio.gather(run_model('python'),run_model('gtm'))
    rules=run_rules(facts,policy)
    decision=decide(predictions['python'],predictions['gtm'],rules,
        mandatory_facts_verified=not any(r.status in ('UNKNOWN','FAIL','MANUAL_REVIEW') for r in rules),
        critical_evidence_missing=bool(facts['missing_document_count']),
        unresolved_contradiction=bool(facts['contradiction_count']),unresolved_duplicate=bool(facts['duplicate_signal']))
    eid=uid()
    evaluation=EvaluationRun(id=eid,claim_revision_id=revision['_id'],input_hash=input_hash,
        evaluation_input_version_hash=unique_hash,status='completed',versions=versions,
        predictions=Predictions(**predictions),comparison=compare(predictions['python'],predictions['gtm']),
        rule_results=rules,recommendation=decision.recommendation,reasons=decision.reasons,
        decision_branch=decision.branch,completed_at=now(),model_errors=errors).model_dump(mode='python')
    evaluation['_id']=evaluation.pop('id')
    async def transaction(session):
        existing=await db.evaluation_runs.find_one({'evaluation_input_version_hash':unique_hash},session=session)
        if existing:
            await db.jobs.update_one({'_id':job['_id']},{'$set':{'status':'completed','stage':'completed','evaluation_id':existing['_id']}},session=session)
            return
        current=await db.claims.find_one({'_id':claim['_id']},session=session)
        if current['current_revision_id']!=revision['_id'] or current['status']!='Under Evaluation':
            raise ValueError('Revision is no longer current')
        await db.evaluation_runs.insert_one(evaluation,session=session)
        await change_claim(db,current,current['version'],current['status'],{'status':'Manual Review','latest_evaluation_id':eid},session)
        await audit(db,'worker','evaluation_completed',claim['_id'],session=session)
        await db.notifications.insert_one({'_id':uid(),'recipient':claim['claimant_id'],'event_type':'evaluation_completed',
            'target_revision':revision['_id'],'reminder_window':0,'read':False,'claim_id':claim['_id']},session=session)
        await db.jobs.update_one({'_id':job['_id']},{'$set':{'status':'completed','stage':'completed','evaluation_id':eid}},session=session)
        summary_id='summary-'+revision['_id']
        await db.jobs.insert_one({'_id':summary_id,'claim_id':claim['_id'],'revision_id':revision['_id'],
            'kind':'summary','status':'queued','stage':'queued'},session=session)
        await db.outbox.insert_one({'_id':summary_id,'kind':'summary','target_id':revision['_id'],
            'status':'pending','created_at':now()},session=session)
    async with db.client.start_session() as session: await session.with_transaction(transaction)

async def summary_job(db,job,settings):
    from src.ml.summary_model.summarize import bounded_summary
    revision=await db.claim_revisions.find_one({'_id':job['revision_id']})
    summary=await asyncio.to_thread(bounded_summary,revision['facts_json'],settings.summary_model,30)
    async def transaction(session):
        await db.claim_summaries.update_one({'claim_revision_id':revision['_id']},{'$setOnInsert':{'_id':uid(),'claim_revision_id':revision['_id'],**summary}},upsert=True,session=session)
        await db.jobs.update_one({'_id':job['_id']},{'$set':{'status':'completed','stage':'completed'}},session=session)
    async with db.client.start_session() as session: await session.with_transaction(transaction)

def expiry_scan(): asyncio.run(scan())

async def scan():
    settings=Settings()
    async with AsyncMongoClient(settings.mongo_uri,tz_aware=True) as client:
        await scan_warranties(client[settings.mongo_database],date.today())

async def scan_warranties(db,today):
    async for warranty in db.warranties.find({'start_date':{'$lte':today.isoformat()},'expiry_date':{'$gte':today.isoformat()}}):
        policy=await db.policy_versions.find_one({'_id':warranty['policy_version_id']})
        if not policy: continue
        window=policy['policy']['reminder_window']
        if date.fromisoformat(warranty['expiry_date'])>today+timedelta(days=window): continue
        product=await db.products.find_one({'_id':warranty['product_id']})
        if not product: continue
        key={'recipient':product['owner_id'],'event_type':'warranty_near_expiry','target_revision':warranty['_id'],'reminder_window':window}
        await db.notifications.update_one(key,{'$setOnInsert':dict(key,_id=uid(),read=False)},upsert=True)
