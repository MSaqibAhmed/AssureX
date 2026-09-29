from datetime import date
import json
import pytest
from src.engines.rules import Policy,expiry,warranty_status,run_rules
from src.engines.contradiction import detect
from src.engines.duplicate import detect as duplicates

@pytest.mark.parametrize('start,months,end', [('2024-02-29',12,'2025-02-27'),('2026-01-31',1,'2026-02-27'),('2026-01-01',12,'2026-12-31')])
def test_inclusive_month_end(start,months,end):
    assert expiry(date.fromisoformat(start),months).isoformat()==end

def test_expiry_boundaries_and_window():
    end=date(2026,10,1)
    assert warranty_status(end,date(2026,10,2),30)=='expired'
    assert warranty_status(end,end,0)=='near-expiry'
    assert warranty_status(end,date(2026,9,1),29)=='active'
    assert warranty_status(end,date(2026,9,1),30)=='near-expiry'

def test_unknown_serial_is_not_verified_failure():
    policy=Policy.model_validate_json(open('policies/mobile.json').read())
    result=next(r for r in run_rules({},policy) if r.rule_id=='serial')
    assert result.status=='UNKNOWN' and not result.verified

def test_contradiction_and_duplicate_context():
    assert detect({'purchase_date':'2026-02-01','fault_date':'2026-01-01'})==['fault_date_before_purchase']
    current={'claim_id':'a','product_id':'p','hashes':['h'],'fault':'screen broken'}
    assert duplicates(current,[dict(current,claim_id='b')])[0]['kind']=='exact'
    assert not duplicates(current,[dict(current,claim_id='b',product_id='other')])
