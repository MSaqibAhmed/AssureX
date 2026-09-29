"""Immutable persisted evaluation contract. Probabilities use fractions, not percentages."""
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Probabilities(StrictModel):
    valid: float = Field(ge=0, le=1)
    invalid: float = Field(ge=0, le=1)
    manual_review: float = Field(ge=0, le=1)

    @model_validator(mode='after')
    def normalized(self):
        values = list(self.model_dump().values())
        if not all(isfinite(v) for v in values) or abs(sum(values) - 1) > 1e-5:
            raise ValueError('Probabilities must be finite and sum to one')
        return self

    def ranked(self):
        return sorted(self.model_dump().items(), key=lambda item: item[1], reverse=True)

class Consistency(StrEnum):
    UNCERTAIN = 'Uncertain Result'
    DISAGREEMENT = 'Model Disagreement'
    STRONG = 'Strong Match'
    ACCEPTABLE = 'Acceptable Match'
    WEAK = 'Weak Match'

class Comparison(StrictModel):
    difference: float | None = None
    status: Consistency

class RuleResult(StrictModel):
    rule_id: str
    status: Literal['PASS', 'FAIL', 'WARNING', 'UNKNOWN', 'MANUAL_REVIEW']
    severity: Literal['info', 'warning', 'hard_fail', 'critical']
    verified: bool = False
    facts_used: dict = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    explanation: str

class Decision(StrictModel):
    recommendation: Literal['Likely Valid', 'Likely Invalid', 'Manual Review Required']
    branch: int = Field(ge=1, le=5)
    reasons: list[str]

class Predictions(StrictModel):
    python: Probabilities | None
    gtm: Probabilities | None

class EvaluationRun(StrictModel):
    id: str
    claim_revision_id: str
    input_hash: str
    evaluation_input_version_hash: str
    status: Literal['completed']
    versions: dict[str, str]
    predictions: Predictions
    comparison: Comparison
    rule_results: list[RuleResult]
    recommendation: Literal['Likely Valid', 'Likely Invalid', 'Manual Review Required']
    reasons: list[str]
    decision_branch: int = Field(ge=1, le=5)
    completed_at: datetime
    model_errors: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode='after')
    def pinned_versions(self):
        if not {'python', 'gtm', 'policy'} <= self.versions.keys():
            raise ValueError('Python, GTM and policy versions must be pinned')
        return self
