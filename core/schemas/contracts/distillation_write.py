# PATH: stride_backend/core/schemas/contracts/distillation_write.py
# DOMAIN: Pydantic schemas for SRSH Boundary 5 — Model Agent internal distillation write.

from __future__ import annotations
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel

from core.schemas.entities import (
    SelfEfficacyLevel,
    BehaviouralBaseline,
    CapacityIndicators,
)
from core.schemas.contracts.shared import BoundaryError, RecentFeedbackEvent
from core.schemas.contracts.goal_structuring import DistilledModelSnapshot


class DistillationOperation(str, Enum):
    DISTILLED_MODEL_UPDATE = "distilled_model_update"
    PRIORITY_LIST_REWRITE  = "priority_list_rewrite"
    SIGNIFICANCE_CHECK     = "significance_check"


class UpdatedDistilledModel(BaseModel):
    self_efficacy_signal: SelfEfficacyLevel
    behavioural_baseline: BehaviouralBaseline
    capacity_indicators: CapacityIndicators
    calibration_period_active: bool


class Boundary5Input(BaseModel):
    user_id: str
    raw_log_window: List[RecentFeedbackEvent]
    current_distilled_model: DistilledModelSnapshot
    operation: DistillationOperation


class Boundary5Output(BaseModel):
    user_id: str
    updated_distilled_model: UpdatedDistilledModel
    distillation_version: int
    operation_fired: DistillationOperation
    write_confirmed: bool
    error: Optional[BoundaryError] = None