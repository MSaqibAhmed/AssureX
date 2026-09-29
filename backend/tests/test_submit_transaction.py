import os,json,asyncio
from pathlib import Path
from uuid import uuid4
from types import SimpleNamespace
import pytest
from bson import Decimal128
from fastapi import HTTPException
from pymongo import AsyncMongoClient
from database.init_schema import initialize
from src.repositories.mongo import now
from src.services.claim_service import submit
from src.schemas.requests import Expected
from src.jobs.tasks import evaluate

@pytest.mark.asyncio
async def test_submission_replay_has_one_revision_and_outbox():
    uri=os.environ.get('MONGO_TEST_URI')
    if not uri: pytest.skip('MONGO_TEST_URI replica set is required')
    async with AsyncMongoClient(uri,tz_aware=True) as client:
        db=client['assurex_test_'+uuid4().hex]
        try:
            await initialize(db)
            await db.products.insert_one({'_id':'p','owner_id':'u','serial_normalized':'AB123','brand':'Brand','model':'M',
                'category':'mobile','purchase_date':'2026-01-01','amount':Decimal128('100')})
            policy=json.loads(Path('policies/mobile.json').read_text())
            await db.policy_versions.insert_one({'_id':'policy','category':'mobile','version':'1','policy':policy,'created_at':now()})
            await db.warranties.insert_one({'_id':'w','product_id':'p','provider':'Test','start_date':'2026-01-01','expiry_date':'2026-12-31','policy_version_id':'policy'})
            for family in ('python','gtm'):
                await db.model_versions.insert_one({'_id':family,'family':family,'version':'1','artifact_path':'fixture','sha256':'fixture','created_at':now()})
                await db.settings.insert_one({'_id':'active_model:'+family,'value':{'id':family}})
            claim={'_id':'c','public_claim_id':'AX-test','claimant_id':'u','product_id':'p','status':'Draft','version':1,
                'facts':{'fault_date':'2026-09-01','fault_category':'display','description':'Screen fault','serial':'AB123','damage_type':'none'}}
            await db.claims.insert_one(claim)
            await db.claims.insert_one(dict(claim,_id='other',public_claim_id='AX-other'))
            expected=Expected(version=1,status='Draft')
            simultaneous=await asyncio.gather(*(submit(db,claim,{'_id':'u'},expected,'stable-key') for _ in range(2)))
            assert simultaneous[0]==simultaneous[1]
            jid=simultaneous[0]
            assert await submit(db,claim,{'_id':'u'},expected,'stable-key')==jid
            assert await db.claim_revisions.count_documents({})==1
            saved_revision=await db.claim_revisions.find_one({'claim_id':'c'})
            assert saved_revision['report_snapshot']['product']['brand']=='Brand'
            assert saved_revision['report_snapshot']['warranty']['provider']=='Test'
            await db.products.update_one({'_id':'p'},{'$set':{'brand':'Changed later'}})
            assert (await db.claim_revisions.find_one({'claim_id':'c'}))['report_snapshot']['product']['brand']=='Brand'
            assert await db.outbox.count_documents({})==1
            assert await db.duplicate_links.count_documents({'claim_id':'c','resolved':False})==1
            with pytest.raises(HTTPException) as error:
                await submit(db,claim,{'_id':'u'},Expected(version=2,status='Draft'),'stable-key')
            assert error.value.status_code==409
            job=await db.jobs.find_one({'_id':jid})
            settings=SimpleNamespace(artifact_root=Path('artifacts'))
            # Missing pinned artifacts must commit an explicit manual recommendation,
            # never a fabricated prediction. A worker retry must not duplicate it.
            await evaluate(db,job,settings)
            await evaluate(db,job,settings)
            assert await db.evaluation_runs.count_documents({})==1
            evaluation=await db.evaluation_runs.find_one({})
            assert evaluation['recommendation']=='Manual Review Required'
            assert set(evaluation['model_errors'])=={'python','gtm'}
            assert evaluation['predictions']=={'python':None,'gtm':None}
            assert (await db.claims.find_one({'_id':'c'}))['status']=='Manual Review'
            assert await db.outbox.count_documents({'kind':'summary'})==1
            assert await db.notifications.count_documents({'event_type':'evaluation_completed'})==1
        finally: await client.drop_database(db.name)
