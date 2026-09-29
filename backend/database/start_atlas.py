"""Start API and queue processes from private Atlas settings, never local MongoDB."""
import json,os,secrets,socket,subprocess,sys,time
from pathlib import Path
from urllib.request import urlopen
from dotenv import load_dotenv
from pymongo import MongoClient
from redis import Redis

def occupied(port):
    with socket.socket() as probe: return probe.connect_ex(('127.0.0.1',port))==0

def main():
    base=Path(__file__).resolve().parents[1]; os.chdir(base)
    config=base/'private/atlas.env'
    if not config.exists(): raise RuntimeError('Configure private/atlas.env first')
    load_dotenv(config,override=True)
    if occupied(8000): raise RuntimeError('Port 8000 occupied; stop the previous API before startup')
    uri=os.environ.get('MONGO_URI','')
    if '@cluster0.t0yoj9e.mongodb.net/' not in uri: raise RuntimeError('Unexpected Atlas target')
    with MongoClient(uri,serverSelectionTimeoutMS=15000) as client: client.admin.command('ping')
    secret=base/'private/session-secret.txt'
    if not secret.exists(): secret.write_text(secrets.token_hex(32),encoding='utf-8')
    os.environ['SESSION_SECRET']=secret.read_text(encoding='utf-8').strip()
    tools=base/'private/test-tools'; logs=base/'private/atlas-logs'; logs.mkdir(exist_ok=True)
    os.environ['PATH']=str(tools/'ocr-env/Library/bin')+os.pathsep+os.environ['PATH']
    os.environ['TESSDATA_PREFIX']=str(tools/'ocr-env/share/tessdata')
    children={}
    def start(name,args,cwd=base):
        with (logs/(name+'.log')).open('a',encoding='utf-8') as log:
            p=subprocess.Popen(args,cwd=cwd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        children[name]=p; return p
    try:
        if not occupied(6380):
            redis=next(tools.glob('redis/*/redis-server.exe'))
            data=base/'private/atlas-redis'; data.mkdir(exist_ok=True)
            start('redis',[str(redis),'--bind','127.0.0.1','--port','6380','--appendonly','yes','--dir',str(data)],redis.parent)
        connection=Redis.from_url(os.environ['REDIS_URL'],socket_connect_timeout=2,socket_timeout=2)
        for _ in range(20):
            try: connection.ping(); break
            except Exception: time.sleep(.5)
        else: raise RuntimeError('Redis did not become ready')
        from rq import Worker
        if Worker.all(connection=connection): raise RuntimeError('Atlas Redis DB already has registered workers; inspect before duplicate startup')
        start('api',[sys.executable,'-m','uvicorn','src.main:app','--host','127.0.0.1','--port','8000','--no-access-log'])
        start('dispatcher',[sys.executable,'-m','src.jobs.dispatcher'])
        start('worker',[sys.executable,'-m','src.jobs.worker'])
        for _ in range(60):
            if any(p.poll() is not None for p in children.values()): raise RuntimeError('A service exited; inspect private/atlas-logs')
            try:
                with urlopen('http://127.0.0.1:8000/openapi.json',timeout=1): break
            except Exception: time.sleep(.5)
        else: raise RuntimeError('API did not become ready')
        (logs/'processes.json').write_text(json.dumps({k:p.pid for k,p in children.items()},indent=2),encoding='utf-8')
        print('Atlas backend ready: http://127.0.0.1:8000/docs')
        print('Database: assurex on cluster0.t0yoj9e.mongodb.net; Redis logical DB 1')
        print('Processes: '+json.dumps({k:p.pid for k,p in children.items()}))
        print('Services run in background. Logs and PID record: '+str(logs))
    except BaseException:
        for p in reversed(list(children.values())):
            if p.poll() is None: p.terminate(); p.wait(timeout=15)
        raise

if __name__=='__main__':
    try: main()
    except Exception as error:
        print('Atlas startup failed: '+type(error).__name__)
        if isinstance(error,RuntimeError): print(str(error))
        sys.exit(1)
