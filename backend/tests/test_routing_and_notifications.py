import os
from datetime import date
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock
import pytest
from bson import Decimal128
from fastapi import HTTPException
from pymongo import AsyncMongoClient
from database.init_schema import initialize
from src.services.routing import assignments
from src.api.claims import create
from src.api.products import service_record
from src.schemas.requests import ClaimCreate,Repair
from src.repositories.mongo import claim_for,now
from src.jobs.tasks import scan_warranties

@pytest.mark.asyncio
async def test_invalid_routing_fails_closed():
    db=SimpleNamespace(settings=SimpleNamespace(find_one=AsyncMock(return_value={
        'value':{'mobile':{'center_id':'disabled'}}})),
        service_centers=SimpleNamespace(find_one=AsyncMock(return_value=None)))
    with pytest.raises(HTTPException) as error: await assignments(db,'mobile')
    assert error.value.status_code==503

@pytest.mark.asyncio
async def test_center_routing_repairs_and_notification_windows():
    uri=os.environ.get('MONGO_TEST_URI')
    if not uri: pytest.skip('MONGO_TEST_URI replica set is required')
    async with AsyncMongoClient(uri,tz_aware=True) as client:
        db=client['assurex_test_'+uuid4().hex]
        try:
            await initialize(db)
            await db.products.insert_one({'_id':'p','owner_id':'customer','serial_normalized':'AB123',
                'brand':'Test','model':'Test','category':'mobile','purchase_date':'2026-01-01','amount':Decimal128('100')})
            await db.service_centers.insert_one({'_id':'center','name':'Assigned center','active':True})
            await db.users.insert_one({'_id':'reviewer','email_normalized':'reviewer@example.test',
                'password_hash':'unused','role':'reviewer','active':True})
            await db.settings.insert_one({'_id':'claim_routing','value':{'mobile':{'center_id':'center','reviewer_id':'reviewer'}}})
            request=SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db=db)),state=SimpleNamespace(request_id='test'))
            result=await create(ClaimCreate(product_id='p',facts={}),request,{'_id':'customer','role':'customer'})
            claim=result['data']
            assert claim['center_id']=='center' and claim['assigned_reviewer_id']=='reviewer'
            service={'_id':'service','role':'service','center_id':'center'}
            await claim_for(db,claim['id'],service)
            with pytest.raises(HTTPException) as error:
                await claim_for(db,claim['id'],dict(service,center_id='other'))
            assert error.value.status_code==404
            repair=Repair(claim_id=claim['id'],date='2026-09-01',authorized=True,notes='Screen repaired')
            await service_record('repairs','p',repair,request,service)
            assert await db.repairs.count_documents({'product_id':'p','center_id':'center'})==1
            await db.policy_versions.insert_one({'_id':'policy','category':'mobile','version':'1',
                'policy':{'reminder_window':10},'created_at':now()})
            await db.warranties.insert_one({'_id':'w','product_id':'p','provider':'Test','start_date':'2026-01-01',
                'expiry_date':'2026-09-30','policy_version_id':'policy'})
            await scan_warranties(db,date(2026,9,19))
            assert await db.notifications.count_documents({})==0
            await scan_warranties(db,date(2026,9,20))
            await scan_warranties(db,date(2026,9,21))
            assert await db.notifications.count_documents({'reminder_window':10})==1
            await db.policy_versions.insert_one({'_id':'policy-v2','category':'mobile','version':'2',
                'policy':{'reminder_window':5},'created_at':now()})
            await db.warranties.update_one({'_id':'w'},{'$set':{'policy_version_id':'policy-v2'}})
            await scan_warranties(db,date(2026,9,24))
            assert await db.notifications.count_documents({'reminder_window':5})==0
            await scan_warranties(db,date(2026,9,25))
            await scan_warranties(db,date(2026,10,1))
            assert await db.notifications.count_documents({'reminder_window':5})==1
        finally: await client.drop_database(db.name)
