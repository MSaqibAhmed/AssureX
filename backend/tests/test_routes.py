from fastapi.testclient import TestClient
from src.main import app
from src.api.routes import ROUTES

def test_exact_requested_surface():
    actual = {(path,method.upper()) for path,operations in app.openapi()['paths'].items() for method in operations}
    assert actual == {('/api/v1'+p,m) for p,ms in ROUTES.items() for m in ms}

def test_unauthenticated_requests_rejected():
    client=TestClient(app)
    response = client.get('/api/v1/dashboard')
    assert response.status_code == 401
    assert set(response.json()) == {'code','message','field_errors'}

def test_no_public_evidence_mount():
    assert not any(getattr(r,'path','').startswith('/private') for r in app.routes)
