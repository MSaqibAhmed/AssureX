from uuid import uuid4
from contextlib import asynccontextmanager
from pymongo import AsyncMongoClient
from src.config import Settings,BrowserSettings
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import router

@asynccontextmanager
async def lifespan(app):
    settings=Settings()
    client=AsyncMongoClient(settings.mongo_uri,serverSelectionTimeoutMS=5000,tz_aware=True)
    app.state.settings=settings
    app.state.db=client[settings.mongo_database]
    yield
    await client.close()

app = FastAPI(title='AssureX Claim Engine', version='1.0.0',lifespan=lifespan)
app.include_router(router)
app.add_middleware(CORSMiddleware, allow_origins=BrowserSettings().cors_origins,
    allow_credentials=True, allow_methods=['GET','POST','PATCH','OPTIONS'],
    allow_headers=['Content-Type','X-CSRF-Token','Idempotency-Key'],
    expose_headers=['X-Request-ID','Content-Disposition'])

@app.middleware('http')
async def request_context(request: Request, call_next):
    request.state.request_id = str(uuid4())
    # Reject cross-site browser authentication/mutations before cookie creation or use.
    if request.method not in ('GET','HEAD','OPTIONS') and request.headers.get('sec-fetch-site')=='cross-site':
        return JSONResponse(status_code=403,content={'code':'forbidden','message':'Cross-site mutation denied','field_errors':{}})
    response = await call_next(request)
    response.headers['X-Request-ID'] = request.state.request_id
    return response

@app.exception_handler(HTTPException)
async def http_error(request, exc):
    codes = {401:'unauthenticated',403:'forbidden',404:'not_found',409:'conflict',413:'upload_too_large',422:'invalid_input',503:'unavailable'}
    return JSONResponse(status_code=exc.status_code,content={
        'code':codes.get(exc.status_code,'request_error'),
        'message':str(exc.detail), 'field_errors':{}})

@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    fields = {'.'.join(map(str,e['loc'])):e['msg'] for e in exc.errors()}
    return JSONResponse(status_code=422,content={'code':'invalid_input','message':'Invalid request','field_errors':fields})

@app.exception_handler(Exception)
async def internal_error(request, exc):
    return JSONResponse(status_code=500,content={'code':'internal_error','message':'Request could not be completed','field_errors':{}})
