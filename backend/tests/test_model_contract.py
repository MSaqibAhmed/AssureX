from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from src.ml.python_model.predict import PythonModel
from src.ml.gtm_adapter.predict import GTMModel
from PIL import Image

def test_class_reordering_uses_estimator_classes():
    model=object.__new__(PythonModel)
    model.pipeline=SimpleNamespace(classes_=np.array(['manual_review','invalid','valid']),predict_proba=lambda _:np.array([[.1,.2,.7]]))
    result=model.predict({})
    assert result.valid==.7 and result.invalid==.2 and result.manual_review==.1

def test_saved_python_artifact_has_valid_probability_contract():
    path=Path('artifacts/python/pipeline.joblib')
    if not path.exists(): pytest.skip('Train the Python artifact first')
    model=PythonModel(path)
    result=model.predict({'product_category':'mobile','serial_status':'unknown'})
    assert sum(result.model_dump().values())==pytest.approx(1)

def test_gtm_class_reordering_maps_explicit_labels():
    model=object.__new__(GTMModel)
    model.labels=['manual_review','valid','invalid']
    model.model=lambda *args,**kwargs:SimpleNamespace(numpy=lambda:np.array([[.1,.7,.2]]))
    result=model.predict(Image.new('RGB',(32,32)))
    assert result.valid==.7 and result.invalid==.2 and result.manual_review==.1

@pytest.mark.parametrize('scores',[[.1,.2,.3,.4],[float('nan'),.5,.5],[.3,.3,.3]])
def test_gtm_invalid_outputs_are_rejected(scores):
    model=object.__new__(GTMModel); model.labels=['valid','invalid','manual_review']
    model.model=lambda *args,**kwargs:SimpleNamespace(numpy=lambda:np.array([scores]))
    with pytest.raises(ValueError): model.predict(Image.new('RGB',(32,32)))
