import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from fastapi import HTTPException
from src.api import reviews
from tests.test_pdf_reports import report_data

@pytest.mark.asyncio
async def test_report_endpoint_checks_pinned_claim_and_review(monkeypatch):
    claim, revision, evaluation, review = report_data()
    evaluation['claim_revision_id'] = revision['_id']
    scoped = AsyncMock(return_value=claim)
    monkeypatch.setattr(reviews, 'claim_for', scoped)
    db = SimpleNamespace(evaluation_runs=SimpleNamespace(find_one=AsyncMock(return_value=evaluation)), claim_revisions=SimpleNamespace(find_one=AsyncMock(return_value=revision)), reviews=SimpleNamespace(find_one=AsyncMock(return_value=review)))
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db=db)))
    user = {'_id':'customer','role':'customer'}
    response = await reviews.report(claim['_id'], request, evaluation['_id'], review['_id'], user)
    assert response.body.startswith(b'%PDF')
    assert response.media_type == 'application/pdf'
    scoped.assert_awaited_once_with(db, claim['_id'], user)
    db.claim_revisions.find_one.assert_awaited_once_with({'_id':revision['_id'],'claim_id':claim['_id']})
    db.reviews.find_one.assert_awaited_once_with({'_id':review['_id'],'claim_id':claim['_id'],'evaluation_id':evaluation['_id']})
    db.reviews.find_one.return_value = None
    with pytest.raises(HTTPException) as exc:
        await reviews.report(claim['_id'], request, evaluation['_id'], 'unrelated-review', user)
    assert exc.value.status_code == 404
    db.claim_revisions.find_one.return_value = None
    with pytest.raises(HTTPException) as exc:
        await reviews.report(claim['_id'], request, evaluation['_id'], None, user)
    assert exc.value.status_code == 404

