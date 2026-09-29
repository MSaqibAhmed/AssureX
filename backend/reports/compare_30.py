import csv,json
from pathlib import Path
import pandas as pd
from src.ml.python_model.predict import PythonModel
from src.ml.gtm_adapter.predict import GTMModel
from src.ml.card import render_card
from src.engines.comparison import compare

def main():
    python=PythonModel('artifacts/python/pipeline.joblib'); gtm=GTMModel('artifacts/gtm/model.keras','artifacts/gtm/labels.json')
    test=pd.read_csv('data/test.csv'); chosen=test.groupby('label',group_keys=False).head(10); rows=[]
    for facts in chosen.to_dict('records'):
        p,g=python.predict(facts),gtm.predict(render_card(facts)); comparison=compare(p,g)
        rows.append({'group_id':facts['group_id'],'label':facts['label'],'python':json.dumps(p.model_dump()),
            'gtm':json.dumps(g.model_dump()),**comparison.model_dump()})
    with open('reports/model-comparison-30.csv','w',newline='',encoding='utf-8') as file:
        writer=csv.DictWriter(file,fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    print('30 test-claim comparisons written')
if __name__=='__main__': main()
