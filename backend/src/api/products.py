from datetime import date
from bson import Decimal128
from fastapi import APIRouter,Depends,HTTPException,Request,Query
from src.schemas.requests import Product,Warranty,Repair,Replacement
from src.security.auth import current_user,role
from src.repositories.mongo import uid,product_for,claim_for,audit
from src.api.common import envelope
from src.engines.rules import warranty_status

router=APIRouter(tags=['products'])

@router.get('/products')
async def products(request:Request,page:int=Query(1,ge=1),limit:int=Query(20,ge=1,le=100),user=Depends(current_user)):
    role(user,'customer','admin','service')
    query={} if user['role']=='admin' else {'owner_id':user['_id']}
    if user['role']=='service':
        claims=await request.app.state.db.claims.find({'center_id':user.get('center_id') or '__unassigned__'},{'product_id':1}).to_list()
        query={'_id':{'$in':[c['product_id'] for c in claims]}}
    rows=await request.app.state.db.products.find(query).sort('_id',1).skip((page-1)*limit).limit(limit).to_list()
    return envelope(request,{'items':rows,'page':page,'limit':limit,'total':await request.app.state.db.products.count_documents(query)})

@router.post('/products',status_code=201)
async def create(body:Product,request:Request,user=Depends(current_user)):
    role(user,'customer','admin')
    if body.purchase_date>date.today(): raise HTTPException(422,'Purchase date cannot be in the future')
    record=body.model_dump(mode='json'); record.update(_id=uid(),owner_id=user['_id'],serial_normalized=body.serial.strip().upper(),amount=Decimal128(body.amount))
    await request.app.state.db.products.insert_one(record)
    return envelope(request,record)

@router.get('/products/{id}')
async def get(id:str,request:Request,user=Depends(current_user)):
    return envelope(request,await product_for(request.app.state.db,id,user))

@router.patch('/products/{id}')
async def update(id:str,body:Product,request:Request,user=Depends(current_user)):
    role(user,'customer','admin'); db=request.app.state.db; await product_for(db,id,user)
    if body.purchase_date>date.today(): raise HTTPException(422,'Purchase date cannot be in the future')
    values=body.model_dump(mode='json'); values.update(serial_normalized=body.serial.strip().upper(),amount=Decimal128(body.amount))
    query={'_id':id} if user['role']=='admin' else {'_id':id,'owner_id':user['_id']}
    await db.products.update_one(query,{'$set':values})
    return envelope(request,await product_for(db,id,user))

@router.get('/products/{id}/warranty')
async def get_warranty(id:str,request:Request,user=Depends(current_user)):
    db=request.app.state.db; await product_for(db,id,user)
    record=await db.warranties.find_one({'product_id':id})
    if not record: raise HTTPException(404,'Warranty not found')
    policy=await db.policy_versions.find_one({'_id':record['policy_version_id']})
    record['status']=warranty_status(date.fromisoformat(record['expiry_date']),date.today(),policy['policy']['reminder_window'])
    return envelope(request,record)

@router.patch('/products/{id}/warranty')
async def warranty(id:str,body:Warranty,request:Request,user=Depends(current_user)):
    role(user,'customer'); db=request.app.state.db; product=await product_for(db,id,user)
    if body.expiry_date<body.start_date: raise HTTPException(422,'Invalid coverage dates')
    if not await db.policy_versions.find_one({'_id':body.policy_version_id,'category':product['category']}):
        raise HTTPException(422,'Unknown policy version for this product category')
    values=body.model_dump(mode='json')|{'product_id':id}
    await db.warranties.update_one({'product_id':id},{'$set':values,'$setOnInsert':{'_id':uid()}},upsert=True)
    return await get_warranty(id,request,user)

async def service_record(kind,id,body,request,user):
    role(user,'service'); db=request.app.state.db; claim=await claim_for(db,body.claim_id,user)
    if claim['product_id']!=id: raise HTTPException(404,'Product not found')
    record=body.model_dump(mode='json')|{'_id':uid(),'product_id':id,'center_id':user.get('center_id')}
    await db[kind].insert_one(record); await audit(db,user['_id'],kind,id)
    return envelope(request,record)

@router.post('/products/{id}/repairs',status_code=201)
async def repair(id:str,body:Repair,request:Request,user=Depends(current_user)):
    return await service_record('repairs',id,body,request,user)

@router.post('/products/{id}/replacements',status_code=201)
async def replacement(id:str,body:Replacement,request:Request,user=Depends(current_user)):
    if body.old_serial.strip().upper()==body.new_serial.strip().upper(): raise HTTPException(422,'Replacement serial must differ')
    return await service_record('replacements',id,body,request,user)
