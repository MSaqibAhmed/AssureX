import pytest
from src.engines.decision import decide
from src.engines.comparison import compare
from src.schemas.evaluation import RuleResult, Consistency, Probabilities

VALID = dict(valid=.9, invalid=.05, manual_review=.05)
INVALID = dict(valid=.05, invalid=.9, manual_review=.05)
MANUAL = dict(valid=.05, invalid=.05, manual_review=.9)
FAIL = RuleResult(rule_id='coverage', status='FAIL', severity='hard_fail', verified=True, explanation='Expired')

@pytest.mark.parametrize('p,g,rules,verified,branch,recommendation', [
    (None,VALID,[],True,1,'Manual Review Required'),
    (VALID,INVALID,[],True,2,'Manual Review Required'),
    (INVALID,INVALID,[FAIL],True,3,'Likely Invalid'),
    (VALID,VALID,[],True,4,'Likely Valid'),
    (INVALID,INVALID,[],True,5,'Manual Review Required'),
    (VALID,VALID,[],False,5,'Manual Review Required'),
])
def test_all_priority_branches(p,g,rules,verified,branch,recommendation):
    result = decide(p,g,rules,mandatory_facts_verified=verified)
    assert (result.branch, result.recommendation) == (branch,recommendation)

@pytest.mark.parametrize('blocker', ['critical_evidence_missing','unresolved_contradiction','unresolved_duplicate'])
def test_blockers_precede_hard_failure(blocker):
    assert decide(INVALID,INVALID,[FAIL],mandatory_facts_verified=True,**{blocker:True}).branch == 1

def test_manual_model_precedes_hard_fail():
    assert decide(MANUAL,MANUAL,[FAIL],mandatory_facts_verified=True).branch == 2

@pytest.mark.parametrize('bad', [None,{}, {'valid':float('nan'),'invalid':0,'manual_review':0},
    {'valid':.9,'invalid':.9,'manual_review':.1}, {'valid':-1,'invalid':1,'manual_review':1}])
def test_invalid_probabilities(bad):
    assert compare(bad,VALID).status == Consistency.UNCERTAIN

@pytest.mark.parametrize('p,g,status', [
    (VALID,VALID,Consistency.STRONG),
    (VALID,INVALID,Consistency.DISAGREEMENT),
    ({'valid':.7,'invalid':.2,'manual_review':.1},VALID,Consistency.ACCEPTABLE),
    ({'valid':.6,'invalid':.3,'manual_review':.1},VALID,Consistency.WEAK),
    ({'valid':.5,'invalid':.5,'manual_review':0},VALID,Consistency.UNCERTAIN),
])
def test_comparison(p,g,status):
    assert compare(p,g).status == status

def test_unverified_failure_cannot_reject():
    rule = FAIL.model_copy(update={'verified':False})
    assert decide(INVALID,INVALID,[rule],mandatory_facts_verified=True).branch == 5
