from fastapi import APIRouter,Depends,HTTPException,Request,Response
from pymongo.errors import DuplicateKeyError
from argon2.exceptions import VerificationError
from src.schemas.requests import Login,Register
from src.security.auth import current_user,hasher,login_session,COOKIE
from src.repositories.mongo import uid
from src.api.common import envelope

router=APIRouter(tags=['auth'])

@router.post('/auth/register',status_code=201)
async def register(body:Register,request:Request,response:Response):
    user={'_id':uid(),'name':body.name,'email_normalized':str(body.email).casefold(),
          'password_hash':hasher.hash(body.password),'role':'customer','active':True,'center_id':None}
    try: await request.app.state.db.users.insert_one(user)
    except DuplicateKeyError: raise HTTPException(409,'Account already exists')
    csrf=await login_session(request,response,user)
    return envelope(request,{'user':user,'csrf_token':csrf})

@router.post('/auth/login')
async def login(body:Login,request:Request,response:Response):
    user=await request.app.state.db.users.find_one({'email_normalized':str(body.email).casefold(),'active':True})
    if not user: raise HTTPException(401,'Invalid credentials')
    try: hasher.verify(user['password_hash'],body.password)
    except VerificationError: raise HTTPException(401,'Invalid credentials')
    csrf=await login_session(request,response,user)
    return envelope(request,{'user':user,'csrf_token':csrf})

@router.post('/auth/logout')
async def logout(request:Request,response:Response,user=Depends(current_user)):
    await request.app.state.db.sessions.delete_one({'_id':request.state.session['_id']})
    response.delete_cookie(COOKIE,path='/api/v1')
    return envelope(request,{'signed_out':True})

@router.get('/me')
async def me(request:Request,user=Depends(current_user)):
    return envelope(request,{'user':user,'csrf_token':request.state.session['csrf']})
