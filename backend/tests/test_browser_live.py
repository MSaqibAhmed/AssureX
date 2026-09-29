"""Browser acceptance against the existing disposable real-service runner."""
import os, secrets, shutil, subprocess, sys
from datetime import date,timedelta
from pathlib import Path
import pytest
from reportlab.pdfgen.canvas import Canvas

def test_integrated_browser(tmp_path):
    if os.environ.get('FULL_TESTS')!='1': pytest.skip('Run database.run_local_tests --full')
    assert os.environ['MONGO_DATABASE'].startswith('assurex_test_')
    project=Path.cwd().parent/'frontend'
    env=dict(os.environ,DEMO_PASSWORD=secrets.token_urlsafe(24),VITE_API_BASE_URL=os.environ['E2E_BASE_URL']+'/api/v1',ASSUREX_TEST_URL='http://127.0.0.1:5174',E2E_PREVIEW='1')
    today=date.today()
    env.update(TEST_PURCHASE_DATE=(today-timedelta(days=30)).isoformat(),TEST_FAULT_DATE=(today-timedelta(days=1)).isoformat(),TEST_EXPIRY_DATE=(today+timedelta(days=335)).isoformat())
    receipt=tmp_path/'receipt.pdf'; canvas=Canvas(str(receipt))
    for i,line in enumerate([f'Purchase date: {env["TEST_PURCHASE_DATE"]}','Invoice: BROWSERINV','Product: Phone','Model: M1','Serial: BROWSER123','Retailer: Test Store','Amount: 899.00','Warranty: 12 months']): canvas.drawString(40,800-i*30,line)
    canvas.save(); env['TEST_RECEIPT']=str(receipt)
    subprocess.run([sys.executable,'-m','database.seed_demo'],env=env,check=True)
    processes=[]; logs=[]; stop=tmp_path/'stop-worker'; worker=None
    reports=project/'reports'; reports.mkdir(exist_ok=True)
    try:
        for module,args in [('src.jobs.dispatcher',[]),('tests.worker_loop',[str(stop)])]:
            log=(reports/(module.replace('.','-')+'.log')).open('w'); logs.append(log)
            process=subprocess.Popen([sys.executable,'-m',module,*args],env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)); processes.append(process)
            if module=='tests.worker_loop': worker=process
        node=shutil.which('node'); assert node
        with (reports/'integration-build.log').open('w',encoding='utf-8') as log:
            subprocess.run([node,'node_modules/vite/bin/vite.js','build','--outDir','tmp/integration-dist'],cwd=project,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
        with (reports/'playwright-run.log').open('w',encoding='utf-8') as log:
            result=subprocess.run([node,'node_modules/@playwright/test/cli.js','test'],cwd=project,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=360)
        print((reports/'playwright-run.log').read_text(encoding='utf-8').encode('ascii','backslashreplace').decode())
        assert result.returncode==0,'See reports/playwright-run.log and test-results'
    finally:
        stop.touch()
        if worker:
            try: worker.wait(timeout=55)
            except subprocess.TimeoutExpired: worker.terminate()
        for process in processes:
            if process.poll() is None: process.terminate()
            process.wait(timeout=10)
        for log in logs: log.close()
