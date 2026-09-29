import asyncio,os
from types import SimpleNamespace
from uuid import uuid4
import pytest
from pymongo import AsyncMongoClient
from fastapi import HTTPException
from database.init_schema import initialize
from src.api.reviews import review
from src.schemas.requests import Review

@pytest.mark.asyncio
async def test_simultaneous_reviewers_append_exactly_one_decision():
    uri=os.environ.get('MONGO_TEST_URI')
    if not uri: pytest.skip('MONGO_TEST_URI replica set is required')
    async with AsyncMongoClient(uri,tz_aware=True) as client:
        db=client['assurex_test_'+uuid4().hex]
        try:
            await initialize(db)
            await db.claims.insert_one({'_id':'c','public_claim_id':'AX-test','claimant_id':'owner','product_id':'p',
                'status':'Manual Review','version':3,'latest_evaluation_id':'e','assigned_reviewer_id':'reviewer'})
            request=SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db=db)),state=SimpleNamespace(request_id='test'))
            user={'_id':'reviewer','role':'reviewer'}
            bodies=[Review(version=3,status='Manual Review',evaluation_id='e',action=action,reason='Evidence reviewed') for action in ('approve','reject')]
            results=await asyncio.gather(*(review('c',body,request,user) for body in bodies),return_exceptions=True)
            assert sum(isinstance(r,dict) for r in results)==1
            conflicts=[r for r in results if isinstance(r,HTTPException)]
            assert len(conflicts)==1 and conflicts[0].status_code==409
            assert await db.reviews.count_documents({'claim_id':'c'})==1
            assert await db.audit_events.count_documents({'target_id':'c'})==1
            assert await db.notifications.count_documents({'recipient':'owner'})==1
        finally:
            await client.drop_database(db.name)
