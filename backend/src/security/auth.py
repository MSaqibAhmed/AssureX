import hashlib,hmac,secrets
from datetime import timedelta
from fastapi import Request, HTTPException
from argon2 import PasswordHasher
from src.repositories.mongo import now

hasher=PasswordHasher()
COOKIE='assurex_session'

def digest(value): return hashlib.sha256(value.encode()).hexdigest()

async def current_user(request:Request):
    token=request.cookies.get(COOKIE)
    if not token: raise HTTPException(401,'Sign in required')
    session=await request.app.state.db.sessions.find_one({'_id':digest(token),'expires_at':{'$gt':now()}})
    if not session: raise HTTPException(401,'Session expired')
    user=await request.app.state.db.users.find_one({'_id':session['user_id'],'active':True})
    if not user: raise HTTPException(401,'Session expired')
    if request.method not in ('GET','HEAD','OPTIONS'):
        if not hmac.compare_digest(request.headers.get('X-CSRF-Token',''),session['csrf']):
            raise HTTPException(403,'CSRF token required')
    request.state.session=session
    return user

def role(user,*roles):
    if user['role'] not in roles: raise HTTPException(403,'Role does not permit this action')

async def login_session(request,response,user):
    token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(32)
    await request.app.state.db.sessions.insert_one({'_id':digest(token),'user_id':user['_id'],'csrf':csrf,'expires_at':now()+timedelta(hours=12)})
    response.set_cookie(COOKIE,token,httponly=True,secure=request.app.state.settings.cookie_secure,samesite='strict',max_age=43200,path='/api/v1')
    return csrf
