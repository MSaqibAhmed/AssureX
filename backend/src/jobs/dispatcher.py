import asyncio,logging
from redis import Redis
from redis.exceptions import RedisError
from rq import Queue,Retry
from rq.exceptions import DuplicateJobError
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError
from src.config import Settings
from src.repositories.mongo import now

async def dispatch_once(db,queue):
    async for intent in db.outbox.find({'status':'pending'}):
        # Deterministic job ID allows safe replay after Redis enqueue/DB acknowledgment crashes.
        existing=queue.fetch_job(intent['_id'])
        if existing is None:
            try:
                queue.enqueue('src.jobs.tasks.perform',intent['_id'],job_id=intent['_id'],job_timeout=180,
                              retry=Retry(max=3,interval=[10,30,60]),result_ttl=86400,unique=True)
            except DuplicateJobError:
                pass  # Another dispatcher atomically enqueued this same intent.
        await db.outbox.update_one({'_id':intent['_id'],'status':'pending'},{'$set':{'status':'dispatched','dispatched_at':now()}})

async def reconcile_once(db,queue):
    # Failed jobs remain visible for operator review; do not reset exhausted retries.
    async for job in db.jobs.find({'status':{'$in':['queued','running']}}):
        if queue.fetch_job(job['_id']) is None:
            await db.outbox.update_one({'_id':job['_id'],'status':'dispatched'},{'$set':{'status':'pending'}})

async def main():
    settings=Settings(); redis=Redis.from_url(settings.redis_url,socket_connect_timeout=5,socket_timeout=5); queue=Queue('assurex',connection=redis)
    async with AsyncMongoClient(settings.mongo_uri,tz_aware=True,serverSelectionTimeoutMS=5000) as client:
        db=client[settings.mongo_database]
        while True:
            try:
                await dispatch_once(db,queue)
                # Recover lost Redis jobs without duplicating completed DB results.
                await reconcile_once(db,queue)
                day=now().date().isoformat()
                if queue.fetch_job('expiry-'+day) is None:
                    try:
                        queue.enqueue('src.jobs.tasks.expiry_scan',job_id='expiry-'+day,job_timeout=180,
                                      retry=Retry(max=3,interval=[30,60,120]),result_ttl=172800,unique=True)
                    except DuplicateJobError: pass
            except (RedisError,PyMongoError) as exc:
                # No URI or exception text: these can contain credentials or data.
                logging.warning('Dispatcher dependency unavailable (%s); retrying',type(exc).__name__)
            await asyncio.sleep(2)

if __name__=='__main__': asyncio.run(main())
