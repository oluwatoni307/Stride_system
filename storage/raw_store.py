# PATH: stride_backend/storage/raw_store.py
# DOMAIN: TinyDB persistence for raw user interaction data.

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List

from tinydb import TinyDB, Query

from core.schemas.entities import (
    FeedbackEvent,
    PhaseTransition,
    PullEvent,
    PullHistory,
    RawUserModel,
)
from storage.store_types import StoreError, StoreResult

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?")

# INF-03 (B-05, B-06): how many recent pulls to retain per user. The
# filters that consume this only ever need the last 2 (DEEP lockout looks
# at 1 prior pull; anti-clumping looks at up to MAX_CONSECUTIVE_PULLS=2
# prior pulls), but keeping a few extra costs nothing and gives headroom
# if a filter's window changes later without needing a storage migration.
_PULL_HISTORY_MAX_LEN = 5


class RawStore:
    def __init__(self, db: TinyDB) -> None:
        self._table = db.table("raw_user_models")
        # INF-03: new table on the SAME TinyDB file/instance passed in —
        # explicitly not a new data/*.json file, per constraint (would
        # require updating the reset protocol and env config for a small
        # rolling list, not worth it).
        self._pull_history_table = db.table("pull_history")

    def _serialise(self, data: Any) -> Any:
        if isinstance(data, datetime):
            return data.isoformat()
        if isinstance(data, Enum):
            # INF-03: PullEvent.tag is a TaskTag enum — explicit handling
            # here rather than relying on TaskTag's str-subclassing to
            # serialise correctly by accident, matching GoalStore's
            # existing explicit Enum branch.
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
        if isinstance(data, dict):
            return {k: self._deserialise(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self._deserialise(item) for item in data]
        return data

    def get(self, user_id: str) -> StoreResult[RawUserModel]:
        try:
            Q = Query()
            doc = self._table.get(Q.user_id == user_id)
            if doc is None:
                return StoreResult(
                    success=False,
                    error=StoreError(
                        code="NOT_FOUND",
                        message=f"No RawUserModel for user {user_id}",
                        operation="get",
                    ),
                )
            model = RawUserModel(**self._deserialise(dict(doc)))
            return StoreResult(success=True, data=model)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(code="READ_ERROR", message=str(e), operation="get"),
            )

    def upsert(self, model: RawUserModel) -> StoreResult[None]:
        try:
            serialised = self._serialise(model.model_dump())
            Q = Query()
            self._table.upsert(serialised, Q.user_id == model.user_id)
            return StoreResult(success=True, data=None)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(code="WRITE_ERROR", message=str(e), operation="upsert"),
            )

    def append_feedback_event(
        self, user_id: str, event: FeedbackEvent
    ) -> StoreResult[None]:
        result = self.get(user_id)
        if not result.success:
            return result
        raw_model = result.data
        raw_model.feedback_events.append(event)
        raw_model.last_updated = datetime.now(timezone.utc)
        return self.upsert(raw_model)

    def append_phase_transition(
        self, user_id: str, transition: PhaseTransition
    ) -> StoreResult[None]:
        result = self.get(user_id)
        if not result.success:
            return result
        raw_model = result.data
        raw_model.phase_transitions.append(transition)
        raw_model.last_updated = datetime.now(timezone.utc)
        return self.upsert(raw_model)

    def initialise_user(self, user_id: str) -> StoreResult[None]:
        result = self.get(user_id)
        if result.success:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="ALREADY_EXISTS",
                    message=f"User {user_id} already exists",
                    operation="initialise_user",
                ),
            )
        fresh = RawUserModel(
            user_id=user_id,
            feedback_events=[],
            phase_transitions=[],
            last_updated=datetime.now(timezone.utc),
        )
        return self.upsert(fresh)

    def get_feedback_events_by_goal(
        self, user_id: str, goal_id: str
    ) -> StoreResult[List[FeedbackEvent]]:
        result = self.get(user_id)
        if not result.success:
            return result
        filtered = [
            e for e in result.data.feedback_events
            if e.goal_id == goal_id
        ]
        return StoreResult(success=True, data=filtered)

    # ── Pull history (INF-03 — B-05, B-06) ──────────────────────────────────────
    # Server-side ground truth for "what was actually pulled last", so that
    # api/routes/tasks.py never has to trust a client-supplied last_task_tag,
    # last_milestone_id, or consecutive_pull_count. Separate table from
    # raw_user_models (different shape, different write frequency — every
    # pull, not just every completion) but same TinyDB file/instance.

    def get_pull_history(self, user_id: str) -> StoreResult[PullHistory]:
        try:
            Q = Query()
            doc = self._pull_history_table.get(Q.user_id == user_id)
            if doc is None:
                # No history yet is a normal, expected state (first-ever
                # pull for this user) — return an empty PullHistory rather
                # than a NOT_FOUND error, since callers shouldn't need a
                # special case for "this user has never pulled before".
                return StoreResult(
                    success=True,
                    data=PullHistory(user_id=user_id, recent_pulls=[]),
                )
            history = PullHistory(**self._deserialise(dict(doc)))
            return StoreResult(success=True, data=history)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="READ_ERROR", message=str(e), operation="get_pull_history"
                ),
            )

    def record_pull(
        self,
        user_id: str,
        task_id: str,
        tag,
        milestone_id: str,
        pulled_at: datetime,
    ) -> StoreResult[None]:
        """
        Append one PullEvent to this user's history and trim to the most
        recent _PULL_HISTORY_MAX_LEN entries (oldest dropped first).
        Called by api/routes/tasks.py immediately after a successful pull
        (pulled_task is not None) — never called for a pull that returned
        no task, since there is nothing to record.
        """
        try:
            existing_result = self.get_pull_history(user_id)
            if not existing_result.success:
                return existing_result
            history = existing_result.data

            history.recent_pulls.append(PullEvent(
                task_id=task_id,
                tag=tag,
                milestone_id=milestone_id,
                pulled_at=pulled_at,
            ))
            # Keep only the most recent N — oldest-first list, so trim from
            # the front.
            if len(history.recent_pulls) > _PULL_HISTORY_MAX_LEN:
                history.recent_pulls = history.recent_pulls[-_PULL_HISTORY_MAX_LEN:]

            serialised = self._serialise(history.model_dump())
            Q = Query()
            self._pull_history_table.upsert(serialised, Q.user_id == user_id)
            return StoreResult(success=True, data=None)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="WRITE_ERROR", message=str(e), operation="record_pull"
                ),
            )