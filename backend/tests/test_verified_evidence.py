from src.engines.rules import Policy,run_rules
from src.engines.decision import decide

def test_file_presence_does_not_verify_receipt_contents():
    policy=Policy.model_validate_json(open('policies/mobile.json').read())
    facts={'purchase_date':'2026-01-01','fault_date':'2026-02-01','submission_date':'2026-02-02',
        'fault_category':'display','damage_type':'none','serial_status':'match',
        'document_types':['receipt','serial_photo'],'unverified_evidence_fields':['purchase_date']}
    rules=run_rules(facts,policy)
    prediction={'valid':.95,'invalid':.03,'manual_review':.02}
    result=decide(prediction,prediction,rules,mandatory_facts_verified=False)
    assert result.branch==1 and result.recommendation=='Manual Review Required'
