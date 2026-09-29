import asyncio,os,time,socket,subprocess,sys
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock,Mock
import pytest
from redis import Redis
from redis.retry import Retry as RedisRetry
from redis.backoff import NoBackoff
from rq import Queue,SimpleWorker,Retry
from rq.exceptions import DuplicateJobError
from rq.scheduler import RQScheduler
from src.jobs.dispatcher import dispatch_once,reconcile_once
from tests.queue_jobs import retry_once,slow_job

@pytest.fixture
def redis_queue():
    uri=os.environ.get('REDIS_TEST_URL')
    if not uri: pytest.skip('REDIS_TEST_URL required')
    connection=Redis.from_url(uri)
    connection.ping()
    queue=Queue('assurex-test-'+uuid4().hex,connection=connection)
    yield queue
    # Only this random queue and its jobs; never FLUSHDB on a caller's Redis.
    for job in queue.get_jobs(): job.delete()
    queue.delete(delete_jobs=True)
    connection.close()

def test_atomic_unique_enqueue_and_execution(redis_queue):
    queue=redis_queue; jid=uuid4().hex
    job=queue.enqueue('operator.add',2,3,job_id=jid,unique=True)
    with pytest.raises(DuplicateJobError): queue.enqueue('operator.add',2,3,job_id=jid,unique=True)
    assert queue.count==1
    SimpleWorker([queue],connection=queue.connection).work(burst=True,logging_level='WARNING')
    assert job.get_status(refresh=True)=='finished' and job.return_value()==5
    job.delete()

def test_retry_scheduling_and_execution(redis_queue):
    queue=redis_queue; key='assurex-test-attempt:'+uuid4().hex
    job=queue.enqueue(retry_once,key,retry=Retry(max=1,interval=1))
    scheduler=RQScheduler([queue],connection=queue.connection)
    try:
        SimpleWorker([queue],connection=queue.connection).work(burst=True,logging_level='CRITICAL')
        assert job.get_status(refresh=True)=='scheduled'
        scheduler.acquire_locks()
        time.sleep(1.1)
        scheduler.enqueue_scheduled_jobs()
        SimpleWorker([queue],connection=queue.connection).work(burst=True,logging_level='CRITICAL')
        assert job.get_status(refresh=True)=='finished' and job.return_value()==2
    finally:
        scheduler.release_locks()
        job.delete(); queue.connection.delete(key)

def test_real_worker_timeout_is_failed_not_a_success(redis_queue):
    queue=redis_queue
    job=queue.enqueue(slow_job,2,job_timeout=1)
    try:
        SimpleWorker([queue],connection=queue.connection).work(burst=True,logging_level='CRITICAL')
        assert job.get_status(refresh=True)=='failed'
        assert 'JobTimeoutException' in job.exc_info
    finally: job.delete()

class Cursor:
    def __init__(self,rows): self.rows=rows
    def __aiter__(self):
        async def items():
            for row in self.rows: yield row
        return items()

def test_live_queue_crash_before_ack_and_lost_job_recovery(redis_queue):
    queue=redis_queue; jid=uuid4().hex
    update=AsyncMock(side_effect=RuntimeError('Simulated Mongo acknowledgment loss'))
    db=SimpleNamespace(outbox=SimpleNamespace(find=Mock(return_value=Cursor([{'_id':jid}])),update_one=update),
        jobs=SimpleNamespace(find=Mock(return_value=Cursor([{'_id':jid,'status':'queued'}]))))
    with pytest.raises(RuntimeError): asyncio.run(dispatch_once(db,queue))
    assert queue.count==1
    update.side_effect=None
    asyncio.run(dispatch_once(db,queue))
    assert queue.count==1
    queue.fetch_job(jid).delete()  # Simulated loss of this job, not a destructive global Redis reset.
    asyncio.run(reconcile_once(db,queue))
    assert update.call_args.args[1]=={'$set':{'status':'pending'}}
    asyncio.run(dispatch_once(db,queue))
    assert queue.fetch_job(jid) is not None and queue.count==1

def test_actual_redis_process_loss_replays_durable_mongo_outbox(tmp_path):
    from pathlib import Path
    from pymongo import AsyncMongoClient
    from database.init_schema import initialize
    from src.repositories.mongo import now
    binary=os.environ.get('REDIS_TEST_BINARY')
    if not binary: pytest.skip('Portable Redis binary required for isolated restart test')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0)); port=probe.getsockname()[1]
    log=(tmp_path/'redis-restart.log').open('w'); process=None; dispatcher=None
    connection=Redis(host='127.0.0.1',port=port,socket_connect_timeout=1,socket_timeout=2,retry=RedisRetry(NoBackoff(),0))
    def start():
        child=subprocess.Popen([binary,'--bind','127.0.0.1','--port',str(port),'--save','','--appendonly','no'],
            cwd=Path(binary).parent,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        for _ in range(50):
            try:
                if connection.ping(): return child
            except Exception: time.sleep(.1)
        child.terminate(); child.wait(timeout=10)
        raise AssertionError('Redis did not start')
    async def exercise():
        nonlocal process,dispatcher
        async with AsyncMongoClient(os.environ['MONGO_TEST_URI'],tz_aware=True) as client:
            db=client['assurex_test_'+uuid4().hex]
            try:
                await initialize(db)
                jid=uuid4().hex
                await db.jobs.insert_one({'_id':jid,'claim_id':'test','status':'queued','stage':'queued'})
                await db.outbox.insert_one({'_id':jid,'kind':'evaluation','target_id':'test','status':'pending','created_at':now()})
                process=start(); queue=Queue('restart-test',connection=connection)
                await dispatch_once(db,queue)
                assert queue.count==1
                # Production dispatcher uses the assurex queue; preserve the same job ID.
                queue.fetch_job(jid).delete()
                queue=Queue('assurex',connection=connection)
                await reconcile_once(db,queue); await dispatch_once(db,queue)
                dispatcher=subprocess.Popen([sys.executable,'-m','src.jobs.dispatcher'],
                    env=dict(os.environ,MONGO_DATABASE=db.name,REDIS_URL=f'redis://127.0.0.1:{port}/0'),
                    stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                process.kill(); process.wait(timeout=10)
                await asyncio.sleep(2.5)
                assert dispatcher.poll() is None,'Dispatcher must survive a Redis connection failure'
                process=start()
                for _ in range(150):
                    if queue.fetch_job(jid) is not None: break
                    await asyncio.sleep(.1)
                assert queue.fetch_job(jid) is not None
                assert queue.job_ids.count(jid)==1
                assert (await db.outbox.find_one({'_id':jid}))['status']=='dispatched'
            finally: await client.drop_database(db.name)
    try: asyncio.run(exercise())
    finally:
        if dispatcher is not None and dispatcher.poll() is None:
            dispatcher.terminate(); dispatcher.wait(timeout=10)
        if process is not None and process.poll() is None:
            try: connection.shutdown(nosave=True)
            except Exception: pass
            process.wait(timeout=10)
        connection.close(); log.close()
