"""Disposable real RQ worker process with cooperative test shutdown."""
import os,sys,time
from pathlib import Path
from redis import Redis
from rq import Queue,SimpleWorker
from src.ml.inference_process import close_models

if __name__=='__main__':
    connection=Redis.from_url(os.environ['REDIS_URL'])
    stop=Path(sys.argv[1])
    queue=Queue('assurex',connection=connection)
    try:
        while not stop.exists():
            if queue.count:
                SimpleWorker([queue],connection=connection).work(burst=True,max_jobs=1,logging_level='WARNING')
            else: time.sleep(.05)
    finally:
        close_models()
        connection.close()
