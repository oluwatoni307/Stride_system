# PATH: stride_backend/storage/onboarding_store.py
# DOMAIN: TinyDB persistence for OnboardingProfile and SlotGrid.

from __future__ import annotations

import re
from datetime import datetime, date
from enum import Enum
from typing import Any

from tinydb import TinyDB, Query

from core.schemas.entities import OnboardingProfile, SlotGrid
from storage.store_types import StoreError, StoreResult

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class OnboardingStore:
    def __init__(self, db: TinyDB) -> None:
        self._profiles = db.table("onboarding_profiles")
        self._grids = db.table("slot_grids")

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

    # ── Profile methods ──────────────────────────────────────────────────

    def get_profile(self, user_id: str) -> StoreResult[OnboardingProfile]:
        try:
            Q = Query()
            doc = self._profiles.get(Q.user_id == user_id)
            if doc is None:
                return StoreResult(
                    success=False,
                    error=StoreError(
                        code="NOT_FOUND",
                        message=f"No OnboardingProfile for user {user_id}",
                        operation="get_profile",
                    ),
                )
            profile = OnboardingProfile(**self._deserialise(dict(doc)))
            return StoreResult(success=True, data=profile)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(code="READ_ERROR", message=str(e), operation="get_profile"),
            )

    def upsert_profile(self, profile: OnboardingProfile) -> StoreResult[None]:
        try:
            serialised = self._serialise(profile.model_dump())
            Q = Query()
            self._profiles.upsert(serialised, Q.user_id == profile.user_id)
            return StoreResult(success=True, data=None)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(code="WRITE_ERROR", message=str(e), operation="upsert_profile"),
            )

    # ── SlotGrid methods ─────────────────────────────────────────────────

    def get_slot_grid(self, user_id: str, week_start: date) -> StoreResult[SlotGrid]:
        try:
            Q = Query()
            doc = self._grids.get(
                (Q.user_id == user_id) & (Q.week_start == week_start.isoformat())
            )
            if doc is None:
                return StoreResult(
                    success=False,
                    error=StoreError(
                        code="NOT_FOUND",
                        message=f"No SlotGrid for user {user_id}, week {week_start.isoformat()}",
                        operation="get_slot_grid",
                    ),
                )
            grid = SlotGrid(**self._deserialise(dict(doc)))
            return StoreResult(success=True, data=grid)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(code="READ_ERROR", message=str(e), operation="get_slot_grid"),
            )

    def upsert_slot_grid(self, grid: SlotGrid) -> StoreResult[None]:
        try:
            serialised = self._serialise(grid.model_dump())
            Q = Query()
            self._grids.upsert(
                serialised,
                (Q.user_id == grid.user_id) & (Q.week_start == grid.week_start.isoformat()),
            )
            return StoreResult(success=True, data=None)
        except Exception as e:
            return StoreResult(
                success=False,
                error=StoreError(code="WRITE_ERROR", message=str(e), operation="upsert_slot_grid"),
            )