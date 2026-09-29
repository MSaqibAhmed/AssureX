from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from src.repositories.mongo import claim_for,change_claim
from src.security.auth import role

@pytest.mark.asyncio
async def test_cross_owner_is_not_found():
    db=SimpleNamespace(claims=SimpleNamespace(find_one=AsyncMock(return_value=None)))
    with pytest.raises(HTTPException) as error:
        await claim_for(db,'secret',{'_id':'alice','role':'customer'})
    assert error.value.status_code==404
    db.claims.find_one.assert_awaited_once_with({'_id':'secret','claimant_id':'alice'})

@pytest.mark.parametrize('user,scope',[
    ({'_id':'r','role':'reviewer'},{'assigned_reviewer_id':'r'}),
    ({'_id':'s','role':'service','center_id':'center'},{'center_id':'center'}),
])
@pytest.mark.asyncio
async def test_staff_scopes(user,scope):
    db=SimpleNamespace(claims=SimpleNamespace(find_one=AsyncMock(return_value={'_id':'c'})))
    await claim_for(db,'c',user)
    db.claims.find_one.assert_awaited_once_with({'_id':'c',**scope})

@pytest.mark.asyncio
async def test_stale_update_is_409_with_all_three_filters():
    update=AsyncMock(return_value=SimpleNamespace(modified_count=0))
    db=SimpleNamespace(claims=SimpleNamespace(update_one=update))
    with pytest.raises(HTTPException) as error:
        await change_claim(db,{'_id':'c'},3,'Manual Review',{'status':'Approved'})
    assert error.value.status_code==409
    assert update.call_args.args[0]=={'_id':'c','version':3,'status':'Manual Review'}

def test_role_escalation_denied():
    with pytest.raises(HTTPException) as error: role({'role':'customer'},'admin')
    assert error.value.status_code==403
