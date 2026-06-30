from typing import Optional
from pydantic import BaseModel

from core.schemas.contracts.shared import BoundaryError


class Boundary3Input(BaseModel):
    user_id: str
    task_id: str
    goal_id: str
    milestone_id: str
    completion_timestamp: str       # ISO datetime string
    user_note: Optional[str] = None
    trigger_significance_check: bool = False    # always False in v1
    schema_version: int = 1


class Boundary3Output(BaseModel):
    user_id: str
    task_id: str
    success: bool
    error: Optional[BoundaryError] = None
    schema_version: int = 1