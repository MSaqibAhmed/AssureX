"""Run with python -m database.init_schema against a transaction-capable Mongo replica set."""
import asyncio
from pymongo import ASCENDING, IndexModel

S = {'bsonType':'string'}
I = {'bsonType':['int','long']}
D = {'bsonType':'date'}
O = {'bsonType':'object'}
B = {'bsonType':'bool'}
A = {'bsonType':'array'}
SCHEMAS = {
 'users': {'email_normalized':S,'password_hash':S,'role':{'enum':['customer','service','reviewer','admin']},'active':B},
 'service_centers': {'name':S,'active':B},
 'products': {'owner_id':S,'serial_normalized':S,'brand':S,'model':S,'purchase_date':S,'amount':{'bsonType':'decimal'}},
 'warranties': {'product_id':S,'provider':S,'start_date':S,'expiry_date':S,'policy_version_id':S},
 'claims': {'public_claim_id':S,'claimant_id':S,'product_id':S,'status':{'enum':['Draft','Submitted','Under Evaluation','Manual Review','Additional Information Required','Approved','Rejected','Closed']},'version':I},
 'claim_revisions': {'claim_id':S,'revision_number':I,'facts_json':O,'submitted_at':D},
 'documents': {'claim_id':S,'object_key':S,'sha256':S,'mime':S},
 'ocr_runs': {'document_id':S,'engine_version':S,'status':S},
 'ocr_fields': {'document_id':S,'field':S,'raw_value':{'bsonType':['string','null']},'normalized_value':{'bsonType':['string','null']},'confidence':{'bsonType':['double','int','null']},'bbox':A},
 'repairs': {'product_id':S,'authorized':{'bsonType':['bool','null']},'date':S},
 'replacements': {'product_id':S,'authorized':{'bsonType':['bool','null']},'old_serial':S,'new_serial':S},
 'policy_versions': {'category':S,'version':S,'policy':O,'created_at':D},
 'model_versions': {'family':S,'version':S,'artifact_path':S,'sha256':S,'created_at':D},
 'evaluation_runs': {'claim_revision_id':S,'input_hash':S,'evaluation_input_version_hash':S,'status':{'enum':['completed']},'versions':O,'predictions':O,'comparison':O,'rule_results':A,'recommendation':S,'reasons':A},
 'claim_summaries': {'claim_revision_id':S,'model_version':S,'prompt_version':S,'input_hash':S,'text':S,'source':{'enum':['local_model','fallback']},'quality_flags':A,'elapsed_ms':{'bsonType':['int','double']}},
 'reviews': {'claim_id':S,'reviewer_id':S,'action':{'enum':['approve','reject','request_info']},'reason':{'bsonType':'string','minLength':1},'evaluation_id':S,'timestamp':D,'version':I,'status':S},
 'audit_events': {'actor_id':S,'action':S,'target_id':S,'timestamp':D},
 'notifications': {'recipient':S,'event_type':S,'target_revision':S,'reminder_window':I,'read':B},
 'duplicate_links': {'claim_id':S,'other_claim_id':S,'kind':S,'resolved':B},
 'outbox': {'kind':S,'target_id':S,'status':S,'created_at':D},
 'jobs': {'claim_id':S,'status':{'enum':['queued','running','completed','failed']},'stage':S},
 'sessions': {'user_id':S,'csrf':S,'expires_at':D},
 'settings': {'value':O},
 'idempotency': {'claim_id':S,'key':S,'request_hash':S,'job_id':S},
 'comments': {'claim_id':S,'author_id':S,'message':S,'visibility':{'enum':['staff','customer']},'timestamp':D},
}
INDEXES = {
 'users': [IndexModel('email_normalized', unique=True)],
 'products': [IndexModel([('owner_id',1),('serial_normalized',1)])],
 'warranties': [IndexModel('product_id',unique=True),IndexModel('expiry_date')],
 'claims': [IndexModel('public_claim_id',unique=True),IndexModel([('claimant_id',1),('status',1),('_id',1)]),IndexModel([('assigned_reviewer_id',1),('status',1),('_id',1)]),IndexModel([('center_id',1),('status',1),('_id',1)])],
 'claim_revisions': [IndexModel([('claim_id',1),('revision_number',1)],unique=True)],
 'documents': [IndexModel('sha256'),IndexModel('claim_id')],
 'ocr_fields': [IndexModel('document_id')],
 'policy_versions': [IndexModel([('category',1),('version',1)],unique=True)],
 'model_versions': [IndexModel([('family',1),('version',1)],unique=True)],
 'evaluation_runs': [IndexModel('evaluation_input_version_hash',unique=True),IndexModel('claim_revision_id')],
 'claim_summaries': [IndexModel('claim_revision_id',unique=True)],
 'reviews': [IndexModel([('claim_id',1),('timestamp',1)])],
 'audit_events': [IndexModel([('target_id',1),('timestamp',1)])],
 'notifications': [IndexModel([('recipient',1),('event_type',1),('target_revision',1),('reminder_window',1)],unique=True)],
 'duplicate_links': [IndexModel([('claim_id',1),('other_claim_id',1),('kind',1)],unique=True)],
 'outbox': [IndexModel([('status',1),('created_at',1)])],
 'sessions': [IndexModel('expires_at',expireAfterSeconds=0)],
 'idempotency': [IndexModel([('claim_id',1),('key',1)],unique=True)],
 'comments': [IndexModel([('claim_id',1),('timestamp',1)])],
}

async def initialize(db):
    existing = await db.list_collection_names()
    for name, properties in SCHEMAS.items():
        validator = {'$jsonSchema':{'bsonType':'object','required':list(properties),'properties':properties}}
        if name not in existing:
            await db.create_collection(name, validator=validator)
        else:
            await db.command('collMod',name,validator=validator,validationLevel='strict')
        if name in INDEXES:
            await db[name].create_indexes(INDEXES[name])

async def main():
    from pymongo import AsyncMongoClient
    from src.config import Settings
    settings = Settings()
    async with AsyncMongoClient(settings.mongo_uri) as client:
        await initialize(client[settings.mongo_database])

if __name__ == '__main__':
    asyncio.run(main())
