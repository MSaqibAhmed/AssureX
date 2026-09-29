"""Real MongoDB transaction test; never substitutes an in-memory database."""
import os
from uuid import uuid4
import pytest
from pymongo import AsyncMongoClient
from fastapi import HTTPException
from src.repositories.mongo import change_claim

@pytest.mark.asyncio
async def test_real_mongo_compare_and_swap():
    uri=os.environ.get('MONGO_TEST_URI')
    if not uri: pytest.skip('MONGO_TEST_URI replica set is required')
    async with AsyncMongoClient(uri) as client:
        db=client['assurex_test_'+uuid4().hex]
        try:
            await db.claims.insert_one({'_id':'c','version':1,'status':'Manual Review'})
            await change_claim(db,{'_id':'c'},1,'Manual Review',{'status':'Approved'})
            with pytest.raises(HTTPException) as error:
                await change_claim(db,{'_id':'c'},1,'Manual Review',{'status':'Rejected'})
            assert error.value.status_code==409
        finally: await client.drop_database(db.name)
