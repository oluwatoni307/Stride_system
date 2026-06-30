from datetime import datetime, timezone
from typing import Optional

from core.schemas.contracts.feedback_loop import Boundary3Input
from core.schemas.contracts.shared import BoundaryError


class FeedbackLoop:
    """
    Pure data packaging component.
    No LLM. No storage. No intelligence.
    Receives raw completion data, returns typed Boundary3Input.
    """

    def package_completion_event(
        self,
        user_id: str,
        task_id: str,
        goal_id: str,
        milestone_id: str,
        completion_timestamp: Optional[str] = None,
        user_note: Optional[str] = None,
    ) -> Boundary3Input:
        """
        Package a task completion event into a typed boundary input.

        Args:
            user_id:               ID of the user completing the task
            task_id:               ID of the completed task
            goal_id:               ID of the parent goal
            milestone_id:          ID of the parent milestone
            completion_timestamp:  ISO datetime string; defaults to now if not provided
            user_note:             Optional note from the user on completion

        Returns:
            Boundary3Input — typed contract ready for ModelAgentExecutor
        """
        if completion_timestamp is None:
            completion_timestamp = datetime.now(timezone.utc).isoformat()

        return Boundary3Input(
            user_id=user_id,
            task_id=task_id,
            goal_id=goal_id,
            milestone_id=milestone_id,
            completion_timestamp=completion_timestamp,
            user_note=user_note,
            trigger_significance_check=False,   # v1 — weekly distillation only
            schema_version=1,
        )