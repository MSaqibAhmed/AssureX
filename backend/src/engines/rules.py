from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from pydantic import Field
from src.schemas.evaluation import StrictModel, RuleResult

class Policy(StrictModel):
    category: str
    version: str
    coverage_months: int = Field(ge=1,le=120)
    reporting_days: int = Field(ge=0,le=365)
    grace_days: int = Field(ge=0,le=90)
    reminder_window: int = Field(ge=0,le=365)
    excluded_damage: list[str]
    required_documents: list[str]
    require_authorized_repairs: bool
    covered_fault_categories: list[str] = Field(default_factory=list)

def expiry(purchase: date, months: int) -> date:
    return purchase + relativedelta(months=months) - timedelta(days=1)

def warranty_status(end: date, today: date, window: int) -> str:
    return 'expired' if end < today else 'near-expiry' if end <= today + timedelta(days=window) else 'active'

def run_rules(facts: dict, policy: Policy) -> list[RuleResult]:
    results = []
    def add(key,status,explanation,values, severity='hard_fail',verified=True):
        results.append(RuleResult(rule_id=key,status=status,severity=severity,verified=verified,
            facts_used=values,evidence_ids=facts.get('evidence_ids',[]),explanation=explanation))
    purchase, fault, submitted = (facts.get(k) for k in ('purchase_date','fault_date','submission_date'))
    if purchase and fault:
        start, issue = date.fromisoformat(purchase), date.fromisoformat(fault)
        end = expiry(start,policy.coverage_months) + timedelta(days=policy.grace_days)
        add('coverage','PASS' if start <= issue <= end else 'FAIL','Coverage window checked',{'start':purchase,'end':end.isoformat(),'fault':fault})
    else:
        add('coverage','UNKNOWN','Coverage dates are missing',{},'critical',False)
    if fault and submitted:
        delay = (date.fromisoformat(submitted)-date.fromisoformat(fault)).days
        add('reporting','PASS' if 0 <= delay <= policy.reporting_days else 'MANUAL_REVIEW','Reporting deadline checked',{'delay_days':delay,'allowed_days':policy.reporting_days})
    else:
        add('reporting','UNKNOWN','Reporting dates are missing',{},'critical',False)
    damage = facts.get('damage_type')
    fault_category=facts.get('fault_category')
    if policy.covered_fault_categories:
        add('covered_fault','UNKNOWN' if not fault_category else 'PASS' if fault_category in policy.covered_fault_categories else 'MANUAL_REVIEW',
            'Fault category compared with policy',{'fault_category':fault_category},'critical',bool(fault_category))
    add('damage','UNKNOWN' if damage is None else 'FAIL' if damage in policy.excluded_damage else 'PASS',
        'Damage exclusion checked',{'damage_type':damage},'critical' if damage is None else 'hard_fail',damage is not None)
    serial = facts.get('serial_status','unknown')
    add('serial','UNKNOWN' if serial == 'unknown' else 'FAIL' if serial == 'mismatch' else 'PASS',
        'Serial verification checked',{'serial_status':serial},'critical' if serial == 'unknown' else 'hard_fail',serial != 'unknown')
    authorization = facts.get('authorization_status','unknown')
    if facts.get('repair_count',0) and policy.require_authorized_repairs:
        add('repairs','PASS' if authorization == 'authorized' else 'FAIL' if authorization == 'unauthorized' else 'UNKNOWN',
            'Repair authorization checked',{'authorization_status':authorization},'critical' if authorization == 'unknown' else 'hard_fail',authorization != 'unknown')
    present = set(facts.get('document_types',[]))
    for required in policy.required_documents:
        add('document:'+required,'PASS' if required in present else 'UNKNOWN','Required evidence checked',
            {'type':required},'critical',required in present)
    # Existence of a file is not verification of its contents. Production snapshots
    # include this field; historical/unit fixtures may omit it.
    for field in facts.get('unverified_evidence_fields',[]):
        add('evidence:'+field,'UNKNOWN','Evidence field has not been extracted or confirmed',{'field':field},'critical',False)
    if facts.get('contradiction_count',0):
        add('contradiction','MANUAL_REVIEW','Contradictory dates require verification',{},'critical')
    if facts.get('duplicate_signal') in (True,'true','yes'):
        add('duplicate','MANUAL_REVIEW','Duplicate signal is not proof of fraud',{},'critical')
    for media in facts.get('fault_media',[]):
        add('fault_media:'+media['document_id'],'MANUAL_REVIEW',
            'Fault video requires human review' if media['type']=='fault_video' else 'Fault image requires specialist review; AI fault detection is not configured',
            {'document_id':media['document_id'],'type':media['type']},'critical',False)
    return results
