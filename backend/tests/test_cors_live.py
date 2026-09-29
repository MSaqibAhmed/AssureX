import os
import httpx
import pytest

def test_credentialed_cors_is_allowlisted():
    base=os.environ.get('E2E_BASE_URL')
    if not base: pytest.skip('Use the disposable API runner')
    headers={'Origin':'http://127.0.0.1:5174','Access-Control-Request-Method':'POST',
        'Access-Control-Request-Headers':'content-type,x-csrf-token,idempotency-key'}
    with httpx.Client(base_url=base) as client:
        preflight=client.options('/api/v1/claims',headers=headers)
        assert preflight.status_code==200
        assert preflight.headers['access-control-allow-origin']==headers['Origin']
        assert preflight.headers['access-control-allow-credentials']=='true'
        denied=client.options('/api/v1/claims',headers=dict(headers,Origin='https://untrusted.invalid'))
        assert denied.status_code==400
        assert 'access-control-allow-origin' not in denied.headers
        unauthorized=client.get('/api/v1/me',headers={'Origin':headers['Origin']})
        assert unauthorized.status_code==401
        assert unauthorized.headers['access-control-allow-origin']==headers['Origin']
        cross_site=client.post('/api/v1/auth/login',headers={'Sec-Fetch-Site':'cross-site'},json={})
        assert cross_site.status_code==403
