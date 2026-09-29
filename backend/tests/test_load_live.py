"""Measured API load, isolated by the portable test runner's random database."""
import asyncio,json,os,secrets,time
from datetime import timedelta
from pathlib import Path
from uuid import uuid4
import httpx,numpy as np,pytest
from pymongo import MongoClient
from src.repositories.mongo import now
from src.security.auth import digest,COOKIE

def stats(values):
    return {'samples':len(values),'p50_ms':float(np.percentile(values,50)),
        'p95_ms':float(np.percentile(values,95)),'max_ms':max(values)}

def test_10000_claims_twenty_concurrent_users():
    if os.environ.get('FULL_TESTS')!='1': pytest.skip('Full local acceptance run required')
    dbname=os.environ['MONGO_DATABASE']
    assert dbname.startswith('assurex_test_')
    client=MongoClient(os.environ['MONGO_URI'],tz_aware=True); db=client[dbname]
    prefix='load-'+uuid4().hex
    owners=[prefix+str(i) for i in range(100)]
    tokens=[secrets.token_urlsafe(32) for _ in owners]
    sessions=[digest(t) for t in tokens]
    report={'scope':'Real HTTP scoped reports/dashboard, local Mongo replica set; excludes model inference',
        'concurrency':20,'claims':10000,'users':100}
    async def measure(total):
        semaphore=asyncio.Semaphore(20)
        async with httpx.AsyncClient(base_url=os.environ['E2E_BASE_URL'],timeout=30) as api:
            async def request(i):
                async with semaphore:
                    started=time.perf_counter()
                    response=await api.get('/api/v1/reports?status=Draft&limit=20',headers={'Cookie':COOKIE+'='+tokens[i%100]})
                    assert response.status_code==200,response.text
                    body=response.json()['data']
                    assert body['total']==total
                    assert all(row['claimant_id']==owners[i%100] for row in body['items'])
                    dashboard=await api.get('/api/v1/dashboard',headers={'Cookie':COOKIE+'='+tokens[i%100]})
                    assert dashboard.status_code==200,dashboard.text
                    assert dashboard.json()['data']['claim_counts']['Draft']==total
                    return (time.perf_counter()-started)*1000
            return await asyncio.gather(*(request(i) for i in range(200)))
    try:
        db.users.insert_many([{'_id':o,'email_normalized':o+'@example.test','role':'customer',
            'password_hash':'not-used','active':True} for o in owners])
        db.sessions.insert_many([{'_id':s,'user_id':o,'csrf':'test','expires_at':now()+timedelta(hours=1)} for s,o in zip(sessions,owners)])
        def rows(start,end):
            return [{'_id':prefix+'claim'+str(i),'public_claim_id':prefix+str(i),'claimant_id':owners[i%100],
                'product_id':prefix+'product','status':'Draft','version':1,'facts':{}} for i in range(start,end)]
        db.claims.insert_many(rows(0,100))
        report['baseline_100']=stats(asyncio.run(measure(1)))
        db.claims.insert_many(rows(100,10000))
        report['load_10000']=stats(asyncio.run(measure(100)))
        report['p95_ratio']=report['load_10000']['p95_ms']/report['baseline_100']['p95_ms']
        report['http_requests']=800
        report['errors']=0
        Path('reports/load-10000.json').write_text(json.dumps(report,indent=2))
        assert report['load_10000']['p95_ms']<2000,report
    finally:
        db.claims.delete_many({'claimant_id':{'$in':owners}})
        db.sessions.delete_many({'_id':{'$in':sessions}})
        db.users.delete_many({'_id':{'$in':owners}})
        client.close()
