from datetime import datetime,timezone
from uuid import uuid4
from bson import Decimal128
from fastapi import HTTPException

def now(): return datetime.now(timezone.utc)
def uid(): return str(uuid4())

def public(value):
    if isinstance(value,dict): return {('id' if k=='_id' else k):public(v) for k,v in value.items() if k not in ('password_hash','object_key','csrf')}
    if isinstance(value,list): return [public(v) for v in value]
    if isinstance(value,Decimal128): return str(value.to_decimal())
    if isinstance(value,datetime): return value.isoformat()
    return value

async def claim_for(db,id,user):
    scope={'_id':id}
    if user['role']=='customer': scope['claimant_id']=user['_id']
    elif user['role']=='reviewer': scope['assigned_reviewer_id']=user['_id']
    elif user['role']=='service': scope['center_id']=user.get('center_id') or '__unassigned__'
    claim=await db.claims.find_one(scope)
    if not claim: raise HTTPException(404,'Claim not found')
    return claim

async def product_for(db,id,user):
    product=await db.products.find_one({'_id':id})
    if not product: raise HTTPException(404,'Product not found')
    if user['role']=='admin' or (user['role']=='customer' and product['owner_id']==user['_id']): return product
    if user['role'] in ('reviewer','service'):
        scope={'product_id':id}
        scope.update({'assigned_reviewer_id':user['_id']} if user['role']=='reviewer' else {'center_id':user.get('center_id') or '__unassigned__'})
        if await db.claims.find_one(scope): return product
    raise HTTPException(404,'Product not found')

async def change_claim(db,claim,version,status,updates,session=None):
    result=await db.claims.update_one({'_id':claim['_id'],'version':version,'status':status},
        {'$set':updates,'$inc':{'version':1}},session=session)
    if result.modified_count!=1: raise HTTPException(409,'Claim changed; reload before retrying')

async def audit(db,actor,action,target,before=None,after=None,session=None):
    await db.audit_events.insert_one({'_id':uid(),'actor_id':actor,'action':action,'target_id':target,
        'before':before,'after':after,'timestamp':now()},session=session)
