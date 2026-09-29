from datetime import date
from src.engines.rules import Policy,run_rules

def policy(grace=0):
    return Policy(category='mobile',version='1',coverage_months=12,reporting_days=30,grace_days=grace,
        reminder_window=30,excluded_damage=['liquid'],required_documents=['receipt'],require_authorized_repairs=True)

def facts(day):
    return {'purchase_date':'2026-01-01','fault_date':day,'submission_date':day,'damage_type':'none',
        'serial_status':'match','document_types':['receipt'],'repair_count':0}

def get(f,p,key): return next(r for r in run_rules(f,p) if r.rule_id==key)

def test_expiry_plus_minus_one_and_grace():
    assert get(facts('2026-12-30'),policy(),'coverage').status=='PASS'
    assert get(facts('2026-12-31'),policy(),'coverage').status=='PASS'
    assert get(facts('2027-01-01'),policy(),'coverage').status=='FAIL'
    assert get(facts('2027-01-01'),policy(1),'coverage').status=='PASS'

def test_missing_receipt_unauthorized_repair_and_exclusion():
    f=facts('2026-10-01'); f.update(document_types=[],repair_count=1,authorization_status='unauthorized',damage_type='liquid')
    assert get(f,policy(),'document:receipt').status=='UNKNOWN'
    assert get(f,policy(),'repairs').status=='FAIL'
    assert get(f,policy(),'damage').status=='FAIL'

def test_reporting_deadline_boundary():
    f=facts('2026-10-01'); f['submission_date']='2026-10-31'
    assert get(f,policy(),'reporting').status=='PASS'
    f['submission_date']='2026-11-01'
    assert get(f,policy(),'reporting').status=='MANUAL_REVIEW'
