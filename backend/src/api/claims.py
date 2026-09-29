from fastapi import APIRouter,Depends,HTTPException,Request,Header
from src.schemas.requests import ClaimCreate,ClaimPatch,Expected,Comment
from src.repositories.mongo import claim_for,product_for,uid,now,change_claim
from src.security.auth import current_user,role
from src.api.common import envelope
from src.services.claim_service import submit as submit_claim
from src.services.lifecycle import require_transition
from src.services.routing import assignments

router=APIRouter(tags=['claims'])

@router.post('/claims',status_code=201)
async def create(body:ClaimCreate,request:Request,user=Depends(current_user)):
    role(user,'customer','service'); db=request.app.state.db; product=await product_for(db,body.product_id,user)
    routing=await assignments(db,product['category'])
    if user['role']=='service': routing['center_id']=user.get('center_id') or '__unassigned__'
    record={'_id':uid(),'public_claim_id':'AX-'+uid()[:12],'claimant_id':product['owner_id'],'product_id':body.product_id,
        'status':'Draft','version':1,'facts':body.facts.model_dump(mode='json'),'current_revision_id':None,
        'latest_evaluation_id':None,**routing,'created_at':now()}
    await db.claims.insert_one(record); return envelope(request,record,record['version'])

@router.get('/claims/{id}')
async def get(id:str,request:Request,user=Depends(current_user)):
    record=await claim_for(request.app.state.db,id,user); return envelope(request,record,record['version'])

@router.patch('/claims/{id}')
async def update(id:str,body:ClaimPatch,request:Request,user=Depends(current_user)):
    db=request.app.state.db; claim=await claim_for(db,id,user)
    if body.target_status:
        role(user,'reviewer','admin')
        if body.facts is not None: raise HTTPException(422,'Closing a claim cannot change facts')
        require_transition(claim['status'],body.target_status)
        await change_claim(db,claim,body.version,body.status,{'status':body.target_status})
        return await get(id,request,user)
    role(user,'customer','service')
    if body.facts is None: raise HTTPException(422,'Facts are required')
    if claim['status'] not in ('Draft','Additional Information Required'): raise HTTPException(409,'Request information before correcting a submitted claim')
    await change_claim(db,claim,body.version,body.status,{'facts':body.facts.model_dump(mode='json')})
    return await get(id,request,user)

@router.post('/claims/{id}/submit',status_code=202)
async def submit(id:str,body:Expected,request:Request,idempotency_key:str=Header(min_length=8,max_length=128),user=Depends(current_user)):
    role(user,'customer','service'); db=request.app.state.db; claim=await claim_for(db,id,user)
    jid=await submit_claim(db,claim,user,body,idempotency_key)
    return envelope(request,{'job_id':jid})

@router.get('/jobs/{id}')
async def job(id:str,request:Request,user=Depends(current_user)):
    db=request.app.state.db; record=await db.jobs.find_one({'_id':id})
    if not record: raise HTTPException(404,'Job not found')
    await claim_for(db,record['claim_id'],user); return envelope(request,record)

@router.get('/claims/{id}/evaluations')
async def evaluations(id:str,request:Request,user=Depends(current_user)):
    db=request.app.state.db; await claim_for(db,id,user)
    revisions=await db.claim_revisions.find({'claim_id':id},{'_id':1}).to_list()
    return envelope(request,await db.evaluation_runs.find({'claim_revision_id':{'$in':[r['_id'] for r in revisions]}}).to_list())

@router.get('/claims/{id}/assistance')
async def assistance(id:str,request:Request,user=Depends(current_user)):
    db=request.app.state.db; claim=await claim_for(db,id,user)
    missing=[k for k in ('fault_date','fault_category','serial') if not claim['facts'].get(k)]
    docs=await db.documents.find({'claim_id':id}).to_list()
    warranty=await db.warranties.find_one({'product_id':claim['product_id']})
    policy=await db.policy_versions.find_one({'_id':warranty['policy_version_id']}) if warranty else None
    required=policy['policy']['required_documents'] if policy else []
    pending=await db.jobs.count_documents({'claim_id':id,'document_id':{'$exists':True},'status':{'$ne':'completed'}})
    fields=await db.ocr_fields.find({'document_id':{'$in':[d['_id'] for d in docs]}}).to_list()
    verified={f['field'] for f in fields if f.get('normalized_value') is not None and (f.get('corrected') or (f.get('confidence') is not None and f['confidence']>=.8))}
    unverified=[key for key in ('purchase_date','serial','invoice_number') if key not in verified]
    deadline=None
    if policy and claim['facts'].get('fault_date'):
        from datetime import date,timedelta
        deadline=(date.fromisoformat(claim['facts']['fault_date'])+timedelta(days=policy['policy']['reporting_days'])).isoformat()
    return envelope(request,{'missing_fields':missing,'missing_documents':sorted(set(required)-{d['type'] for d in docs}),
        'warranty_registered':bool(policy),'pending_document_jobs':pending,'unverified_evidence_fields':unverified,
        'deadline':deadline,'corrective_actions':(['Register the existing warranty coverage'] if not policy else [])+['Provide '+k.replace('_',' ') for k in missing]+(['Some document details could not be verified automatically. You may correct them or submit for human review.'] if unverified else []),
        'requested_information':claim.get('requested_information')})

@router.get('/claims/{id}/summary')
async def summary(id:str,request:Request,user=Depends(current_user)):
    role(user,'reviewer','service','admin'); db=request.app.state.db; claim=await claim_for(db,id,user)
    value=await db.claim_summaries.find_one({'claim_revision_id':claim['current_revision_id']})
    if not value: raise HTTPException(404,'Summary not available')
    return envelope(request,value)

@router.post('/claims/{id}/comments',status_code=201)
async def comment(id:str,body:Comment,request:Request,user=Depends(current_user)):
    db=request.app.state.db; await claim_for(db,id,user)
    if user['role']=='customer' and body.visibility=='staff': raise HTTPException(403,'Staff-only comment is forbidden')
    record={'_id':uid(),'claim_id':id,'author_id':user['_id'],'timestamp':now(),**body.model_dump()}
    await db.comments.insert_one(record); return envelope(request,record)

@router.get('/claims/{id}/comments')
async def comments(id:str,request:Request,user=Depends(current_user)):
    db=request.app.state.db; await claim_for(db,id,user); query={'claim_id':id}
    if user['role']=='customer': query['visibility']='customer'
    return envelope(request,await db.comments.find(query).sort('timestamp',1).to_list())
