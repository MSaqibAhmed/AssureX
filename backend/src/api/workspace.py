"""Workflow discovery and scoped workspace records; no model/decision calculations."""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pymongo.errors import DuplicateKeyError
from src.api.common import envelope
from src.api.dashboard import scope
from src.repositories.mongo import claim_for, product_for, uid, audit, change_claim
from src.security.auth import current_user, role, hasher
from src.schemas.requests import ProfileUpdate, UserCreate, UserAccess, Assignment

router = APIRouter(tags=['workspace'])

@router.get('/policies')
async def policies(request:Request,category:str|None=None,page:int=Query(1,ge=1),limit:int=Query(20,ge=1,le=100),user=Depends(current_user)):
    db=request.app.state.db
    query={'category':category} if category else {}
    return envelope(request,{'items':await db.policy_versions.find(query).sort('created_at',-1).skip((page-1)*limit).limit(limit).to_list(),
        'total':await db.policy_versions.count_documents(query),'page':page,'limit':limit})

@router.get('/policies/{id}')
async def policy(id:str,request:Request,user=Depends(current_user)):
    record=await request.app.state.db.policy_versions.find_one({'_id':id})
    if not record: raise HTTPException(404,'Policy not found')
    return envelope(request,record)

@router.patch('/me')
async def profile(body:ProfileUpdate,request:Request,user=Depends(current_user)):
    db=request.app.state.db
    await db.users.update_one({'_id':user['_id']},{'$set':body.model_dump()})
    await audit(db,user['_id'],'profile_updated',user['_id'])
    return envelope(request,await db.users.find_one({'_id':user['_id']}))

@router.get('/documents')
async def documents(request:Request,product_id:str|None=None,page:int=Query(1,ge=1),limit:int=Query(20,ge=1,le=100),user=Depends(current_user)):
    db=request.app.state.db
    claims=await db.claims.find(scope(user),{'_id':1}).to_list()
    query={'claim_id':{'$in':[c['_id'] for c in claims]}}
    if product_id:
        await product_for(db,product_id,user)
        query['product_id']=product_id
    return envelope(request,{'items':await db.documents.find(query).sort('_id',-1).skip((page-1)*limit).limit(limit).to_list(),
        'total':await db.documents.count_documents(query),'page':page,'limit':limit})

@router.get('/products/{id}/service-history')
async def product_history(id:str,request:Request,user=Depends(current_user)):
    db=request.app.state.db
    await product_for(db,id,user)
    query={'product_id':id}
    if user['role']=='service': query['center_id']=user.get('center_id') or '__unassigned__'
    repairs=await db.repairs.find(query).to_list()
    replacements=await db.replacements.find(query).to_list()
    return envelope(request,sorted([dict(r,kind='repair') for r in repairs]+[dict(r,kind='replacement') for r in replacements],key=lambda r:r['date'],reverse=True))

@router.get('/service-history')
async def service_history(request:Request,page:int=Query(1,ge=1),limit:int=Query(20,ge=1,le=100),user=Depends(current_user)):
    role(user,'service','admin'); db=request.app.state.db
    query={} if user['role']=='admin' else {'center_id':user.get('center_id') or '__unassigned__'}
    # Fetch a bounded prefix from each source to form a correctly ordered combined page.
    rows=[]
    for collection,kind in [('repairs','repair'),('replacements','replacement')]:
        rows += [dict(r,kind=kind) for r in await db[collection].find(query).sort([('date',-1),('_id',-1)]).limit(page*limit).to_list()]
    rows.sort(key=lambda r:(r['date'],r['_id']),reverse=True)
    total=await db.repairs.count_documents(query)+await db.replacements.count_documents(query)
    return envelope(request,{'items':rows[(page-1)*limit:page*limit],'total':total,'page':page,'limit':limit})

