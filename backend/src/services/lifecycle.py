from fastapi import HTTPException

TRANSITIONS = {
    'Draft': {'Submitted'},
    'Submitted': {'Under Evaluation'},
    'Under Evaluation': {'Manual Review'},
    'Manual Review': {'Approved','Rejected','Additional Information Required'},
    'Additional Information Required': {'Submitted'},
    'Approved': {'Closed'},
    'Rejected': {'Closed'},
    'Closed': set(),
}

def require_transition(before,after):
    if after not in TRANSITIONS.get(before,set()):
        raise HTTPException(409,'Invalid claim state transition')
