import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch
import pytest
from pymongo import AsyncMongoClient
from database.init_schema import initialize
from src.repositories.mongo import now
from src.jobs.tasks import ocr_job

@pytest.mark.asyncio
async def test_ocr_retry_commits_one_result(tmp_path):
    uri=os.environ.get('MONGO_TEST_URI')
    if not uri: pytest.skip('MONGO_TEST_URI replica set is required')
    async with AsyncMongoClient(uri,tz_aware=True) as client:
        db=client['assurex_test_'+uuid4().hex]
        try:
            await initialize(db)
            (tmp_path/'document').write_bytes(b'fixture')
            await db.documents.insert_one({'_id':'d','claim_id':'c','object_key':'document','sha256':'hash','mime':'application/pdf'})
            job={'_id':'j','claim_id':'c','document_id':'d','status':'running','stage':'ocr'}
            await db.jobs.insert_one(job)
            field={'field':'serial','raw_value':'A1','normalized_value':'A1','confidence':.9,'bbox':[0,0,10,10],'page':1}
            with patch('src.jobs.tasks.extract',return_value=[field]):
                await ocr_job(db,job,SimpleNamespace(evidence_root=tmp_path,max_pdf_pages=10))
                await ocr_job(db,job,SimpleNamespace(evidence_root=tmp_path,max_pdf_pages=10))
            assert await db.ocr_runs.count_documents({'document_id':'d'})==1
            assert await db.ocr_fields.count_documents({'document_id':'d'})==1
            assert (await db.jobs.find_one({'_id':'j'}))['status']=='completed'
        finally: await client.drop_database(db.name)
