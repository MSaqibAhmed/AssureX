import hashlib, json, subprocess, time
from pathlib import Path
import joblib, pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import f1_score, accuracy_score, confusion_matrix
from src.ml.features import NUMERIC,CATEGORICAL,TRISTATE,FEATURES,CLASSES,build_features

def frame(df):
    return pd.DataFrame([build_features(r) for r in df.to_dict('records')])

def train(data=Path('data'), output=Path('artifacts/python')):
    train_df, val = (pd.read_csv(data/f'{s}.csv') for s in ['train','validation'])
    prep = ColumnTransformer([
        ('numeric',Pipeline([('impute',SimpleImputer(strategy='median')),('scale',StandardScaler())]),NUMERIC),
        ('category',OneHotEncoder(handle_unknown='ignore',sparse_output=False),CATEGORICAL+TRISTATE)])
    candidates = [(LogisticRegression(max_iter=1000),{'model__C':[.5,2]}),
        (RandomForestClassifier(random_state=42,n_jobs=1),{'model__n_estimators':[100],'model__max_depth':[8,None]}),
        (GradientBoostingClassifier(random_state=42),{'model__n_estimators':[80,120],'model__max_depth':[2]})]
    results=[]
    for estimator,grid in candidates:
        pipe=Pipeline([('prepare',prep),('model',estimator)])
        search=GridSearchCV(pipe,grid,cv=StratifiedKFold(5,shuffle=True,random_state=42),scoring='f1_macro',n_jobs=1)
        search.fit(frame(train_df),train_df.label)
        start=time.perf_counter(); pred=search.predict(frame(val)); elapsed=time.perf_counter()-start
        record={'algorithm':type(estimator).__name__,'validation_macro_f1':f1_score(val.label,pred,average='macro'),
            'invalid_to_valid':int(((val.label=='invalid') & (pred=='valid')).sum()),'latency_ms':elapsed*1000/len(val),
            'cv_macro_f1':search.best_score_,'parameters':search.best_params_}
        results.append((record,search.best_estimator_)); print(json.dumps(record),flush=True)
    results.sort(key=lambda item:(-item[0]['validation_macro_f1'],item[0]['invalid_to_valid'],item[0]['latency_ms']))
    winner=results[0][1]
    # Only now open untouched test split; never use test scores to select/tune a model.
    test=pd.read_csv(data/'test.csv'); pred=winner.predict(frame(test))
    metrics={'accuracy':accuracy_score(test.label,pred),'macro_f1':f1_score(test.label,pred,average='macro'),
        'confusion_matrix':confusion_matrix(test.label,pred,labels=CLASSES).tolist(),'class_order':CLASSES,'test_count':len(test)}
    output.mkdir(parents=True,exist_ok=True); joblib.dump(winner,output/'pipeline.joblib')
    sha=subprocess.run(['git','rev-parse','HEAD'],capture_output=True,text=True)
    metadata={'winner':results[0][0],'candidates':[r[0] for r in results],'test_metrics':metrics,
        'classes':list(winner.classes_),'feature_schema':FEATURES,'git_sha':sha.stdout.strip() or None,
        'dataset_hashes':json.loads((data/'manifest.json').read_text())['hashes']}
    (output/'metadata.json').write_text(json.dumps(metadata,indent=2)); (output/'metrics.json').write_text(json.dumps(metrics,indent=2))
    (output/'feature_schema.json').write_text(json.dumps({'numeric':NUMERIC,'categorical':CATEGORICAL,'tri_state':TRISTATE},indent=2))
    print(json.dumps(metrics),flush=True)

if __name__=='__main__': train()
