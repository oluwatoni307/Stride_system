from typing import List, Optional
from pydantic import BaseModel, Field

from core.schemas.enums import TaskTag
from core.schemas.contracts.shared import BoundaryError, CompletedTaskSummary


class TaskDraft(BaseModel):
    description: str
    tag: TaskTag
    dependencies: List[str] = Field(default_factory=list)
    # dependencies reference other task descriptions
    # API resolves these to task_ids on write
    schema_version: int = 1


class TaskDecompositionInput(BaseModel):
    milestone_id: str
    milestone_description: str
    objectives: List[str]
    success_metrics: List[str]
    previous_task_logs: List[CompletedTaskSummary] = Field(default_factory=list)
    schema_version: int = 1


class TaskDecompositionOutput(BaseModel):
    milestone_id: str
    tasks: List[TaskDraft]
    error: Optional[BoundaryError] = None
    schema_version: int = 1


class StalledTaskBreakdownInput(BaseModel):
    task_id: str
    description: str
    tag: TaskTag
    milestone_id: str
    milestone_description: str
    schema_version: int = 1


class StalledTaskBreakdownOutput(BaseModel):
    original_task_id: str
    replacement_tasks: List[TaskDraft]     # 2–4 MODERATE or MECHANICAL tasks
    error: Optional[BoundaryError] = None
    schema_version: int = 1