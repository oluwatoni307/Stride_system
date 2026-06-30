# PATH: stride_backend/core/schemas/contracts/task_coaching.py
# DOMAIN: Task Coach contract — task generation from timetable slots and task regeneration after edit

from __future__ import annotations
from datetime import date
from typing import List, Optional
from pydantic import BaseModel
from core.schemas.entities import FeedbackEvent, Task, TaskStatus, GoalStatus
from core.schemas.contracts.shared import BoundaryError


# ── Type 1 — Task Generation (Mode 1) ─────────────────────────────────────────

class MilestoneSlot(BaseModel):
    milestone_id: str
    goal_id: str
    scheduled_date: date
    scheduled_time_window: str
    estimated_duration_minutes: int


class TaskGenerationInput(BaseModel):
    user_id: str
    milestone_id: str
    goal_id: str
    milestone_description: str
    slots: List[MilestoneSlot]
    goal_context: str
    previous_task_logs: List[FeedbackEvent]


class TaskGenerationOutput(BaseModel):
    user_id: str
    milestone_id: str
    tasks: List[Task]
    error: Optional[BoundaryError] = None


# ── Type 2 — Task Regeneration (Mode 2) ───────────────────────────────────────

class TaskRegenerationInput(BaseModel):
    user_id: str
    task_id: str
    goal_id: str
    milestone_id: str
    new_description: str
    new_scheduled_date: date
    new_scheduled_time_window: str
    new_estimated_duration_minutes: int
    reason_for_change: str


class TaskRegenerationOutput(BaseModel):
    user_id: str
    task_id: str
    regenerated_task: Task
    error: Optional[BoundaryError] = None