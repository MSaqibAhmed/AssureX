import pytest
from fastapi import HTTPException
from src.services.lifecycle import TRANSITIONS,require_transition

def test_only_reviewer_stage_can_reach_final_decisions():
    for before,targets in TRANSITIONS.items():
        if before!='Manual Review': assert not {'Approved','Rejected'} & targets
    require_transition('Manual Review','Approved')
    require_transition('Approved','Closed')
    with pytest.raises(HTTPException): require_transition('Draft','Approved')
    with pytest.raises(HTTPException): require_transition('Closed','Submitted')
