# PATH: stride_backend/storage/distilled_store.py
# DOMAIN: TinyDB persistence for distilled user model and priority list.

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from tinydb import TinyDB, Query

from core.schemas.entities import DistilledModel, PriorityList
from storage.store_types import StoreError, StoreResult

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?")


class DistilledStore:
    def __init__(self, db: TinyDB) -> None:
        self._model_table = db.table("distilled_models")
        self._priority_table = db.table("priority_lists")

    def _serialise(self, data: Any) -> Any:
        if isinstance(data, datetime):
            return data.isoformat()
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

    # ── DistilledModel ─────────────────────────────────────────────────────────

    def get_model(self, user_id: str) -> StoreResult[DistilledModel]:
        try:
            Q = Query()
            doc = self._model_table.get(Q.user_id == user_id)
            if doc is None:
                return StoreResult(
                    success=False,
                    error=StoreError(
                        code="NOT_FOUND",
                        message=f"No DistilledModel for user {user_id}",
                        operation="get_model",
                    ),
                )
            model = DistilledModel(**self._deserialise(dict(doc)))
            return StoreResult(success=True, data=model)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="READ_ERROR", message=str(e), operation="get_model"
                ),
            )

    def write_model(self, model: DistilledModel) -> StoreResult[None]:
        try:
            model.distillation_version += 1
            model.last_distilled_at = datetime.now(timezone.utc)
            serialised = self._serialise(model.model_dump())
            Q = Query()
            self._model_table.upsert(serialised, Q.user_id == model.user_id)
            return StoreResult(success=True, data=None)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="WRITE_ERROR", message=str(e), operation="write_model"
                ),
            )

    def get_model_snapshot(self, user_id: str) -> StoreResult[DistilledModel]:
        """
        Returns the DistilledModel directly as snapshot.
        ModelAgentExecutor passes this to LLM prompts via model_dump().
        """
        return self.get_model(user_id)

    def write_model_snapshot(self, model: DistilledModel) -> StoreResult[None]:
        """Alias for write_model — used by executor after weekly guidance."""
        return self.write_model(model)

    def initialise_user(self, user_id: str) -> StoreResult[None]:
        existing = self.get_model(user_id)
        if existing.success:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="ALREADY_EXISTS",
                    message=f"DistilledModel already exists for user {user_id}",
                    operation="initialise_user",
                ),
            )

        model = DistilledModel(
            user_id=user_id,
            notes=None,
            distillation_version=0,
            last_distilled_at=datetime.now(timezone.utc),
        )

        priority_list = PriorityList(
            user_id=user_id,
            ranked_goals=[],
            last_updated=datetime.now(timezone.utc),
        )

        model_result = self.write_model(model)
        if not model_result.success:
            return model_result

        return self.write_priority_list(priority_list)

    # ── PriorityList ───────────────────────────────────────────────────────────

    def get_priority_list(self, user_id: str) -> StoreResult[PriorityList]:
        try:
            Q = Query()
            doc = self._priority_table.get(Q.user_id == user_id)
            if doc is None:
                return StoreResult(
                    success=False,
                    error=StoreError(
                        code="NOT_FOUND",
                        message=f"No PriorityList for user {user_id}",
                        operation="get_priority_list",
                    ),
                )
            priority_list = PriorityList(**self._deserialise(dict(doc)))
            return StoreResult(success=True, data=priority_list)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="READ_ERROR", message=str(e), operation="get_priority_list"
                ),
            )

    def write_priority_list(self, priority_list: PriorityList) -> StoreResult[None]:
        try:
            priority_list.last_updated = datetime.now(timezone.utc)
            serialised = self._serialise(priority_list.model_dump())
            Q = Query()
            self._priority_table.upsert(
                serialised, Q.user_id == priority_list.user_id
            )
            return StoreResult(success=True, data=None)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(
                    code="WRITE_ERROR", message=str(e), operation="write_priority_list"
                ),
            )