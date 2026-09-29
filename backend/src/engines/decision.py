"""Advisory only. This engine never writes Approved or Rejected."""
from src.engines.comparison import compare, probabilities
from src.schemas.evaluation import Consistency, Decision, RuleResult

def decide(python, gtm, rules: list[RuleResult], *, mandatory_facts_verified: bool,
           critical_evidence_missing: bool = False, unresolved_contradiction: bool = False,
           unresolved_duplicate: bool = False) -> Decision:
    p, g = probabilities(python), probabilities(gtm)
    comparison = compare(p, g)
    blockers = []
    if p is None or g is None:
        blockers.append('A model failed or returned invalid output')
    if critical_evidence_missing or any(r.severity == 'critical' and r.status == 'UNKNOWN' for r in rules):
        blockers.append('Critical evidence is unknown or missing')
    if unresolved_contradiction:
        blockers.append('Unresolved contradiction')
    if unresolved_duplicate:
        blockers.append('Unresolved duplicate signal')
    if blockers:
        return Decision(recommendation='Manual Review Required', branch=1, reasons=blockers)
    tops = (p.ranked()[0][0], g.ranked()[0][0])
    if (comparison.status not in (Consistency.STRONG, Consistency.ACCEPTABLE)
            or 'manual_review' in tops or any(r.status == 'MANUAL_REVIEW' for r in rules)):
        return Decision(recommendation='Manual Review Required', branch=2,
                        reasons=['Model consistency, model class, or policy requires review'])
    hard_fail = any(r.status == 'FAIL' and r.severity == 'hard_fail' and r.verified for r in rules)
    if tops == ('invalid', 'invalid') and hard_fail:
        return Decision(recommendation='Likely Invalid', branch=3,
                        reasons=['Both models agree and a verified hard-fail exists'])
    if (tops == ('valid', 'valid') and mandatory_facts_verified and not hard_fail
            and not any(r.status in ('FAIL', 'UNKNOWN', 'MANUAL_REVIEW') for r in rules)):
        return Decision(recommendation='Likely Valid', branch=4,
                        reasons=['Models agree, mandatory facts are verified, and rules permit coverage'])
    return Decision(recommendation='Manual Review Required', branch=5,
                    reasons=['Evidence does not satisfy an advisory valid or invalid branch'])
