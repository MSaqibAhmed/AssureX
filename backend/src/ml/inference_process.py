"""Killable model inference; a timed-out model cannot retain an RQ worker thread."""
import multiprocessing
import atexit
import threading

class ModelUnavailable(RuntimeError):
    pass

def _predict(connection,family,path,facts):
    try:
        if family=='python':
            from src.ml.python_model.predict import PythonModel
            output=PythonModel(path).predict(facts)
        elif family=='gtm':
            from pathlib import Path
            from src.ml.gtm_adapter.predict import GTMModel
            from src.ml.card import render_card
            output=GTMModel(path,Path(path).parent/'labels.json').predict(render_card(facts))
        else:
            raise ValueError('Unknown family')
        connection.send({'output':output.model_dump()})
    except Exception:
        connection.send({'error':'model_unavailable_or_invalid_output'})
    finally:
        connection.close()

def bounded_call(target,args,timeout):
    context=multiprocessing.get_context('spawn')
    receiver,sender=context.Pipe(duplex=False)
    process=context.Process(target=target,args=(sender,*args),daemon=True)
    process.start(); sender.close()
    try:
        if not receiver.poll(timeout):
            raise ModelUnavailable('model_timeout')
        try: result=receiver.recv()
        except EOFError: raise ModelUnavailable('model_process_failed')
        if result.get('error'): raise ModelUnavailable(result['error'])
        return result['output']
    finally:
        receiver.close()
        if process.is_alive(): process.terminate()
        process.join(timeout=5)
        if process.is_alive(): process.kill(); process.join()

def _model_server(connection,family,path):
    try:
        if family=='python':
            from src.ml.python_model.predict import PythonModel
            model=PythonModel(path)
            predict=model.predict
        elif family=='gtm':
            from pathlib import Path
            from src.ml.gtm_adapter.predict import GTMModel
            from src.ml.card import render_card
            model=GTMModel(path,Path(path).parent/'labels.json')
            predict=lambda facts:model.predict(render_card(facts))
        else: raise ValueError('Unknown model family')
        connection.send({'ready':True})
        while True:
            facts=connection.recv()
            if facts is None: break
            try: connection.send({'output':predict(facts).model_dump()})
            except Exception: connection.send({'error':'model_unavailable_or_invalid_output'})
    except (EOFError,BrokenPipeError):
        pass
    except Exception:
        try: connection.send({'error':'model_load_failed'})
        except (EOFError,BrokenPipeError): pass
    finally: connection.close()

class ModelProcess:
    def __init__(self,family,path):
        context=multiprocessing.get_context('spawn')
        self.connection,child=context.Pipe()
        self.process=context.Process(target=_model_server,args=(child,family,str(path)),daemon=True)
        self.lock=threading.Lock()
        self.ready=False
        self.process.start(); child.close()

    def close(self):
        self.connection.close()
        if self.process.is_alive(): self.process.terminate()
        self.process.join(timeout=5)
        if self.process.is_alive(): self.process.kill(); self.process.join()

    def predict(self,facts,timeout):
        with self.lock:
            try:
                # Cold imports/model loading have a separate bounded budget. The
                # prediction deadline still applies to every actual inference.
                if not self.ready:
                    if not self.connection.poll(90): raise ModelUnavailable('model_startup_timeout')
                    message=self.connection.recv()
                    if not message.get('ready'): raise ModelUnavailable(message.get('error','model_load_failed'))
                    self.ready=True
                self.connection.send(facts)
                if not self.connection.poll(timeout): raise ModelUnavailable('model_timeout')
                result=self.connection.recv()
                if result.get('error'): raise ModelUnavailable(result['error'])
                return result['output']
            except (EOFError,BrokenPipeError,OSError) as exc:
                raise ModelUnavailable('model_process_failed') from exc

_models={}
_pool_lock=threading.Lock()

def close_models():
    with _pool_lock:
        for process in _models.values(): process.close()
        _models.clear()

atexit.register(close_models)

def infer(family,path,facts,timeout=20):
    from src.schemas.evaluation import Probabilities
    key=(family,str(path))
    with _pool_lock:
        if key not in _models:
            for old_key in list(_models):
                if old_key[0]==family: _models.pop(old_key).close()
            _models[key]=ModelProcess(family,path)
        process=_models[key]
    try:
        return Probabilities.model_validate(process.predict(facts,timeout))
    except Exception:
        with _pool_lock:
            if _models.get(key) is process: _models.pop(key).close()
        raise
