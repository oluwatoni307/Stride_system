# PATH: stride_backend/core/scheduling/slot_grid_generator.py
# DOMAIN: Pure Python expansion of OnboardingProfile energy blocks into a
# fully populated SlotGrid at SLOT_DURATION_MINUTES granularity.
# Zero LLM calls. Never writes to storage — returns a SlotGrid, caller writes it.

from __future__ import annotations

from datetime import date, datetime, timedelta

from core.config import SLOT_DURATION_MINUTES
from core.schemas.entities import OnboardingProfile, SlotGrid, TimeSlot

_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_WEEKEND_DAYS = {"Saturday", "Sunday"}


def _parse_time(s: str) -> datetime:
    return datetime.strptime(s, "%H:%M")


def _format_time(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def generate_slot_grid(profile: OnboardingProfile, week_start: date) -> SlotGrid:
    if not profile.weekday_blocks or not profile.weekend_blocks:
        raise ValueError(
            "OnboardingProfile must have non-empty weekday_blocks and "
            "weekend_blocks before SlotGrid generation — this should have "
            "been rejected at validation."
        )

    slots: list[TimeSlot] = []
    step = timedelta(minutes=SLOT_DURATION_MINUTES)

    for day_name in _DAY_NAMES:
        blocks = profile.weekend_blocks if day_name in _WEEKEND_DAYS else profile.weekday_blocks

        for block in blocks:
            current = _parse_time(block.start_time)
            end = _parse_time(block.end_time)

            while current + step <= end:
                slots.append(TimeSlot(
                    day=day_name,
                    start_time=_format_time(current),
                    energy_level=block.energy_level,
                ))
                current += step

    return SlotGrid(
        user_id=profile.user_id,
        week_start=week_start,
        slots=slots,
        schema_version=1,
    )