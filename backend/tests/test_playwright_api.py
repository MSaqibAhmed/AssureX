"""Opt-in API E2E using Playwright; no frontend or browser installation needed."""
import os
import io
from PIL import Image
from uuid import uuid4
import pytest

def test_api_authentication_e2e():
    base=os.environ.get('E2E_BASE_URL')
    if not base: pytest.skip('Set E2E_BASE_URL to an isolated running backend')
    playwright=pytest.importorskip('playwright.sync_api')
    with playwright.sync_playwright() as p:
        context=p.request.new_context(base_url=base)
        try:
            response=context.get('/api/v1/me')
            assert response.status==401
            assert response.json()['code']=='unauthenticated'
            response=context.post('/api/v1/auth/register',data={'name':'Test','email':'x@example.test','password':'longtestpassword','role':'admin'})
            assert response.status==422
        finally: context.dispose()

def test_customer_session_csrf_and_record_isolation_e2e():
    base=os.environ.get('E2E_BASE_URL')
    if not base: pytest.skip('Set E2E_BASE_URL to an isolated running backend')
    playwright=pytest.importorskip('playwright.sync_api')
    with playwright.sync_playwright() as p:
        owner=p.request.new_context(base_url=base)
        other=p.request.new_context(base_url=base)
        try:
            for context in (owner,other):
                response=context.post('/api/v1/auth/register',data={'name':'Test Customer',
                    'email':uuid4().hex+'@example.com','password':'local-test-password-123'})
                assert response.status==201, response.text()
                assert 'password_hash' not in response.text()
                csrf=response.json()['data']['csrf_token']
                assert context.get('/api/v1/me').status==200
                assert context.post('/api/v1/auth/logout').status==403
                if context is owner: owner_headers={'X-CSRF-Token':csrf}
            product={'serial':'TEST-'+uuid4().hex,'brand':'Test','model':'Test M','category':'mobile',
                'purchase_date':'2026-01-01','amount':'100.00'}
            response=owner.post('/api/v1/products',data=product,headers=owner_headers)
            assert response.status==201, response.text()
            product_id=response.json()['data']['id']
            assert other.get('/api/v1/products/'+product_id).status==404
            response=owner.post('/api/v1/claims',data={'product_id':product_id,'facts':{'description':'Screen fault'}},headers=owner_headers)
            assert response.status==201, response.text()
            claim=response.json()['data']
            assert other.get('/api/v1/claims/'+claim['id']).status==404
            assert owner.get('/api/v1/claims/'+claim['id']+'/workflow').status==200
            assert other.get('/api/v1/claims/'+claim['id']+'/workflow').status==404
            assert owner.get('/api/v1/policies').status==200
            for path in ('users','models','audit','service-centers'):
                assert owner.get('/api/v1/admin/'+path).status==403
            assert owner.get('/api/v1/service-history').status==403
            updated=owner.patch('/api/v1/me',data={'name':'Updated Customer','phone':'123456'},headers=owner_headers)
            assert updated.status==200 and updated.json()['data']['name']=='Updated Customer'
            assert 'password_hash' not in updated.text()
            assert owner.patch('/api/v1/me',data={'name':'Escalation','role':'admin'},headers=owner_headers).status==422
            response=owner.patch('/api/v1/claims/'+claim['id'],data={'version':claim['version'],
                'status':'Draft','facts':{'description':'Corrected screen fault'}},headers=owner_headers)
            assert response.status==200, response.text()
            response=owner.patch('/api/v1/claims/'+claim['id'],data={'version':claim['version'],
                'status':'Draft','facts':{'description':'Stale update'}},headers=owner_headers)
            assert response.status==409
            buffer=io.BytesIO()
            Image.new('RGB',(40,40),'white').save(buffer,format='PNG')
            upload_url='/api/v1/claims/'+claim['id']+'/documents'
            multipart={'document_type':'receipt','version':'2','status':'Draft',
                'file':{'name':'../../receipt.png','mimeType':'image/png','buffer':buffer.getvalue()}}
            response=owner.post(upload_url,multipart=multipart,headers=owner_headers)
            assert response.status==202, response.text()
            document_id=response.json()['data']['document_id']
            assert response.json()['version']==3
            listed=owner.get(upload_url)
            assert listed.status==200
            assert [row['id'] for row in listed.json()['data']]==[document_id]
            assert 'object_key' not in listed.text()
            library=owner.get('/api/v1/documents?product_id='+product_id)
            assert library.status==200 and library.json()['data']['total']==1
            assert 'object_key' not in library.text()
            assert other.get('/api/v1/documents').json()['data']['total']==0
            assert other.get('/api/v1/documents?product_id='+product_id).status==404
            assert other.get(upload_url).status==404
            # The same stale version must not create a second document or leave a file.
            assert owner.post(upload_url,multipart=multipart,headers=owner_headers).status==409
            malicious=dict(multipart,version='3',file={'name':'fake.png','mimeType':'image/png','buffer':b'<script>bad</script>'})
            assert owner.post(upload_url,multipart=malicious,headers=owner_headers).status==422
            ocr_url='/api/v1/documents/'+document_id+'/ocr'
            response=owner.get(ocr_url)
            assert response.status==200
            assert 'object_key' not in response.text()
            download_url=response.json()['data']['download_url']
            downloaded=owner.get(download_url)
            assert downloaded.status==200 and downloaded.body()==buffer.getvalue()
            assert downloaded.headers['cache-control']=='private, no-store'
            assert other.get(ocr_url).status==404
            assert owner.get('/api/v1/documents/'+document_id+'/preview').status==200
            assert other.get('/api/v1/documents/'+document_id+'/preview').status==404
            assert other.get(download_url).status==404
            assert owner.get(download_url.replace('signature=','signature=invalid')).status==403
            assert owner.get(ocr_url+'?download=true&expires=1&signature=expired').status==403
            assert owner.post('/api/v1/auth/logout',headers=owner_headers).status==200
            assert owner.get('/api/v1/me').status==401
        finally:
            owner.dispose(); other.dispose()
