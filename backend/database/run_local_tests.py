"""Start one disposable portable Mongo replica set, run tests, stop it.
Only the provided private test directory is used; no OS service is installed.
"""
import os,subprocess,sys,time,secrets,socket
from tempfile import TemporaryDirectory
from uuid import uuid4
from urllib.request import urlopen
from urllib.error import URLError,HTTPError
from pathlib import Path
from pymongo import MongoClient
from pymongo.errors import OperationFailure,PyMongoError

def main():
    root=Path('private/test-tools').resolve()
    full='--full' in sys.argv
    args=[arg for arg in sys.argv[1:] if arg!='--full']
    mongo_port=int(os.environ.get('TEST_MONGO_PORT','27018'))
    redis_port=int(os.environ.get('TEST_REDIS_PORT','6380'))
    for port in ([mongo_port,18000,redis_port] if full else [mongo_port,18000]):
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1',port))==0:
                raise SystemExit(f'Test port {port} is occupied; refusing to touch an existing service')
    candidates=list(root.glob('mongodb-*/bin/mongod.exe'))
    if not candidates: raise SystemExit('Extract the MongoDB Windows ZIP under private/test-tools first')
    data=root/('data' if mongo_port==27018 else f'test-data-{mongo_port}'); data.mkdir(exist_ok=True)
    process=subprocess.Popen([str(candidates[0]),'--dbpath',str(data),'--port',str(mongo_port),'--bind_ip','127.0.0.1',
        '--replSet','rs0','--logpath',str(root/'mongodb.log'),'--logappend','--wiredTigerCacheSizeGB','0.25'],
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    uri=f'mongodb://127.0.0.1:{mongo_port}/?replicaSet=rs0&directConnection=true'
    client=MongoClient(f'mongodb://127.0.0.1:{mongo_port}/?directConnection=true',serverSelectionTimeoutMS=1000)
    api=None
    api_log=None
    redis_process=None
    redis_log=None
    redis_client=None
    api_database='assurex_test_api_'+uuid4().hex
    evidence=TemporaryDirectory(prefix='evidence-',dir=root)
    try:
        for _ in range(60):
            if process.poll() is not None: raise RuntimeError('MongoDB failed to start; inspect private/test-tools/mongodb.log')
            try:
                client.admin.command('ping'); break
            except PyMongoError: time.sleep(.5)
        try: client.admin.command('replSetInitiate',{'_id':'rs0','members':[{'_id':0,'host':f'127.0.0.1:{mongo_port}'}]})
        except OperationFailure as exc:
            if exc.code!=23: raise
        for _ in range(60):
            if client.admin.command('hello').get('isWritablePrimary'): break
            time.sleep(.5)
        env=dict(os.environ,MONGO_TEST_URI=uri,MONGO_URI=uri,MONGO_DATABASE=api_database,
            SESSION_SECRET=secrets.token_hex(32),COOKIE_SECURE='false',E2E_BASE_URL='http://127.0.0.1:18000',
            EVIDENCE_ROOT=evidence.name,CORS_ORIGINS='["http://127.0.0.1:5173","http://127.0.0.1:5174"]')
        if full:
            from redis import Redis
            from redis.retry import Retry
            from redis.backoff import NoBackoff
            redis_binary=next(root.glob('redis/*/redis-server.exe'),None)
            ocr_bin=root/'ocr-env/Library/bin'
            if redis_binary is None or not (ocr_bin/'tesseract.exe').exists():
                raise RuntimeError('Full tests require portable Redis and the Tesseract environment')
            env.update(REDIS_URL=f'redis://127.0.0.1:{redis_port}/0',REDIS_TEST_URL=f'redis://127.0.0.1:{redis_port}/15',
                FULL_TESTS='1',TESSDATA_PREFIX=str(root/'ocr-env/share/tessdata'),REDIS_TEST_BINARY=str(redis_binary))
            env['PATH']=str(ocr_bin)+os.pathsep+env['PATH']
            redis_log=(root/'redis.log').open('w')
            redis_process=subprocess.Popen([str(redis_binary),'--bind','127.0.0.1','--port',str(redis_port),
                '--save','','--appendonly','no'],stdout=redis_log,stderr=subprocess.STDOUT,
                cwd=redis_binary.parent,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            redis_client=Redis.from_url(env['REDIS_URL'],socket_connect_timeout=1,socket_timeout=2,retry=Retry(NoBackoff(),0))
            for _ in range(60):
                if redis_process.poll() is not None: raise RuntimeError('Redis startup failed; inspect redis.log')
                try:
                    if redis_client.ping(): break
                except Exception: time.sleep(.5)
            else: raise RuntimeError('Redis did not become ready')
        subprocess.run([sys.executable,'-m','database.init_schema'],env=env,check=True)
        api_log=(root/'api.log').open('w')
        api=subprocess.Popen([sys.executable,'-m','uvicorn','src.main:app','--host','127.0.0.1','--port','18000','--no-access-log'],
            env=env,stdout=api_log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        for _ in range(60):
            if api.poll() is not None: raise RuntimeError('API failed to start; inspect private/test-tools/api.log')
            try:
                with urlopen(env['E2E_BASE_URL']+'/openapi.json',timeout=1): break
            except (URLError,HTTPError): time.sleep(.5)
        else: raise RuntimeError('API did not become ready')
        result=subprocess.run([sys.executable,'-m','pytest','-q','-p','no:cacheprovider','--cov=src',
            '--cov-report=term','--cov-report=xml:reports/coverage.xml',*args],env=env)
        return result.returncode
    finally:
        if api is not None:
            api.terminate(); api.wait(timeout=10)
        if api_log is not None: api_log.close()
        evidence.cleanup()
        if redis_process is not None:
            if redis_client is not None:
                try: redis_client.shutdown(nosave=True)
                except Exception: pass
                redis_client.close()
            try: redis_process.wait(timeout=10)
            except subprocess.TimeoutExpired: redis_process.terminate(); redis_process.wait(timeout=10)
        if redis_log is not None: redis_log.close()
        try: client.drop_database(api_database)
        except PyMongoError: pass
        try: client.admin.command('shutdown',force=True)
        except PyMongoError: pass
        client.close()
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.terminate(); process.wait(timeout=10)

if __name__=='__main__': sys.exit(main())
