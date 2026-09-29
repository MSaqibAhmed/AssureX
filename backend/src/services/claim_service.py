import hashlib,json
from datetime import date
from fastapi import HTTPException
from src.repositories.mongo import uid,now,change_claim,audit
from src.engines.rules import Policy,expiry
from src.engines.contradiction import detect
from src.engines.duplicate import detect as duplicate_candidates

async def submit(db,claim,user,expected,key):
    request_hash=hashlib.sha256(json.dumps(expected.model_dump(),sort_keys=True).encode()).hexdigest()
    async def transaction(session):
        previous=await db.idempotency.find_one({'claim_id':claim['_id'],'key':key},session=session)
        if previous:
            if previous['request_hash']!=request_hash: raise HTTPException(409,'Idempotency key used for different input')
            return previous['job_id']
        current=await db.claims.find_one({'_id':claim['_id']},session=session)
        if current['status'] not in ('Draft','Additional Information Required'): raise HTTPException(409,'Claim cannot be submitted in this state')
        product=await db.products.find_one({'_id':current['product_id']},session=session)
        warranty=await db.warranties.find_one({'product_id':product['_id']},session=session)
        if not warranty: raise HTTPException(422,'Warranty required')
        policy_record=await db.policy_versions.find_one({'_id':warranty['policy_version_id']},session=session)
        policy=Policy.model_validate(policy_record['policy'])
        models={}
        for family in ('python','gtm'):
            activation=await db.settings.find_one({'_id':'active_model:'+family},session=session)
            model=await db.model_versions.find_one({'_id':activation['value']['id']},session=session) if activation else None
            if not model: raise HTTPException(503,'Both model versions must be activated before submission')
            models[family]=model
        documents=await db.documents.find({'claim_id':current['_id']},session=session).to_list()
        if await db.jobs.find_one({'claim_id':current['_id'],'document_id':{'$exists':True},'status':{'$ne':'completed'}},session=session):
            raise HTTPException(409,'Wait for document extraction to complete before submission')
        extracted=await db.ocr_fields.find({'document_id':{'$in':[d['_id'] for d in documents]}},session=session).to_list()
        repairs=await db.repairs.find({'product_id':product['_id']},session=session).to_list()
        raw=dict(current['facts']); today=now().date(); purchase=date.fromisoformat(product['purchase_date'])
        fault=date.fromisoformat(raw['fault_date']) if raw.get('fault_date') else None
        serial=raw.get('serial'); registered=product.get('serial_normalized')
        types=[d['type'] for d in documents]
        facts=raw|{'purchase_date':purchase.isoformat(),'submission_date':today.isoformat(),
            'product_category':product['category'],'product_age_days':(today-purchase).days,
            'warranty_remaining_days':(expiry(purchase,policy.coverage_months)-today).days,
            'coverage_months':policy.coverage_months,'reporting_delay_days':(today-fault).days if fault else None,
            'repair_count':len(repairs),'repairs':repairs,'missing_document_count':len(set(policy.required_documents)-set(types)),
            'serial_status':'unknown' if not serial or not registered else 'match' if serial.strip().upper()==registered else 'mismatch',
            'authorization_status':'unauthorized' if any(r['authorized'] is False for r in repairs) else 'unknown' if any(r['authorized'] is None for r in repairs) else 'authorized',
            'receipt_present':'receipt' in types,'warranty_card_present':'warranty' in types,
            'covered_fault':None,'excluded_damage':None if raw.get('damage_type') is None else raw['damage_type'] in policy.excluded_damage,
            'duplicate_signal':False,'document_types':types,'evidence_ids':[d['_id'] for d in documents],
            'ocr_fields':extracted,
            'fault_media':[{'document_id':d['_id'],'type':d['type'],'analysis':d.get('media_analysis',{})} for d in documents if d['type'] in ('fault_image','fault_video')]}
        verified_fields={f['field']:f['normalized_value'] for f in extracted if f.get('normalized_value') is not None
            and (f.get('corrected') or (f.get('confidence') is not None and f['confidence']>=.8))}
        facts['unverified_evidence_fields']=[field for field in ('purchase_date','serial','invoice_number') if field not in verified_fields]
        evidence_contradictions=[]
        for field,expected_value in [('purchase_date',purchase.isoformat()),('serial',registered),('invoice_number',raw.get('invoice_number'))]:
            if field in verified_fields and expected_value and verified_fields[field].strip().upper()!=str(expected_value).strip().upper():
                evidence_contradictions.append(field+'_evidence_mismatch')
        facts['covered_fault']=None if not raw.get('fault_category') else raw['fault_category'] in policy.covered_fault_categories
        facts['contradiction_count']=len(detect(facts))+len(evidence_contradictions)
        facts['evidence_contradictions']=evidence_contradictions
        hashes=[d['sha256'] for d in documents]
        if hashes:
            facts['duplicate_signal']=bool(await db.documents.find_one({'sha256':{'$in':hashes},'claim_id':{'$ne':current['_id']},'product_id':product['_id']},session=session))
        others=await db.claims.find({'product_id':product['_id'],'_id':{'$ne':current['_id']}},session=session).to_list()
        links=duplicate_candidates({'claim_id':current['_id'],'product_id':product['_id'],'fault':raw.get('description',''),'hashes':hashes},
            [{'claim_id':other['_id'],'product_id':other['product_id'],'fault':other.get('facts',{}).get('description',''),'hashes':[]} for other in others])
        for link in links:
            duplicate_key={'claim_id':current['_id'],'other_claim_id':link['other_claim_id'],'kind':link['kind']}
            await db.duplicate_links.update_one(duplicate_key,{'$setOnInsert':dict(duplicate_key,_id=uid(),resolved=False)},upsert=True,session=session)
        unresolved=await db.duplicate_links.find_one({'claim_id':current['_id'],'resolved':False},session=session)
        facts['duplicate_signal']=facts['duplicate_signal'] or bool(unresolved)
        rid,jid=uid(),uid(); revision=current.get('revision_number',0)+1
        await change_claim(db,current,expected.version,expected.status,{'status':'Submitted','current_revision_id':rid,'revision_number':revision},session)
        await db.claim_revisions.insert_one({'_id':rid,'claim_id':current['_id'],'revision_number':revision,'facts_json':facts,
            'report_snapshot':{'product':{k:product.get(k) for k in ('name','brand','model','category','serial','retailer','amount')},
                'warranty':{k:warranty.get(k) for k in ('provider','start_date','expiry_date')},
                'documents':[{k:d.get(k) for k in ('_id','name','type','mime','size','sha256')} for d in documents]},
            'submitted_at':now(),'policy':policy.model_dump(),'policy_version_id':policy_record['_id'],'models':models},session=session)
        await db.jobs.insert_one({'_id':jid,'claim_id':current['_id'],'revision_id':rid,'status':'queued','stage':'queued'},session=session)
        await db.outbox.insert_one({'_id':jid,'kind':'evaluation','target_id':rid,'status':'pending','created_at':now()},session=session)
        await db.idempotency.insert_one({'_id':uid(),'claim_id':current['_id'],'key':key,'request_hash':request_hash,'job_id':jid},session=session)
        await audit(db,user['_id'],'claim_submitted',current['_id'],current['status'],'Submitted',session)
        return jid
    async with db.client.start_session() as session:
        return await session.with_transaction(transaction)
