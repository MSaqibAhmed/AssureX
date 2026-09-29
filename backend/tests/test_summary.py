from unittest.mock import patch
from src.ml.summary_model.summarize import summarize,bounded_summary
from src.ml.inference_process import ModelUnavailable
import os,json,time
from pathlib import Path
import pytest

def test_generation_failure_uses_factual_fallback():
    facts={'product_category':'mobile','serial_status':'unknown'}
    with patch('src.ml.summary_model.summarize.load',side_effect=RuntimeError('offline')):
        result=summarize(facts)
    assert result['source']=='fallback'
    assert result['quality_flags']==['generation_unavailable']
    assert 'serial_status: unknown' in result['text']
    assert 'Approved' not in result['text']

def test_timeout_uses_fallback_without_changing_facts():
    facts={'fault_category':'display'}
    with patch('src.ml.inference_process.bounded_call',side_effect=ModelUnavailable('timeout')):
        result=bounded_summary(facts,'unused',.1)
    assert result['source']=='fallback' and result['quality_flags']==['generation_timeout_or_failure']
    assert facts=={'fault_category':'display'}

def test_actual_local_summary_generates_or_rejects_grounding():
    if os.environ.get('FULL_TESTS')!='1': pytest.skip('Full local model test required')
    facts={'product_category':'mobile','fault_category':'display','purchase_date':'2026-01-01',
        'fault_date':'2026-02-01','serial_status':'match','repair_count':0}
    # Diagnostic cold-load budget, not the production 30-second deadline.
    # Production timeout/fallback is separately asserted above and in E2E.
    started=time.perf_counter()
    result=bounded_summary(facts,str(Path('artifacts/summary').resolve()),120)
    result['wall_elapsed_ms']=(time.perf_counter()-started)*1000
    result['test_budget_seconds']=120
    result['production_budget_seconds']=30
    result['within_production_budget']=result['wall_elapsed_ms']<=30000
    Path('reports/summary-real.json').write_text(json.dumps(result,indent=2))
    assert result['source'] in ('local_model','fallback')
    assert not set(result['quality_flags']) & {'generation_unavailable','generation_timeout_or_failure'},result
