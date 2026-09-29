from types import SimpleNamespace
from unittest.mock import AsyncMock
from datetime import timedelta
import pytest
from fastapi import HTTPException
from src.security.auth import current_user,digest
from src.repositories.mongo import now

@pytest.mark.asyncio
async def test_session_needs_csrf_for_mutation():
    session={'_id':digest('token'),'user_id':'customer','csrf':'expected','expires_at':now()+timedelta(hours=1)}
    db=SimpleNamespace(sessions=SimpleNamespace(find_one=AsyncMock(return_value=session)),
        users=SimpleNamespace(find_one=AsyncMock(return_value={'_id':'customer','role':'customer','active':True})))
    request=SimpleNamespace(cookies={'assurex_session':'token'},headers={},method='POST',state=SimpleNamespace(),app=SimpleNamespace(state=SimpleNamespace(db=db)))
    with pytest.raises(HTTPException) as error: await current_user(request)
    assert error.value.status_code==403
    request.headers={'X-CSRF-Token':'expected'}
    assert (await current_user(request))['_id']=='customer'
