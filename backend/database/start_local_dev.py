"""Start persistent loopback development services using the portable Windows tools."""
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen
from pymongo import MongoClient
from pymongo.errors import PyMongoError, OperationFailure

def occupied(port):
    with socket.socket() as probe:
        return probe.connect_ex(('127.0.0.1', port)) == 0

def main():
    backend = Path(__file__).resolve().parents[1]
    os.chdir(backend)
    if (backend / 'private/atlas.env').exists():
        from database.start_atlas import main as start_atlas
        return start_atlas()
    root = backend / 'private/test-tools'
    logs = root / 'dev-logs'
    logs.mkdir(exist_ok=True)
    data = root / 'dev-data'
    data.mkdir(exist_ok=True)
    redis_data = root / 'dev-redis'
    redis_data.mkdir(exist_ok=True)
    for port in (8000, 27018, 6380):
        if occupied(port):
            raise SystemExit(f'Port {port} already occupied; refusing duplicate startup')
    env = dict(os.environ, MONGO_URI='mongodb://127.0.0.1:27018/?replicaSet=rs0&directConnection=true',
        MONGO_DATABASE='assurex_local_dev', REDIS_URL='redis://127.0.0.1:6380/0',
        SESSION_SECRET=secrets.token_hex(32), COOKIE_SECURE='false',
        CORS_ORIGINS='["http://127.0.0.1:5173","http://127.0.0.1:5174","http://127.0.0.1:5180"]',
        EVIDENCE_ROOT=str(backend/'private/dev-evidence'),
        TESSDATA_PREFIX=str(root/'ocr-env/share/tessdata'))
    env['PATH'] = str(root/'ocr-env/Library/bin') + os.pathsep + env['PATH']
    processes = []
    def start(name, args, cwd=backend):
        with (logs/(name+'.log')).open('a') as log:
            process = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        processes.append(process)
        print(f'{name}: PID {process.pid}', flush=True)
        return process
    client = None
    try:
        mongo = next(root.glob('mongodb-*/bin/mongod.exe'))
        start('mongodb', [str(mongo), '--dbpath', str(data), '--port', '27018',
            '--bind_ip', '127.0.0.1', '--replSet', 'rs0', '--wiredTigerCacheSizeGB', '0.25'])
        client = MongoClient(env['MONGO_URI'], serverSelectionTimeoutMS=1000)
        direct = MongoClient('mongodb://127.0.0.1:27018/?directConnection=true',serverSelectionTimeoutMS=1000)
        try:
            for _ in range(60):
                try:
                    direct.admin.command('ping')
                    break
                except PyMongoError:
                    time.sleep(.5)
            try:
                direct.admin.command('replSetInitiate', {'_id':'rs0','members':[{'_id':0,'host':'127.0.0.1:27018'}]})
            except OperationFailure as error:
                if error.code != 23: raise
            for _ in range(60):
                if direct.admin.command('hello').get('isWritablePrimary'): break
                time.sleep(.5)
            else: raise RuntimeError('MongoDB primary not ready')
        finally:
            direct.close()
        redis = next(root.glob('redis/*/redis-server.exe'))
        start('redis', [str(redis),'--bind','127.0.0.1','--port','6380','--appendonly','yes','--dir',str(redis_data)],redis.parent)
        from redis import Redis
        connection = Redis.from_url(env['REDIS_URL'],socket_connect_timeout=1,socket_timeout=1)
        for _ in range(30):
            try:
                connection.ping()
                break
            except Exception: time.sleep(.5)
        else: raise RuntimeError('Redis not ready')
        connection.close()
        existing = client[env['MONGO_DATABASE']].users.count_documents({})
        env['DEMO_PASSWORD'] = secrets.token_urlsafe(15)
        subprocess.run([sys.executable,'-m','database.seed_demo'],env=env,check=True)
        start('api',[sys.executable,'-m','uvicorn','src.main:app','--host','127.0.0.1','--port','8000','--no-access-log'])
        start('dispatcher',[sys.executable,'-m','src.jobs.dispatcher'])
        start('worker',[sys.executable,'-m','src.jobs.worker'])
        for _ in range(60):
            try:
                with urlopen('http://127.0.0.1:8000/openapi.json',timeout=1): break
            except Exception: time.sleep(.5)
        else: raise RuntimeError('API not ready')
        print('Backend ready: http://127.0.0.1:8000/docs',flush=True)
        if not existing:
            print('Local development accounts: customer@example.com, reviewer@example.com, service@example.com, admin@example.com')
            print('Development password: '+env['DEMO_PASSWORD'])
        else:
            print('Existing local accounts preserved; use their previous passwords or register a customer.')
        print('Services remain running. Logs: '+str(logs))
    except BaseException:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=15)
        raise
    finally:
        if client: client.close()

if __name__ == '__main__': main()
