# PATH: stride_backend/core/validation/onboarding.py
# DOMAIN: Pure validation rules for OnboardingProfile — no FastAPI/HTTPException
# dependency, so this is unit-testable in isolation. Route layer translates
# a failed StoreResult into HTTPException(400, ...).

from __future__ import annotations

from typing import List, Optional

from core.schemas.entities import EnergyBlock, OnboardingProfile
from storage.store_types import StoreError, StoreResult


def _check_overlaps(blocks: List[EnergyBlock], block_set_name: str) -> Optional[StoreError]:
    """
    Sort blocks by start_time, then confirm each adjacent pair satisfies
    block[i].end_time <= block[i+1].start_time. Returns a StoreError on the
    first overlap found, or None if no overlaps exist.
    """
    sorted_blocks = sorted(blocks, key=lambda b: b.start_time)
    for i in range(len(sorted_blocks) - 1):
        current = sorted_blocks[i]
        nxt = sorted_blocks[i + 1]
        if current.end_time > nxt.start_time:
            return StoreError(
                code="ENERGY_BLOCK_OVERLAP",
                message=(
                    f"Block '{current.label}' ({current.start_time}-{current.end_time}) "
                    f"overlaps with '{nxt.label}' ({nxt.start_time}-{nxt.end_time}) "
                    f"in {block_set_name}"
                ),
                operation="validate_onboarding_profile",
            )
    return None


def validate_onboarding_profile(profile: OnboardingProfile) -> StoreResult[None]:
    """
    Enforces Brief 029 Section 1.1 validation rules:
      1. max_workable_hours must be > 0
      2. weekday_blocks and weekend_blocks must each contain >= 1 block
      3/4/5. No overlapping blocks within weekday_blocks, independently
             within weekend_blocks — rejected, never silently resolved
             by precedence
      6. Gaps between blocks are allowed (no check needed — absence of
         a TimeSlot in a gap is the expected behavior, enforced by
         SlotGridGenerator, not here)
    """
    if profile.max_workable_hours <= 0:
        return StoreResult(
            success=False,
            error=StoreError(
                code="INVALID_INPUT",
                message="max_workable_hours must be > 0",
                operation="validate_onboarding_profile",
            ),
        )

    if not profile.weekday_blocks:
        return StoreResult(
            success=False,
            error=StoreError(
                code="INVALID_INPUT",
                message="weekday_blocks must contain at least 1 block",
                operation="validate_onboarding_profile",
            ),
        )

    if not profile.weekend_blocks:
        return StoreResult(
            success=False,
            error=StoreError(
                code="INVALID_INPUT",
                message="weekend_blocks must contain at least 1 block",
                operation="validate_onboarding_profile",
            ),
        )

    weekday_overlap = _check_overlaps(profile.weekday_blocks, "weekday_blocks")
    if weekday_overlap:
        return StoreResult(success=False, error=weekday_overlap)

    weekend_overlap = _check_overlaps(profile.weekend_blocks, "weekend_blocks")
    if weekend_overlap:
        return StoreResult(success=False, error=weekend_overlap)

    return StoreResult(success=True, data=None)