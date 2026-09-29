import time
from pathlib import Path
import pytest
from src.ml.inference_process import bounded_call,ModelUnavailable

def sleepy(connection):
    time.sleep(30)

def failed(connection):
    connection.send({'error':'explicit_failure'})

def test_model_timeout_is_explicit_and_process_is_stopped():
    started=time.monotonic()
    with pytest.raises(ModelUnavailable,match='model_timeout'):
        bounded_call(sleepy,(),.1)
    assert time.monotonic()-started<10

def test_model_failure_is_not_a_prediction():
    with pytest.raises(ModelUnavailable,match='explicit_failure'):
        bounded_call(failed,(),5)

def test_cold_start_has_separate_budget_from_prediction():
    import threading
    from src.ml.inference_process import ModelProcess
    class Connection:
        def __init__(self):
            self.budgets=[]
            self.responses=iter([{'ready':True},{'output':{'valid':1}}, {'output':{'valid':1}}])
        def poll(self,timeout):
            self.budgets.append(timeout)
            return True
        def recv(self): return next(self.responses)
        def send(self,facts): pass
    process=object.__new__(ModelProcess)
    process.connection=Connection()
    process.lock=threading.Lock()
    process.ready=False
    assert process.predict({},.1)=={'valid':1}
    assert process.predict({},.1)=={'valid':1}
    assert process.connection.budgets==[90,.1,.1]

def test_warm_python_process_is_reused_and_returns_probabilities():
    from src.ml.inference_process import infer,close_models,_models
    path=Path('artifacts/python/pipeline.joblib').resolve()
    if not path.exists(): pytest.skip('Train the Python artifact first')
    try:
        first=infer('python',path,{'product_category':'mobile'},timeout=30)
        process=_models[('python',str(path))].process
        second=infer('python',path,{'product_category':'mobile'},timeout=30)
        assert _models[('python',str(path))].process is process
        assert process.is_alive()
        assert first==second
        assert sum(second.model_dump().values())==pytest.approx(1)
    finally: close_models()
