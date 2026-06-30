from typing import Optional
from pydantic import BaseModel


class BoundaryError(BaseModel):
    code: str
    message: str
    component: str          # which agent or component raised this
    retry_count: int = 0    # how many times this boundary has been retried
    schema_version: int = 2


# ─────────────────────────────────────────────
# SHARED TYPES (used across multiple contracts)
# ─────────────────────────────────────────────

class GoalSummary(BaseModel):
    goal_id: str
    name: str
    macro_impact: int
    terminal_deadline: str      # ISO string
    status: str
    schema_version: int = 2


class MilestoneSummary(BaseModel):
    milestone_id: str
    goal_id: str
    description: str
    tri_vector_weight: float
    min_weekly_units: int
    status: str
    schema_version: int = 2


class CompletedTaskSummary(BaseModel):
    task_id: str
    description: str
    tag: str
    completed_at: str           # ISO string
    schema_version: int = 2