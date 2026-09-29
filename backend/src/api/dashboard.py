from fastapi import APIRouter,Depends,HTTPException,Request,Query
from src.security.auth import current_user
from src.schemas.requests import ReadNotice
from src.api.common import envelope
from datetime import date
import re

router=APIRouter(tags=['analytics'])

def scope(user):
    return {'customer':{'claimant_id':user['_id']},'reviewer':{'assigned_reviewer_id':user['_id']},
        'service':{'center_id':user.get('center_id') or '__unassigned__'},'admin':{}}[user['role']]

@router.get('/dashboard')
async def dashboard(request:Request,user=Depends(current_user)):
    db=request.app.state.db
    counts=await db.claims.aggregate([{'$match':scope(user)},{'$group':{'_id':'$status','count':{'$sum':1}}}])
    claims=await db.claims.find(scope(user),{'_id':1,'product_id':1}).to_list()
    product_scope={} if user['role']=='admin' else {'owner_id':user['_id']} if user['role']=='customer' else {'_id':{'$in':[c['product_id'] for c in claims]}}
    products=await db.products.find(product_scope,{'_id':1}).to_list()
    warranties=await db.warranties.find({'product_id':{'$in':[p['_id'] for p in products]}}).to_list()
    today=date.today(); active=0; expiring=0
    for warranty in warranties:
        remaining=(date.fromisoformat(warranty['expiry_date'])-today).days
        if date.fromisoformat(warranty['start_date'])<=today and remaining>=0:
            active+=1
            policy=await db.policy_versions.find_one({'_id':warranty['policy_version_id']})
            if remaining<=(policy or {}).get('policy',{}).get('reminder_window',30): expiring+=1
    return envelope(request,{'claim_counts':{r['_id']:r['count'] async for r in counts},'registered_products':len(products),'active_warranties':active,'expiring_warranties':expiring,
        'saved_documents':await db.documents.count_documents({'claim_id':{'$in':[c['_id'] for c in claims]}})})

@router.get('/reports')
async def reports(request:Request,status:str|None=None,q:str=Query('',max_length=100),sort:str=Query('newest',pattern='^(newest|oldest)$'),page:int=Query(1,ge=1),limit:int=Query(20,ge=1,le=100),user=Depends(current_user)):
    query=scope(user)
    if status: query['status']=status
    db=request.app.state.db
    if q.strip():
        pattern={'$regex':re.escape(q.strip()),'$options':'i'}
        query['$or']=[{key:pattern} for key in ('public_claim_id','product_id','facts.serial','facts.description')]
    rows=await db.claims.find(query).sort([('created_at',-1 if sort=='newest' else 1),('_id',1)]).skip((page-1)*limit).limit(limit).to_list()
    return envelope(request,{'items':rows,'total':await db.claims.count_documents(query),'page':page,'limit':limit})

@router.get('/notifications')
async def notifications(request:Request,page:int=Query(1,ge=1),limit:int=Query(20,ge=1,le=100),user=Depends(current_user)):
    db=request.app.state.db; query={'recipient':user['_id']}
    return envelope(request,{'items':await db.notifications.find(query).sort('_id',-1).skip((page-1)*limit).limit(limit).to_list(),
        'total':await db.notifications.count_documents(query),'unread_count':await db.notifications.count_documents(dict(query,read=False)),'page':page,'limit':limit})

@router.patch('/notifications/{id}')
async def mark(id:str,body:ReadNotice,request:Request,user=Depends(current_user)):
    result=await request.app.state.db.notifications.update_one({'_id':id,'recipient':user['_id']},{'$set':{'read':body.read}})
    if not result.matched_count: raise HTTPException(404,'Notification not found')
    return envelope(request,{'id':id,'read':body.read})
