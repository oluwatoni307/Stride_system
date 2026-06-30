# PATH: stride_backend/core/schemas/contracts/execution_engine.py
from __future__ import annotations
from datetime import date
from typing import List, Optional
from pydantic import BaseModel
from core.schemas.contracts.shared import BoundaryError
from core.schemas.enums import EnergyLevel, TaskTag
from core.schemas.entities import Task

# ── Shared allocation data ─────────────────────────────────────────────────────
class MilestoneAllocationData(BaseModel):
    """Minimal milestone data passed to SchedulingComponent and SlotAllocator."""
    milestone_id: str
    tri_vector_weight: float
    min_weekly_units: int
    max_weekly_units: int
    schema_version: int = 1

# ── SchedulingComponent contracts ──────────────────────────────────────────────
class SlotAllocationInput(BaseModel):
    user_id: str
    week_start: date
    milestones: List[MilestoneAllocationData]   # was active_milestone_ids: List[str]
    slot_grid: dict
    notes: Optional[str] = None
    schema_version: int = 1

class DeepSessionPlan(BaseModel):
    milestone_id: str
    assigned_days: List[str]
    sessions_planned: int
    sessions_needed: int
    partial_allocation: bool = False
    schema_version: int = 1

class SlotAllocationOutput(BaseModel):
    user_id: str
    week_start: date
    deep_session_plans: List[DeepSessionPlan]
    error: Optional[BoundaryError] = None
    schema_version: int = 1

# ── SlotAllocator contracts ────────────────────────────────────────────────────
class QueuePullRequest(BaseModel):
    user_id: str
    current_energy_level: EnergyLevel
    last_task_tag: Optional[TaskTag] = None
    last_milestone_id: Optional[str] = None
    consecutive_pull_count: int = 0
    force_pull: bool = False
    schema_version: int = 1

class QueuePullResponse(BaseModel):
    pulled_task: Optional[Task] = None
    state_message: str
    error: Optional[BoundaryError] = None
    schema_version: int = 1

# ── Weekly aggregation ─────────────────────────────────────────────────────────
class MilestoneUtilization(BaseModel):
    milestone_id: str
    description: str
    consumed_units: int
    max_weekly_units: int
    utilization_pct: float
    below_floor: bool
    schema_version: int = 1

class WeeklyAggregatedSummary(BaseModel):
    user_id: str
    week_start: str
    milestones_active: int
    tasks_completed: int
    tasks_stalled: int
    deep_work_sessions: int
    mechanical_bias_pct: float
    milestone_utilization: List[MilestoneUtilization]
    goals_below_floor: List[str]
    schema_version: int = 1