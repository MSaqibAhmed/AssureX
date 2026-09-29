import joblib, pandas as pd
from src.ml.features import build_features,CLASSES
from src.schemas.evaluation import Probabilities

class PythonModel:
    def __init__(self,path):
        self.pipeline=joblib.load(path)
        if set(self.pipeline.classes_) != set(CLASSES):
            raise ValueError('Unknown model class mapping')
    def predict(self,facts):
        scores=self.pipeline.predict_proba(pd.DataFrame([build_features(facts)]))[0]
        return Probabilities.model_validate(dict(zip(self.pipeline.classes_,map(float,scores))))
