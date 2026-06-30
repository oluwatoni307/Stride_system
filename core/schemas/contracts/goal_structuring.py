from typing import List, Optional
from pydantic import BaseModel

from core.schemas.contracts.shared import BoundaryError, GoalSummary


class SmartFormulation(BaseModel):
    specific: str
    measurable: str
    achievable: str
    relevant: str
    time_bound: str
    schema_version: int = 2


class Boundary1Input(BaseModel):
    user_id: str
    confirmed_draft: dict  # DraftingOutput passed as dict
    distilled_model_snapshot: dict
    existing_goal_summaries: List[GoalSummary] = []
    schema_version: int = 2


class Boundary1Output(BaseModel):
    user_id: str
    smart_formulation: SmartFormulation
    impact_score: int  # 1–5; SmartAgent assigns, Python uses as I
    extracted_deadline: Optional[str] = None  # ISO date string; SmartAgent extracts.
    # None is valid — not every goal has a
    # deadline. confirm_goal already handles
    # this explicitly (400 if missing when required).    viability_assessment: str
    conflict_flag: bool = False
    override_flag: bool = False
    override_reason: Optional[str] = None
    error: Optional[BoundaryError] = None
    schema_version: int = 2
