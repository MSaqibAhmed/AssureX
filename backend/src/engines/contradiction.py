from datetime import date

def detect(facts):
    issues = []
    purchase = facts.get('purchase_date')
    if not purchase:
        return issues
    p = date.fromisoformat(purchase)
    for field in ('fault_date','submission_date'):
        if facts.get(field) and date.fromisoformat(facts[field]) < p:
            issues.append(field + '_before_purchase')
    if facts.get('fault_date') and facts.get('submission_date') and facts['fault_date'] > facts['submission_date']:
        issues.append('fault_after_submission')
    for repair in facts.get('repairs',[]):
        if date.fromisoformat(repair['date']) < p:
            issues.append('repair_before_purchase')
    return issues
