# PATH: stride_backend/core/schemas/contracts/goal_scheduling.py
# DOMAIN: Pydantic schemas for SRSH Boundary 2 — scheduling and task decomposition.

from __future__ import annotations
from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel

from core.schemas.entities import SmartFormulation, CapacityIndicators, PriorityEntry
from core.schemas.contracts.shared import BoundaryError
from stride_backend.core.schemas.contracts.goal_structuring import GoalSummary


class PriorityListSnapshot(BaseModel):
    ranked_goals: List[PriorityEntry]
    last_updated: datetime


class ScheduledTask(BaseModel):
    description: str
    goal_id: str
    scheduled_date: date
    scheduled_time_window: str
    estimated_duration_minutes: int


class TimetableOutput(BaseModel):
    tasks: List[ScheduledTask]


class Boundary2Input(BaseModel):
    user_id: str
    approved_goal: GoalSummary
    smart_formulation: SmartFormulation
    priority_list_snapshot: PriorityListSnapshot
    availability_windows: List[str]
    capacity_indicators: CapacityIndicators
    distillation_version_used: int
    calibration_period_active: bool


class Boundary2Output(BaseModel):
    user_id: str
    goal_id: str
    timetable: TimetableOutput
    conflicts_resolved: List[str]
    generated_by_distillation_version: int
    error: Optional[BoundaryError] = None