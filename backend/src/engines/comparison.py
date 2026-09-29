from pydantic import ValidationError
from src.schemas.evaluation import Comparison, Consistency, Probabilities

def probabilities(value):
    try:
        return value if isinstance(value, Probabilities) else Probabilities.model_validate(value)
    except (ValidationError, TypeError, ValueError):
        return None

def compare(python, gtm) -> Comparison:
    p, g = probabilities(python), probabilities(gtm)
    if p is None or g is None:
        return Comparison(status=Consistency.UNCERTAIN)
    pr, gr = p.ranked(), g.ranked()
    difference = abs(pr[0][1] - gr[0][1])
    cmin = min(pr[0][1], gr[0][1])
    # Tolerance permits exact decimal boundaries despite binary floating point.
    if cmin < .60 - 1e-12 or any(r[0][1] - r[1][1] < .10 - 1e-12 or r[0][1] == r[1][1] for r in (pr, gr)):
        status = Consistency.UNCERTAIN
    elif pr[0][0] != gr[0][0]:
        status = Consistency.DISAGREEMENT
    elif cmin >= .85 - 1e-12 and difference <= .10 + 1e-12:
        status = Consistency.STRONG
    elif cmin >= .70 - 1e-12 and difference <= .20 + 1e-12:
        status = Consistency.ACCEPTABLE
    else:
        status = Consistency.WEAK
    return Comparison(status=status, difference=difference)
