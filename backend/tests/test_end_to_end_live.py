"""Real HTTP -> private upload -> RQ OCR -> both saved models -> Mongo commit."""
import hashlib,io,json,os,secrets,subprocess,sys,time
from datetime import date,timedelta
from pathlib import Path
from uuid import uuid4
import httpx,numpy as np,pytest
from pymongo import MongoClient
from reportlab.pdfgen.canvas import Canvas
from src.repositories.mongo import now
from src.security.auth import hasher
from tests.test_load_live import stats

def test_real_pipeline_roles_history_and_latency(tmp_path):
    if os.environ.get('FULL_TESTS')!='1': pytest.skip('Full local acceptance run required')
    assert os.environ['MONGO_DATABASE'].startswith('assurex_test_')
    mongo=MongoClient(os.environ['MONGO_URI'],tz_aware=True); db=mongo[os.environ['MONGO_DATABASE']]
    token=uuid4().hex; password=secrets.token_urlsafe(24)
    clients={}; processes=[]; logs=[]; worker=None
    stop=tmp_path/'stop-worker'
    results={'scope':'Sequential real HTTP upload-complete through OCR, automatic correction calls, submit, RQ inference and committed evaluation; summary drained between samples',
        'cold_ms':[],'warm_ms':[],'model_failures':0}
    def spawn(module,*args):
        log=(tmp_path/(module.replace('.','-')+str(len(logs))+'.log')).open('w')
        logs.append(log)
        process=subprocess.Popen([sys.executable,'-m',module,*args],stdout=log,stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        processes.append(process); return process
    def start_worker():
        stop.unlink(missing_ok=True)
        return spawn('tests.worker_loop',str(stop))
    def stop_worker(process):
        stop.touch(); process.wait(timeout=60)
    def call(who,method,path,expected=200,**kwargs):
        response=clients[who].request(method,'/api/v1'+path,**kwargs)
        assert response.status_code==expected,(method,path,response.status_code,response.text)
        return response.json()['data']
    def wait_job(jid,timeout=120):
        until=time.monotonic()+timeout
        while time.monotonic()<until:
            job=call('customer','GET','/jobs/'+jid)
            assert job['status']!='failed',job
            if job['status']=='completed': return job
            time.sleep(.1)
        raise AssertionError('Job timeout: '+jid)
    def wait_summary(cid):
        until=time.monotonic()+90
        while time.monotonic()<until:
            response=clients['reviewer'].get('/api/v1/claims/'+cid+'/summary')
            if response.status_code==200:
                summary=response.json()['data']
                assert summary['source'] in ('local_model','fallback')
                assert summary['input_hash'] and summary['prompt_version']
                return summary
            assert response.status_code==404,response.text
            time.sleep(.2)
        raise AssertionError('Summary did not finish')
    try:
        # Provision identities directly only in the runner's disposable database;
        # role changes are never permitted through customer registration.
        for role in ('customer','service','reviewer','admin'):
            uid=token+'-'+role; email=uid+'@example.com'
            db.users.insert_one({'_id':uid,'email_normalized':email,'password_hash':hasher.hash(password),
                'active':True,'role':role,'name':role,'center_id':token+'-center' if role=='service' else None})
            api=httpx.Client(base_url=os.environ['E2E_BASE_URL'],timeout=45)
            clients[role]=api
            result=call(role,'POST','/auth/login',json={'email':email,'password':password})
            api.headers['X-CSRF-Token']=result['csrf_token']
        db.service_centers.insert_one({'_id':token+'-center','name':'Test center','active':True})
        db.settings.update_one({'_id':'claim_routing'},{'$set':{'value':{'default':{
            'center_id':token+'-center','reviewer_id':token+'-reviewer'}}}},upsert=True)
        policy=json.loads(Path('policies/mobile.json').read_text()); policy['version']=token
        policy_id=call('admin','POST','/admin/policies',201,json=policy)['id']
        assert clients['customer'].post('/api/v1/admin/policies',json=policy).status_code==403
        assert clients['admin'].post('/api/v1/admin/policies',json=policy).status_code==409
        for family,relative in [('python','python/pipeline.joblib'),('gtm','gtm/model.keras')]:
            artifact=Path('artifacts')/relative; mid=token+'-'+family
            db.model_versions.insert_one({'_id':mid,'family':family,'version':token,
                'artifact_path':relative,'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'created_at':now()})
            call('admin','POST','/admin/model-activations',json={'model_version_id':mid,'reason':'Isolated acceptance run'})
        spawn('src.jobs.dispatcher'); worker=start_worker()
        last=None
        for i in range(8):
            cold=i<3
            if 0<i<3:
                stop_worker(worker); worker=start_worker()
            purchase=(date.today()-timedelta(days=30)).isoformat()
            serial='SERIAL'+str(i)+token[:6]; invoice='INV'+str(i)
            product=call('customer','POST','/products',201,json={'serial':serial,'brand':'Test','model':'M1',
                'category':'mobile','purchase_date':purchase,'amount':'899.00'})
            pid=product['id']
            call('customer','PATCH','/products/'+pid,json={'serial':serial,'brand':'Updated Test','model':'M1',
                'category':'mobile','purchase_date':purchase,'amount':'899.00'})
            assert call('customer','GET','/products/'+pid)['brand']=='Updated Test'
            warranty={'provider':'Test','start_date':purchase,'expiry_date':(date.today()+timedelta(days=335)).isoformat(),'policy_version_id':policy_id}
            assert call('customer','PATCH','/products/'+pid+'/warranty',json=warranty)['status']=='active'
            facts={'fault_date':(date.today()-timedelta(days=1)).isoformat(),'fault_category':'display',
                'description':'Screen fault','damage_type':'none','serial':serial,'invoice_number':invoice}
            claim=call('customer','POST','/claims',201,json={'product_id':pid,'facts':facts}); cid=claim['id']
            if i==0:
                call('service','POST','/products/'+pid+'/repairs',201,json={'claim_id':cid,'date':date.today().isoformat(),'authorized':True,'notes':'Diagnostic only'})
                call('service','POST','/products/'+pid+'/replacements',201,json={'claim_id':cid,'date':date.today().isoformat(),
                    'authorized':True,'notes':'Previous component replacement','old_serial':'OLD','new_serial':serial})
                call('service','POST','/claims/'+cid+'/comments',201,json={'message':'Internal note','visibility':'staff'})
                assert call('customer','GET','/claims/'+cid+'/comments')==[]
                call('customer','POST','/claims/'+cid+'/comments',201,json={'message':'Customer note','visibility':'customer'})
                assert len(call('reviewer','GET','/claims/'+cid+'/comments'))==2
                assert call('customer','GET','/claims/'+cid+'/assistance')['missing_documents']
            output=io.BytesIO(); canvas=Canvas(output)
            for n,line in enumerate([f'Purchase date: {purchase}',f'Invoice: {invoice}','Product: Phone','Model: M1',
                f'Serial: {serial}','Retailer: Test Store','Amount: 899.00','Warranty: 12 months']):
                canvas.drawString(40,800-n*30,line)
            canvas.save(); jobs=[]; documents=[]
            for version,kind in enumerate(('receipt','serial_photo'),start=1):
                uploaded=call('customer','POST','/claims/'+cid+'/documents',202,
                    data={'document_type':kind,'version':str(version),'status':'Draft'},
                    files={'file':('receipt.pdf',output.getvalue(),'application/pdf')})
                jobs.append(uploaded['job_id']); documents.append(uploaded['document_id'])
            started=time.perf_counter()  # Last upload response: all bytes persisted.
            for jid in jobs: wait_job(jid)
            fields=call('customer','GET','/documents/'+documents[0]+'/ocr')['fields']
            # Text-PDF extraction has no confidence score; explicitly confirm values.
            for field in fields:
                if field['field'] in ('purchase_date','serial','invoice_number'):
                    call('customer','PATCH','/ocr-fields/'+field['id'],json={'normalized_value':field['normalized_value']})
            claim=call('customer','GET','/claims/'+cid)
            expected={'version':claim['version'],'status':claim['status']}; key=uuid4().hex
            submitted=call('customer','POST','/claims/'+cid+'/submit',202,json=expected,headers={'Idempotency-Key':key})
            replay=call('customer','POST','/claims/'+cid+'/submit',202,json=expected,headers={'Idempotency-Key':key})
            assert replay==submitted
            wait_job(submitted['job_id'])
            elapsed=(time.perf_counter()-started)*1000
            evaluation=call('customer','GET','/claims/'+cid+'/evaluations')[0]
            assert not evaluation['model_errors'],evaluation['model_errors']
            assert evaluation['predictions']['python'] and evaluation['predictions']['gtm']
            results['cold_ms' if cold else 'warm_ms'].append(elapsed)
            wait_summary(cid)
            assert call('customer','GET','/claims/'+cid)['status']=='Manual Review'
            last=(cid,pid,evaluation,facts)
        cid,pid,evaluation,facts=last
        original=db.evaluation_runs.find_one({'_id':evaluation['id']})
        # Activate a new model record and policy without mutating historical output.
        replacement=dict(db.model_versions.find_one({'_id':token+'-python'}),_id=token+'-python-v2',version=token+'-2')
        db.model_versions.insert_one(replacement)
        call('admin','POST','/admin/model-activations',json={'model_version_id':replacement['_id'],'reason':'Test version pinning'})
        next_policy=dict(policy,version=token+'-2',reminder_window=14)
        next_policy_id=call('admin','POST','/admin/policies',201,json=next_policy)['id']
        call('customer','PATCH','/products/'+pid+'/warranty',json=dict(warranty,policy_version_id=next_policy_id))
        claim=call('reviewer','GET','/claims/'+cid)
        review_body={'version':claim['version'],'status':'Manual Review','evaluation_id':evaluation['id'],
            'action':'request_info','reason':'Please confirm the fault description'}
        review=call('reviewer','POST','/claims/'+cid+'/reviews',201,json=review_body)
        assert clients['reviewer'].post('/api/v1/claims/'+cid+'/reviews',json=review_body).status_code==409
        claim=call('customer','GET','/claims/'+cid)
        call('customer','PATCH','/claims/'+cid,json={'version':claim['version'],'status':claim['status'],'facts':dict(facts,description='Confirmed screen fault')})
        claim=call('customer','GET','/claims/'+cid)
        job=call('customer','POST','/claims/'+cid+'/submit',202,json={'version':claim['version'],'status':claim['status']},headers={'Idempotency-Key':uuid4().hex})
        wait_job(job['job_id']); wait_summary(cid)
        assert db.evaluation_runs.find_one({'_id':evaluation['id']})==original
        claim=call('reviewer','GET','/claims/'+cid)
        new_evaluation=db.evaluation_runs.find_one({'_id':claim['latest_evaluation_id']})
        assert new_evaluation['versions']['python']==replacement['_id']
        assert new_evaluation['versions']['policy']==next_policy_id
        approved=call('reviewer','POST','/claims/'+cid+'/reviews',201,json={'version':claim['version'],'status':claim['status'],
            'evaluation_id':claim['latest_evaluation_id'],'action':'approve','reason':'Evidence reviewed and confirmed'})
        pdf=clients['reviewer'].get('/api/v1/claims/'+cid+'/report',params={'evaluation_id':claim['latest_evaluation_id'],'review_id':approved['id']})
        assert pdf.status_code==200 and pdf.content.startswith(b'%PDF-')
        assert clients['reviewer'].get('/api/v1/claims/'+cid+'/report',params={'evaluation_id':'wrong'}).status_code==404
        claim=call('reviewer','GET','/claims/'+cid)
        call('reviewer','PATCH','/claims/'+cid,json={'version':claim['version'],'status':'Approved','target_status':'Closed'})
        reports=call('customer','GET','/reports?status=Closed')
        assert any(row['id']==cid for row in reports['items'])
        notices=call('customer','GET','/notifications')['items']; assert notices
        call('customer','PATCH','/notifications/'+notices[0]['id'],json={'read':True})
        assert clients['service'].patch('/api/v1/notifications/'+notices[0]['id'],json={'read':True}).status_code==404
        results['cold']=stats(results['cold_ms']); results['warm']=stats(results['warm_ms'])
        results['five_second_target_met']=results['warm']['max_ms']<=5000
        results['cold_target_met']=results['cold']['max_ms']<=5000
        Path('reports/end-to-end.json').write_text(json.dumps(results,indent=2))
    finally:
        if worker is not None and worker.poll() is None:
            try: stop_worker(worker)
            except subprocess.TimeoutExpired: worker.terminate(); worker.wait(timeout=10)
        for process in processes:
            if process.poll() is None: process.terminate(); process.wait(timeout=10)
        for api in clients.values(): api.close()
        for log in logs: log.close()
        mongo.close()
