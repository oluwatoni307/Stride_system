from __future__ import annotations
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

from core.schemas.enums import (
    TaskTag, TaskStatus, MilestoneStatus, GoalStatus, EnergyLevel
)


# ─────────────────────────────────────────────
# GOAL
# ─────────────────────────────────────────────

class Goal(BaseModel):
    goal_id: str
    user_id: str
    name: str
    status: GoalStatus = GoalStatus.ACTIVE
    macro_impact: int               # 1–5, cascades to child milestones as I
    terminal_deadline: date         # Python uses this to compute U
    schema_version: int = 2


# ─────────────────────────────────────────────
# MILESTONE
# ─────────────────────────────────────────────

class Milestone(BaseModel):
    milestone_id: str
    goal_id: str
    user_id: str
    description: str
    objectives: List[str] = Field(default_factory=list)
    success_metrics: List[str] = Field(default_factory=list)
    tri_vector_weight: float = 0.0          # computed by Python, not LLM
    min_weekly_units: int = 0               # floor — derived from weight
    max_weekly_units: int = 0               # ceiling — derived from weight
    status: MilestoneStatus = MilestoneStatus.DRAFT
    schema_version: int = 2


# ─────────────────────────────────────────────
# TASK
# ─────────────────────────────────────────────

class Task(BaseModel):
    task_id: str
    milestone_id: str
    goal_id: str
    user_id: str
    description: str
    tag: TaskTag
    dependencies: List[str] = Field(default_factory=list)  # list of task_ids
    status: TaskStatus = TaskStatus.PENDING
    stalled_flag: bool = False
    # INF-03 (B-09): set the moment a task transitions to AVAILABLE — the
    # two call sites are _resolve_dependencies (api/routes/goals.py,
    # initial creation at confirm_goal) and the dependency-unlock loop in
    # complete_task (api/routes/tasks.py). Stagnation age check at pull
    # time (core/execution/slot_allocator.py) reads this field; it is
    # never recomputed or re-derived elsewhere. None until the task first
    # becomes AVAILABLE — a task sitting PENDING has no age to measure.
    first_made_available_at: Optional[datetime] = None
    schema_version: int = 2

    # NOTE: No slot_units field. Slot cost derived at runtime:
    # MECHANICAL=1, MODERATE=2, DEEP=4 (from config.SLOT_UNIT_CONSTANTS)


# ─────────────────────────────────────────────
# SLOT GRID
# ─────────────────────────────────────────────

class TimeSlot(BaseModel):
    day: str                        # e.g. "Monday"
    start_time: str                 # e.g. "09:00"
    energy_level: EnergyLevel


class SlotGrid(BaseModel):
    user_id: str
    week_start: date
    slots: List[TimeSlot] = Field(default_factory=list)
    schema_version: int = 1

    # NOTE: SlotGrid holds NO task IDs.
    # It is an energy index — describes the user's week, not their schedule.


# ─────────────────────────────────────────────
# ONBOARDING PROFILE
# ─────────────────────────────────────────────

class EnergyBlock(BaseModel):
    label: str                  # user-defined free text, e.g. "morning", "post-lunch slump"
    start_time: str             # "HH:MM" 24hr format
    end_time: str               # "HH:MM" 24hr format, must be > start_time
    energy_level: EnergyLevel   # HIGH | MEDIUM | LOW

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        import re
        if not re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", v):
            raise ValueError(f"Invalid HH:MM time format: {v}")
        return v


class OnboardingProfile(BaseModel):
    user_id: str
    max_workable_hours: float                   # hard weekly cap
    weekday_blocks: List[EnergyBlock]            # applied Mon-Fri
    weekend_blocks: List[EnergyBlock]            # applied Sat-Sun. Client sends
                                                  # matching blocks for both if user
                                                  # wants no weekday/weekend difference
                                                  # — this is a user decision, not a
                                                  # system default. Never silently
                                                  # duplicated server-side.
    schema_version: int = 3


# ─────────────────────────────────────────────
# RAW STORE ENTITIES
# ─────────────────────────────────────────────

class FeedbackEvent(BaseModel):
    id: str
    task_id: str
    goal_id: str
    milestone_id: str
    user_id: str
    completed_at: datetime
    note: Optional[str] = None
    significance_check_triggered: bool = False
    schema_version: int = 1


class PhaseTransition(BaseModel):
    id: str
    goal_id: str
    user_id: str
    from_status: str
    to_status: str
    transitioned_at: datetime
    reason: str
    schema_version: int = 1


class RawUserModel(BaseModel):
    user_id: str
    feedback_events: List[FeedbackEvent] = Field(default_factory=list)
    phase_transitions: List[PhaseTransition] = Field(default_factory=list)
    last_updated: datetime
    schema_version: int = 1


# ─────────────────────────────────────────────
# PULL HISTORY (INF-03 — B-05, B-06)
# ─────────────────────────────────────────────
# Server-side record of what was actually pulled, independent of whatever
# a client claims in last_task_tag / last_milestone_id / consecutive_pull_count
# on a PullTaskRequest. Per INF-03: "do not trust the client to report this
# correctly." Stored on RawStore as a new table on the SAME TinyDB file
# (no new data/*.json file) — see storage/raw_store.py PullHistory methods.
# Kept short: only the last few entries per user are retained (trim logic
# lives in RawStore, not here — this is just the per-pull record shape).

class PullEvent(BaseModel):
    task_id: str
    tag: TaskTag
    milestone_id: str
    pulled_at: datetime
    schema_version: int = 1


class PullHistory(BaseModel):
    user_id: str
    recent_pulls: List[PullEvent] = Field(default_factory=list)  # most recent last
    schema_version: int = 1


# ─────────────────────────────────────────────
# DISTILLED STORE ENTITIES
# ─────────────────────────────────────────────

class PriorityEntry(BaseModel):
    goal_id: str
    goal_name: str
    weight: float                   # tri_vector_weight — used for ordering
    schema_version: int = 1


class PriorityList(BaseModel):
    user_id: str
    ranked_goals: List[PriorityEntry] = Field(default_factory=list)
    last_updated: datetime
    schema_version: int = 1


class DistilledModel(BaseModel):
    user_id: str
    notes: Optional[str] = None     # free-form coaching notes from weekly guidance
    distillation_version: int = 0   # incremented on each write
    last_distilled_at: Optional[datetime] = None
    schema_version: int = 1