# PATH: stride_backend/storage/goal_store.py
# DOMAIN: TinyDB persistence for Goals, Milestones, and Tasks.

from __future__ import annotations

import re
from datetime import datetime, date, timezone
from enum import Enum
from typing import Any, List

from tinydb import TinyDB, Query

from core.schemas.entities import Goal, Milestone, Task
from core.schemas.enums import GoalStatus, MilestoneStatus, TaskStatus
from storage.store_types import StoreError, StoreResult

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class GoalStore:
    def __init__(self, db: TinyDB) -> None:
        self._goals = db.table("goals")
        self._milestones = db.table("milestones")
        self._tasks = db.table("tasks")

    def _serialise(self, data: Any) -> Any:
        if isinstance(data, datetime):
            return data.isoformat()
        if isinstance(data, date):
            return data.isoformat()
        if isinstance(data, Enum):
            return data.value
        if isinstance(data, dict):
            return {k: self._serialise(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self._serialise(item) for item in data]
        return data

    def _deserialise(self, data: Any) -> Any:
        if isinstance(data, str) and _ISO_RE.match(data):
            try:
                return datetime.fromisoformat(data)
            except ValueError:
                return data
        if isinstance(data, str) and _DATE_RE.match(data):
            try:
                return date.fromisoformat(data)
            except ValueError:
                return data
        if isinstance(data, dict):
            return {k: self._deserialise(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self._deserialise(item) for item in data]
        return data

    # ── Goal methods ───────────────────────────────────────────────────────────

    def get_goal(self, user_id: str, goal_id: str) -> StoreResult[Goal]:
        try:
            Q = Query()
            doc = self._goals.get(
                (Q.goal_id == goal_id) & (Q.user_id == user_id)
            )
            if doc is None:
                return StoreResult(
                    success=False,
                    error=StoreError(
                        code="NOT_FOUND",
                        message=f"No Goal with goal_id {goal_id} for user {user_id}",
                        operation="get_goal",
                    ),
                )
            goal = Goal(**self._deserialise(dict(doc)))
            return StoreResult(success=True, data=goal)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="READ_ERROR", message=str(e), operation="get_goal"
                ),
            )

    def get_goals_by_user(self, user_id: str) -> StoreResult[List[Goal]]:
        try:
            Q = Query()
            docs = self._goals.search(Q.user_id == user_id)
            goals = [Goal(**self._deserialise(dict(doc))) for doc in docs]
            return StoreResult(success=True, data=goals)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="READ_ERROR", message=str(e), operation="get_goals_by_user"
                ),
            )

    def get_active_goals(self, user_id: str) -> StoreResult[List[Goal]]:
        try:
            Q = Query()
            docs = self._goals.search(
                (Q.user_id == user_id) & (Q.status == GoalStatus.ACTIVE.value)
            )
            goals = [Goal(**self._deserialise(dict(doc))) for doc in docs]
            return StoreResult(success=True, data=goals)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="READ_ERROR", message=str(e), operation="get_active_goals"
                ),
            )

    def upsert_goal(self, goal: Goal) -> StoreResult[None]:
        try:
            serialised = self._serialise(goal.model_dump())
            Q = Query()
            self._goals.upsert(serialised, Q.goal_id == goal.goal_id)
            return StoreResult(success=True, data=None)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="WRITE_ERROR", message=str(e), operation="upsert_goal"
                ),
            )

    def update_goal_status(
        self, goal_id: str, user_id: str, new_status: GoalStatus, reason: str
    ) -> StoreResult[None]:
        if not reason:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="INVALID_INPUT",
                    message="reason must not be empty",
                    operation="update_goal_status",
                ),
            )
        result = self.get_goal(user_id, goal_id)
        if not result.success:
            return result
        goal = result.data
        goal.status = new_status
        return self.upsert_goal(goal)

    # ── Milestone methods ──────────────────────────────────────────────────────

    def get_milestones_by_goal(self, goal_id: str) -> StoreResult[List[Milestone]]:
        try:
            Q = Query()
            docs = self._milestones.search(Q.goal_id == goal_id)
            milestones = [
                Milestone(**self._deserialise(dict(doc))) for doc in docs
            ]
            return StoreResult(success=True, data=milestones)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="READ_ERROR",
                    message=str(e),
                    operation="get_milestones_by_goal",
                ),
            )

    def get_active_milestones_by_user(
        self, user_id: str
    ) -> StoreResult[List[Milestone]]:
        try:
            Q = Query()
            docs = self._milestones.search(
                (Q.user_id == user_id)
                & (Q.status == MilestoneStatus.ACTIVE.value)
            )
            milestones = [
                Milestone(**self._deserialise(dict(doc))) for doc in docs
            ]
            return StoreResult(success=True, data=milestones)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="READ_ERROR",
                    message=str(e),
                    operation="get_active_milestones_by_user",
                ),
            )

    def get_staged_milestones_by_user(
        self, user_id: str
    ) -> StoreResult[List[Milestone]]:
        try:
            Q = Query()
            docs = self._milestones.search(
                (Q.user_id == user_id)
                & (Q.status == MilestoneStatus.STAGED.value)
            )
            milestones = [
                Milestone(**self._deserialise(dict(doc))) for doc in docs
            ]
            return StoreResult(success=True, data=milestones)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="READ_ERROR",
                    message=str(e),
                    operation="get_staged_milestones_by_user",
                ),
            )

    def upsert_milestone(self, milestone: Milestone) -> StoreResult[None]:
        try:
            serialised = self._serialise(milestone.model_dump())
            Q = Query()
            self._milestones.upsert(
                serialised, Q.milestone_id == milestone.milestone_id
            )
            return StoreResult(success=True, data=None)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="WRITE_ERROR", message=str(e), operation="upsert_milestone"
                ),
            )

    # ── Task methods ───────────────────────────────────────────────────────────

    def get_task(self, task_id: str) -> StoreResult[Task]:
        try:
            Q = Query()
            doc = self._tasks.get(Q.task_id == task_id)
            if doc is None:
                return StoreResult(
                    success=False,
                    error=StoreError(
                        code="NOT_FOUND",
                        message=f"No Task with task_id {task_id}",
                        operation="get_task",
                    ),
                )
            task = Task(**self._deserialise(dict(doc)))
            return StoreResult(success=True, data=task)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="READ_ERROR", message=str(e), operation="get_task"
                ),
            )

    def get_tasks_by_milestone(
        self, milestone_id: str
    ) -> StoreResult[List[Task]]:
        try:
            Q = Query()
            docs = self._tasks.search(Q.milestone_id == milestone_id)
            tasks = [Task(**self._deserialise(dict(doc))) for doc in docs]
            return StoreResult(success=True, data=tasks)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="READ_ERROR",
                    message=str(e),
                    operation="get_tasks_by_milestone",
                ),
            )

    def get_available_tasks_by_user(
        self, user_id: str
    ) -> StoreResult[List[Task]]:
        """
        Returns all AVAILABLE tasks for a user across all milestones.
        Used by the API route to feed SlotAllocator.pull().
        """
        try:
            Q = Query()
            docs = self._tasks.search(
                (Q.user_id == user_id)
                & (Q.status == TaskStatus.AVAILABLE.value)
            )
            tasks = [Task(**self._deserialise(dict(doc))) for doc in docs]
            return StoreResult(success=True, data=tasks)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="READ_ERROR",
                    message=str(e),
                    operation="get_available_tasks_by_user",
                ),
            )

    def upsert_task(self, task: Task) -> StoreResult[None]:
        try:
            serialised = self._serialise(task.model_dump())
            Q = Query()
            self._tasks.upsert(serialised, Q.task_id == task.task_id)
            return StoreResult(success=True, data=None)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="WRITE_ERROR", message=str(e), operation="upsert_task"
                ),
            )

    def update_task_status(
        self, task_id: str, new_status: TaskStatus
    ) -> StoreResult[None]:
        result = self.get_task(task_id)
        if not result.success:
            return result
        task = result.data
        task.status = new_status
        return self.upsert_task(task)

    def get_tasks_by_user(self, user_id: str) -> StoreResult[List[Task]]:
        try:
            Q = Query()
            docs = self._tasks.search(Q.user_id == user_id)
            tasks = [Task(**self._deserialise(dict(doc))) for doc in docs]
            return StoreResult(success=True, data=tasks)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="READ_ERROR",
                    message=str(e),
                    operation="get_tasks_by_user",
                ),
            )