from src.repositories.mongo import public

def envelope(request,data,version=1):
    return {'data':public(data),'request_id':request.state.request_id,'version':version}
