import time
from rq import get_current_job

def retry_once(key):
    job=get_current_job()
    attempt=job.connection.incr(key)
    if attempt==1: raise RuntimeError('Deliberate transient test failure')
    return attempt

def slow_job(seconds):
    time.sleep(seconds)
    return 'finished'
