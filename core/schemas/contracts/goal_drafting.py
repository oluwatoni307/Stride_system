from typing import List, Optional
from pydantic import BaseModel

from core.schemas.enums import TaskTag
from core.schemas.contracts.shared import BoundaryError, CompletedTaskSummary


class ProposedMilestone(BaseModel):
    description: str
    objectives: List[str]
    suggested_tag: TaskTag          # predominant task type expected in this milestone
    schema_version: int = 1


class DraftingInput(BaseModel):
    user_id: str
    raw_goal: str
    user_context: str               # brief profile summary
    distilled_model_snapshot: dict
    schema_version: int = 1


class DraftingOutput(BaseModel):
    user_id: str
    objectives: List[str]
    proposed_milestones: List[ProposedMilestone]
    success_metrics: List[str]
    error: Optional[BoundaryError] = None
    schema_version: int = 1


class DraftingRevisionInput(BaseModel):
    user_id: str
    previous_draft: DraftingOutput
    user_response: str
    schema_version: int = 1