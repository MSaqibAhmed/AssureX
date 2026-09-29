from redis import Redis
from rq import Queue,SimpleWorker
from src.config import Settings

if __name__=='__main__':
    settings=Settings(); connection=Redis.from_url(settings.redis_url)
    # Keep the parent alive across jobs; model subprocesses enforce hard inference
    # timeouts and preserve loaded artifacts for normal warm requests.
    SimpleWorker([Queue('assurex',connection=connection)],connection=connection).work(with_scheduler=True)
