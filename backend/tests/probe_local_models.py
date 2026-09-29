"""Read-only diagnostic of saved artifacts against the latest local revision."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time
from pymongo import MongoClient
from src.ml.inference_process import infer, close_models

def main():
    with MongoClient('mongodb://127.0.0.1:27018/?directConnection=true',serverSelectionTimeoutMS=5000) as client:
        db=client['assurex_local_dev']
        evaluation=db.evaluation_runs.find_one(sort=[('completed_at',-1)])
        revision=db.claim_revisions.find_one({'_id':evaluation['claim_revision_id']})
    def check(family):
        started=time.perf_counter()
        try:
            output=infer(family,Path('artifacts')/revision['models'][family]['artifact_path'],revision['facts_json'],120)
            print(family,output.model_dump(),'seconds',round(time.perf_counter()-started,2),flush=True)
        except Exception as exc: print(family,type(exc).__name__,str(exc),flush=True)
    try:
        with ThreadPoolExecutor(2) as pool: list(pool.map(check,['python','gtm']))
    finally: close_models()

if __name__=='__main__': main()
