import asyncio,hashlib,json,os
from pathlib import Path
from pymongo import AsyncMongoClient
from src.config import Settings
from src.repositories.mongo import now
from src.security.auth import hasher
from database.init_schema import initialize

async def seed():
    settings=Settings(); password=os.environ.get('DEMO_PASSWORD')
    if not password or len(password)<12: raise ValueError('Set DEMO_PASSWORD to at least 12 characters')
    async with AsyncMongoClient(settings.mongo_uri,tz_aware=True) as client:
        db=client[settings.mongo_database]; await initialize(db)
        for role in ('customer','service','reviewer','admin'):
            await db.users.update_one({'email_normalized':role+'@example.com'},{'$setOnInsert':{
                '_id':role,'name':role.title(),'email_normalized':role+'@example.com','password_hash':hasher.hash(password),
                'role':role,'active':True,'center_id':'central' if role=='service' else None}},upsert=True)
        await db.service_centers.update_one({'_id':'central'},{'$setOnInsert':{'name':'Central Service','active':True}},upsert=True)
        await db.settings.update_one({'_id':'claim_routing'},{'$setOnInsert':{
            'value':{'default':{'center_id':'central','reviewer_id':'reviewer'}}}},upsert=True)
        for path in Path('policies').glob('*.json'):
            policy=json.loads(path.read_text()); id=policy['category']+'-'+policy['version']
            await db.policy_versions.update_one({'_id':id},{'$setOnInsert':{'category':policy['category'],'version':policy['version'],'policy':policy,'created_at':now()}},upsert=True)
        for family,file in [('python','python/pipeline.joblib'),('gtm','gtm/model.keras')]:
            path=settings.artifact_root/file
            if not path.exists(): continue
            sha=hashlib.sha256(path.read_bytes()).hexdigest(); id=family+'-'+sha[:16]
            await db.model_versions.update_one({'_id':id},{'$setOnInsert':{'family':family,'version':sha[:16],'artifact_path':file,'sha256':sha,'created_at':now()}},upsert=True)
            await db.settings.update_one({'_id':'active_model:'+family},{'$setOnInsert':{'value':{'id':id}}},upsert=True)
        print('Schema, demo identities, policies and available model artifacts registered.')

if __name__=='__main__': asyncio.run(seed())
