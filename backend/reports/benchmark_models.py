"""Offline model timings only. Does NOT claim upload-to-Mongo processing latency."""
import json,time
from pathlib import Path
import numpy as np,pandas as pd
from src.ml.python_model.predict import PythonModel
from src.ml.gtm_adapter.predict import GTMModel
from src.ml.card import render_card

def metrics(values):
    return {'p50_ms':float(np.percentile(values,50)),'p95_ms':float(np.percentile(values,95)),'max_ms':max(values),'samples':len(values)}

def main():
    rows=pd.read_csv('data/test.csv').head(30).to_dict('records')
    start=time.perf_counter(); p=PythonModel('artifacts/python/pipeline.joblib'); g=GTMModel('artifacts/gtm/model.keras','artifacts/gtm/labels.json')
    p.predict(rows[0]); g.predict(render_card(rows[0])); cold=[(time.perf_counter()-start)*1000]
    warm=[]
    for row in rows:
        start=time.perf_counter(); p.predict(row); g.predict(render_card(row)); warm.append((time.perf_counter()-start)*1000)
    result={'scope':'Offline two-model inference plus card rendering; no OCR, queue, MongoDB, summary or network',
        'cold':metrics(cold),'warm':metrics(warm),'end_to_end_target_verified':False}
    Path('reports/model-latency.json').write_text(json.dumps(result,indent=2)); print(json.dumps(result))
if __name__=='__main__': main()
