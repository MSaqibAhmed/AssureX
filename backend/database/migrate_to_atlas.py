"""One-time local-to-Atlas copy; requires source app writers to be stopped."""
import hashlib,json,os,sys
from datetime import datetime,timezone
from pathlib import Path
from bson import BSON,json_util
from dotenv import dotenv_values
from pymongo import MongoClient

def digest(docs):
    return hashlib.sha256(b''.join(sorted(hashlib.sha256(BSON.encode(d)).digest() for d in docs))).hexdigest()

def main():
    base=Path(__file__).resolve().parents[1]
    cfg=dotenv_values(base/'private/atlas.env')
    uri=cfg['MONGO_URI']
    assert '@cluster0.t0yoj9e.mongodb.net/' in uri, 'Unexpected Atlas target'
    source=MongoClient('mongodb://127.0.0.1:27018/?replicaSet=rs0&directConnection=true',serverSelectionTimeoutMS=5000)
    target=MongoClient(uri,serverSelectionTimeoutMS=20000)
    src=source['assurex_local_dev']; dst=target['assurex']
    target.admin.command('ping')
    if dst.list_collection_names():
        raise RuntimeError('Destination is not empty; refusing to overwrite or merge')
    if src.jobs.count_documents({'status':{'$in':['queued','running']}}):
        raise RuntimeError('Source has pending work; finish it before migration')
    backup=base/'private'/('atlas-migration-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir()
    snapshots={}; manifest={'source':'assurex_local_dev','destination':'assurex','host':'cluster0.t0yoj9e.mongodb.net','collections':{},'verified':False}
    for name in sorted(src.list_collection_names()):
        docs=list(src[name].find({})); options=src[name].options(); indexes=list(src[name].list_indexes())
        snapshots[name]=(docs,options,indexes)
        (backup/(name+'.bson')).write_bytes(b''.join(BSON.encode(d) for d in docs))
        (backup/(name+'.metadata.json')).write_text(json_util.dumps({'options':options,'indexes':indexes}),encoding='utf-8')
    for name,(docs,options,indexes) in snapshots.items():
        dst.create_collection(name,**options)
        if docs: dst[name].insert_many(docs,ordered=True)
        for index in indexes:
            if index['name']=='_id_': continue
            args={k:v for k,v in index.items() if k not in ('key','v','ns')}
            dst[name].create_index(list(index['key'].items()),**args)
        actual=list(dst[name].find({}))
        match=digest(docs)==digest(actual)
        manifest['collections'][name]={'source_count':len(docs),'atlas_count':len(actual),'sha256':digest(docs),'matched':match}
        (backup/'verification.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        if not match: raise RuntimeError('Content verification failed for '+name)
        if dst[name].options()!=options: raise RuntimeError('Collection options differ: '+name)
        print(name+': '+str(len(actual))+' documents verified',flush=True)
    for name,(docs,_,_) in snapshots.items():
        if digest(list(src[name].find({})))!=digest(docs): raise RuntimeError('Source changed during migration: '+name)
    with target.start_session() as session:
        session.start_transaction()
        dst.settings.insert_one({'_id':'atlas-migration-transaction-check','value':{}},session=session)
        session.abort_transaction()
    manifest['verified']=True
    manifest['transaction_check']='passed (aborted test write)'
    manifest['completed_at']=datetime.now(timezone.utc).isoformat()
    (backup/'verification.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Verified migration. Backup and report: '+str(backup))
    print('Admin accounts preserved: '+str(dst.users.count_documents({'role':'admin'})))
    source.close(); target.close()

if __name__=='__main__':
    try: main()
    except Exception as error:
        print('Migration stopped: '+type(error).__name__)
        # Mongo exceptions can contain credentials; do not log their raw text.
        if isinstance(error,(RuntimeError,AssertionError)): print(str(error))
        sys.exit(1)
