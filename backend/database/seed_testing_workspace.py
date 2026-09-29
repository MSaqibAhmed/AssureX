"""Add an isolated QA account suite to the explicitly local development database.

Only test identities and assignment of newly created test claims are provisioned
directly. Products, evidence, OCR corrections, evaluations and reviews use real APIs.
"""
import json
import secrets
import time
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4
import httpx
from pymongo import MongoClient
from reportlab.pdfgen.canvas import Canvas
from src.security.auth import hasher


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / 'private' / ('testing-kit-' + time.strftime('%Y%m%d-%H%M%S'))
    output.mkdir(parents=True, exist_ok=False)
    password = secrets.token_urlsafe(15)
    tag = uuid4().hex[:6]
    mongo = MongoClient('mongodb://127.0.0.1:27018/?replicaSet=rs0&directConnection=true', serverSelectionTimeoutMS=3000)
    db = mongo['assurex_local_dev']
    clients = {}
    users = {}
    cases = []
    try:
        assert db.service_centers.find_one({'_id':'central','active':True}), 'Start local development first'
        for role in ('admin','customer','reviewer','service'):
            identity = {'_id':str(uuid4()), 'name':f'QA {role.title()} {tag}',
                'email_normalized':f'qa.{role}.{tag}@example.com', 'role':role,
                'active':True, 'center_id':'central' if role=='service' else None,
                'password_hash':hasher.hash(password)}
            db.users.insert_one(identity)
            users[role] = {'id':identity['_id'],'email':identity['email_normalized']}
            client = httpx.Client(base_url='http://127.0.0.1:8000/api/v1',timeout=45)
            clients[role] = client
            response = client.post('/auth/login',json={'email':identity['email_normalized'],'password':password})
            response.raise_for_status()
            client.headers['X-CSRF-Token'] = response.json()['data']['csrf_token']

        def call(role, method, path, **kwargs):
            response = clients[role].request(method,path,**kwargs)
            if response.status_code >= 400:
                raise RuntimeError(f'{method} {path}: {response.status_code} {response.text}')
            return response.json()['data']

        def wait(jid):
            deadline = time.monotonic()+180
            while time.monotonic()<deadline:
                job = call('customer','GET','/jobs/'+jid)
                if job['status']=='completed': return
                if job['status']=='failed': raise RuntimeError(f'Job failed: {jid}')
                time.sleep(.5)
            raise RuntimeError(f'Job timeout: {jid}')

        def save_manifest():
            # Credentials are local-only and stored under the already ignored private directory.
            (output/'accounts.json').write_text(json.dumps({'url':'http://127.0.0.1:5173','password':password,'users':users},indent=2),encoding='utf-8')
            (output/'scenarios.json').write_text(json.dumps(cases,indent=2),encoding='utf-8')
        save_manifest()
        specs = [
            ('01-draft-upload','mobile',False,None,30,False),
            ('02-warranty-required','electronics',False,None,45,True),
            ('03-ready-for-review','mobile',True,None,30,False),
            ('04-approved','electronics',True,'approve',60,False),
            ('05-expired-rejected','appliances',True,'reject',900,False),
            ('06-information-requested','mobile',True,'request_info',40,False),
            ('07-closed','electronics',True,'close',25,False),
            ('08-near-expiry-draft','mobile',False,None,350,False),
        ]
        today = date.today()
        for index,(label,category,evaluate,action,age,no_warranty) in enumerate(specs,1):
            purchase = today-timedelta(days=age)
            serial = f'QA{tag.upper()}{index:03d}'
            invoice = f'INV{tag.upper()}{index:03d}'
            product = call('customer','POST','/products',json={'serial':serial,'brand':'QA Test Brand',
                'model':label,'category':category,'purchase_date':purchase.isoformat(),'amount':'899.00'})
            if not no_warranty:
                policy = db.policy_versions.find_one({'_id':category+'-1.0'})
                assert policy
                from dateutil.relativedelta import relativedelta
                expiry = purchase+relativedelta(months=policy['policy']['coverage_months'])-timedelta(days=1)
                call('customer','PATCH',f'/products/{product["id"]}/warranty',json={'provider':'Synthetic QA Warranty',
                    'start_date':purchase.isoformat(),'expiry_date':expiry.isoformat(),'policy_version_id':policy['_id']})
            facts = {'fault_date':(today-timedelta(days=1)).isoformat(),'fault_category':'display',
                'description':f'SYNTHETIC QA CASE {label}: device fault for local testing only.',
                'damage_type':'none','serial':serial,'invoice_number':invoice}
            claim = call('customer','POST','/claims',json={'product_id':product['id'],'facts':facts})
            cid = claim['id']
            # Fixture-specific assignment only: never change global routing or existing records.
            db.claims.update_one({'_id':cid,'claimant_id':users['customer']['id'],'status':'Draft','version':1},
                {'$set':{'assigned_reviewer_id':users['reviewer']['id']}})
            case = {'scenario':label,'claim_id':cid,'public_claim_id':claim['public_claim_id'],
                'product_id':product['id'],'serial':serial,'invoice':invoice,'purchase_date':purchase.isoformat(),
                'customer_url':'http://127.0.0.1:5173/claims/'+cid,'reviewer_url':'http://127.0.0.1:5173/review/'+cid}
            cases.append(case)
            case_dir = output/label
            case_dir.mkdir()
            for kind in ('receipt','serial_photo'):
                file = case_dir/(kind+'.pdf')
                canvas = Canvas(str(file))
                lines = ['SYNTHETIC QA EVIDENCE - NOT A REAL PURCHASE',f'Purchase date: {purchase.isoformat()}',
                    f'Invoice: {invoice}','Product: Device',f'Model: {label}',f'Serial: {serial}',
                    'Retailer: Synthetic QA Store','Amount: 899.00','Warranty: 12 months']
                for row,line in enumerate(lines): canvas.drawString(40,800-row*28,line)
                canvas.save()
                if evaluate:
                    current = call('customer','GET','/claims/'+cid)
                    with file.open('rb') as evidence:
                        uploaded = call('customer','POST',f'/claims/{cid}/documents',
                            data={'document_type':kind,'version':str(current['version']),'status':current['status']},
                            files={'file':(file.name,evidence,'application/pdf')})
                    wait(uploaded['job_id'])
                    ocr = call('customer','GET',f'/documents/{uploaded["document_id"]}/ocr')
                    for field in ocr['fields']:
                        expected = {'purchase_date':purchase.isoformat(),'serial':serial,'invoice_number':invoice}.get(field['field'])
                        if expected:
                            call('customer','PATCH',f'/ocr-fields/{field["id"]}',json={'normalized_value':expected})
            case['evidence_folder'] = str(case_dir)
            call('customer','POST',f'/claims/{cid}/comments',json={'message':f'QA scenario: {label}. Synthetic data only.','visibility':'customer'})
            if evaluate:
                current = call('customer','GET','/claims/'+cid)
                job = call('customer','POST',f'/claims/{cid}/submit',json={'version':current['version'],'status':current['status']},headers={'Idempotency-Key':str(uuid4())})
                wait(job['job_id'])
                current = call('customer','GET','/claims/'+cid)
                evaluation = next(e for e in call('customer','GET',f'/claims/{cid}/evaluations') if e['id']==current['latest_evaluation_id'])
                case.update(recommendation=evaluation['recommendation'],comparison=evaluation['comparison']['status'],model_errors=evaluation['model_errors'])
                if action:
                    decision = 'approve' if action=='close' else action
                    reason = {'approve':'QA reviewer approved this synthetic claim after checking evidence.',
                        'reject':'QA reviewer rejected this synthetic expired-coverage claim.',
                        'request_info':'Please clarify the fault description and confirm the serial number, then resubmit.'}[decision]
                    call('reviewer','POST',f'/claims/{cid}/reviews',json={'version':current['version'],'status':current['status'],
                        'evaluation_id':current['latest_evaluation_id'],'action':decision,'reason':reason})
                    if action=='close':
                        current=call('customer','GET','/claims/'+cid)
                        call('admin','PATCH','/claims/'+cid,json={'version':current['version'],'status':current['status'],'target_status':'Closed'})
            case['status']=call('customer','GET','/claims/'+cid)['status']
            save_manifest()
            print(label+': '+case['status'],flush=True)
        target=cases[0]
        call('service','POST',f'/products/{target["product_id"]}/repairs',json={'claim_id':target['claim_id'],
            'date':today.isoformat(),'authorized':True,'notes':'Synthetic diagnostic inspection; no customer charge.'})
        call('service','POST',f'/products/{target["product_id"]}/replacements',json={'claim_id':target['claim_id'],
            'date':today.isoformat(),'authorized':True,'notes':'Synthetic historical component replacement.',
            'old_serial':'OLD'+target['serial'],'new_serial':target['serial']})
        call('service','POST',f'/claims/{target["claim_id"]}/comments',json={'message':'Internal QA service diagnostic note. Must not be visible to customer.','visibility':'staff'})
        print('TESTING_KIT='+str(output),flush=True)
        print('ACCOUNTS='+json.dumps(users),flush=True)
        print('LOCAL_TEST_PASSWORD='+password,flush=True)
    finally:
        for client in clients.values(): client.close()
        mongo.close()

if __name__=='__main__': main()
