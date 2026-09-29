from pathlib import Path
import hashlib
from fastapi import APIRouter,Depends,HTTPException,Request
from pymongo.errors import DuplicateKeyError
from src.security.auth import current_user,role
from src.repositories.mongo import uid,now,audit
from src.engines.rules import Policy
from src.schemas.requests import Activation
from src.api.common import envelope

router=APIRouter(tags=['admin'])

@router.post('/admin/policies',status_code=201)
async def policy(body:Policy,request:Request,user=Depends(current_user)):
    role(user,'admin'); db=request.app.state.db
    record={'_id':uid(),'category':body.category,'version':body.version,'policy':body.model_dump(),'created_at':now()}
    try: await db.policy_versions.insert_one(record)
    except DuplicateKeyError: raise HTTPException(409,'Policy version already exists')
    await audit(db,user['_id'],'policy_created',record['_id'])
    return envelope(request,record)

@router.post('/admin/model-activations')
async def activate(body:Activation,request:Request,user=Depends(current_user)):
    role(user,'admin'); db=request.app.state.db; model=await db.model_versions.find_one({'_id':body.model_version_id})
    if not model: raise HTTPException(404,'Model version not found')
    root=request.app.state.settings.artifact_root.resolve(); path=(root/model['artifact_path']).resolve()
    if not path.is_relative_to(root) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=model['sha256']:
        raise HTTPException(422,'Model artifact is missing or fails checksum validation')
    async def transaction(session):
        await db.settings.update_one({'_id':'active_model:'+model['family']},{'$set':{'value':{'id':model['_id']}}},upsert=True,session=session)
        await audit(db,user['_id'],'model_activated',model['_id'],session=session)
    async with db.client.start_session() as session: await session.with_transaction(transaction)
    return envelope(request,{'model_version_id':model['_id'],'reason':body.reason})