@router.get('/claims/{id}/workflow')
async def workflow(id:str,request:Request,user=Depends(current_user)):
    db=request.app.state.db; claim=await claim_for(db,id,user)
    job=await db.jobs.find_one({'claim_id':id,'revision_id':claim.get('current_revision_id'),'kind':{'$ne':'summary'}}) if claim.get('current_revision_id') else None
    reviews=await db.reviews.find({'claim_id':id}).sort('timestamp',1).to_list()
    events=await db.audit_events.find({'target_id':id,'action':{'$in':['claim_submitted','evaluation_completed','review_approve','review_reject','review_request_info','reviewer_assigned']}}).sort('timestamp',1).to_list()
    return envelope(request,{'evaluation_job':job,'reviews':reviews,'timeline':events,
        'product':await product_for(db,claim['product_id'],user),
        'warranty':await db.warranties.find_one({'product_id':claim['product_id']})})

@router.get('/admin/models')
async def models(request:Request,user=Depends(current_user)):
    role(user,'admin'); db=request.app.state.db
    active=await db.settings.find({'_id':{'$in':['active_model:python','active_model:gtm']}}).to_list()
    return envelope(request,{'items':await db.model_versions.find({}, {'artifact_path':0}).limit(100).to_list(),
        'active_ids':[r['value']['id'] for r in active]})

@router.get('/admin/users')
async def users(request:Request,page:int=Query(1,ge=1),limit:int=Query(20,ge=1,le=100),user=Depends(current_user)):
    role(user,'admin'); db=request.app.state.db
    return envelope(request,{'items':await db.users.find({}, {'password_hash':0}).sort('name',1).skip((page-1)*limit).limit(limit).to_list(),
        'total':await db.users.count_documents({}),'page':page,'limit':limit})

@router.post('/admin/users',status_code=201)
async def create_user(body:UserCreate,request:Request,user=Depends(current_user)):
    role(user,'admin'); db=request.app.state.db
    if body.role=='service' and not await db.service_centers.find_one({'_id':body.center_id,'active':True}):
        raise HTTPException(422,'Select an active service center')
    record={'_id':uid(),'name':body.name,'email_normalized':str(body.email).casefold(),'role':body.role,
        'center_id':body.center_id if body.role=='service' else None,'active':True,'password_hash':hasher.hash(body.password)}
    try: await db.users.insert_one(record)
    except DuplicateKeyError: raise HTTPException(409,'Account already exists')
    await audit(db,user['_id'],'user_created',record['_id'])
    return envelope(request,record)

@router.patch('/admin/users/{id}')
async def user_access(id:str,body:UserAccess,request:Request,user=Depends(current_user)):
    role(user,'admin'); db=request.app.state.db
    target=await db.users.find_one({'_id':id})
    if not target: raise HTTPException(404,'User not found')
    if target['role']=='admin': raise HTTPException(409,'Administrator access changes require an operator')
    await db.users.update_one({'_id':id},{'$set':{'active':body.active}})
    if not body.active: await db.sessions.delete_many({'user_id':id})
    await audit(db,user['_id'],'user_access_changed',id,after=str(body.active))
    return envelope(request,await db.users.find_one({'_id':id}))

@router.get('/admin/service-centers')
async def centers(request:Request,user=Depends(current_user)):
    role(user,'admin')
    return envelope(request,await request.app.state.db.service_centers.find({'active':True}).limit(100).to_list())

@router.get('/admin/audit')
async def events(request:Request,page:int=Query(1,ge=1),limit:int=Query(20,ge=1,le=100),user=Depends(current_user)):
    role(user,'admin'); db=request.app.state.db
    return envelope(request,{'items':await db.audit_events.find().sort('timestamp',-1).skip((page-1)*limit).limit(limit).to_list(),
        'total':await db.audit_events.count_documents({}),'page':page,'limit':limit})

@router.patch('/claims/{id}/assignment')
async def assign(id:str,body:Assignment,request:Request,user=Depends(current_user)):
    role(user,'admin'); db=request.app.state.db; claim=await claim_for(db,id,user)
    if claim['status'] in ('Approved','Rejected','Closed'): raise HTTPException(409,'A decided claim cannot be reassigned')
    if not await db.users.find_one({'_id':body.reviewer_id,'role':'reviewer','active':True}): raise HTTPException(422,'Reviewer must be active')
    await change_claim(db,claim,body.version,body.status,{'assigned_reviewer_id':body.reviewer_id})
    await audit(db,user['_id'],'reviewer_assigned',id,claim.get('assigned_reviewer_id'),body.reviewer_id)
    return envelope(request,await claim_for(db,id,user))
