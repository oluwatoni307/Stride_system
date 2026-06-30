# PATH: stride_backend/core/scheduling/scheduling_component.py
# DOMAIN: SchedulingComponent — deterministic DEEP session planner.
# No LLM. No storage. Pure Python.

from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Dict, List, Tuple

from core.schemas.contracts.execution_engine import (
    DeepSessionPlan,
    MilestoneAllocationData,
    SlotAllocationInput,
    SlotAllocationOutput,
)
from core.schemas.contracts.shared import BoundaryError
from core.schemas.enums import EnergyLevel, TaskTag
from core.config import DEEP_MIN_GAP_DAYS, SLOT_UNIT_CONSTANTS


DAY_INDEX: Dict[str, int] = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}

DAY_FROM_INDEX: Dict[int, str] = {v: k for k, v in DAY_INDEX.items()}


@dataclass
class _EligibleWindow:
    """Internal representation of a HIGH-energy slot."""
    day: str
    day_index: int
    start_time: str
    taken: bool = False


class SchedulingComponent:
    """
    Deterministic DEEP session planner.

    Receives the user's SlotGrid and active milestone data.
    Returns a DeepSessionPlan per milestone indicating which days
    are designated for DEEP work.

    Zero LLM calls. Zero storage imports.
    The session plan is a guide — not a hard constraint on task pulling.
    """

    def allocate_slots(self, input: SlotAllocationInput) -> SlotAllocationOutput:
        """
        Main entry point. Synchronous — no async needed (pure computation).

        Args:
            input: SlotAllocationInput containing active milestone data,
                   SlotGrid, and week metadata.

        Returns:
            SlotAllocationOutput with a DeepSessionPlan per milestone.
        """
        try:
            plans = self._run_allocation(input)
            return SlotAllocationOutput(
                user_id=input.user_id,
                week_start=input.week_start,
                deep_session_plans=plans,
                error=None,
            )
        except Exception as e:
            return SlotAllocationOutput(
                user_id=input.user_id,
                week_start=input.week_start,
                deep_session_plans=[],
                error=BoundaryError(
                    code="ALLOCATION_FAILURE",
                    message=f"SchedulingComponent failed: {e}",
                    component="SchedulingComponent",
                    retry_count=0,
                ),
            )

    def _run_allocation(self, input: SlotAllocationInput) -> List[DeepSessionPlan]:
        # Step 1 — extract and sort HIGH energy windows
        eligible_windows = self._extract_eligible_windows(input.slot_grid)

        if not eligible_windows:
            # No HIGH energy windows at all this week. Milestones with a
            # real allocation (max_weekly_units > 0) get partial_allocation;
            # zero-unit milestones stay cleanly skipped (no allocation owed).
            plans: List[DeepSessionPlan] = []
            for m in input.milestones:
                needed = self._sessions_needed(m, available_windows=0)
                plans.append(DeepSessionPlan(
                    milestone_id=m.milestone_id,
                    assigned_days=[],
                    sessions_planned=0,
                    sessions_needed=needed,
                    partial_allocation=needed > 0,
                ))
            return plans

        # Step 2 — sort milestones by weight descending (highest priority first)
        milestones = sorted(
            input.milestones,
            key=lambda m: m.tri_vector_weight,
            reverse=True,
        )

        plans: List[DeepSessionPlan] = []

        for milestone in milestones:
            if milestone.max_weekly_units == 0:
                plans.append(DeepSessionPlan(
                    milestone_id=milestone.milestone_id,
                    assigned_days=[],
                    sessions_planned=0,
                    sessions_needed=0,
                    partial_allocation=False,
                ))
                continue

            needed = self._sessions_needed(
                milestone, available_windows=len(eligible_windows)
            )
            assigned_days, sessions_assigned = self._greedy_assign(
                eligible_windows, needed
            )
            partial = sessions_assigned < needed

            plans.append(DeepSessionPlan(
                milestone_id=milestone.milestone_id,
                assigned_days=assigned_days,
                sessions_planned=sessions_assigned,
                sessions_needed=needed,
                partial_allocation=partial,
            ))

        return plans

    def _extract_eligible_windows(self, slot_grid: dict) -> List[_EligibleWindow]:
        """
        Parse SlotGrid dict and return HIGH energy windows sorted by day then time.
        """
        slots = slot_grid.get("slots", [])
        windows: List[_EligibleWindow] = []

        for slot in slots:
            energy = str(slot.get("energy_level", "")).upper()
            if energy != EnergyLevel.HIGH.value:
                continue
            day = slot.get("day", "")
            if day not in DAY_INDEX:
                continue
            windows.append(_EligibleWindow(
                day=day,
                day_index=DAY_INDEX[day],
                start_time=slot.get("start_time", "00:00"),
            ))

        # Sort by day_index then start_time
        windows.sort(key=lambda w: (w.day_index, w.start_time))
        return windows

    def _sessions_needed(
        self, milestone: MilestoneAllocationData, available_windows: int
    ) -> int:
        """
        Compute how many DEEP sessions a milestone needs this week.
        Based on max_weekly_units and DEEP slot cost, minimum 1 if the
        milestone has any allocation, and capped by the count of HIGH
        energy windows available this week (spec Step 2). When there are
        zero windows available at all, the cap is intentionally skipped
        here so the resulting plan still reflects unmet demand (the
        caller marks partial_allocation accordingly) rather than reporting
        a misleading "0 needed".
        """
        max_units = milestone.max_weekly_units
        if max_units == 0:
            return 0
        deep_cost = SLOT_UNIT_CONSTANTS[TaskTag.DEEP]
        needed = max(1, floor(max_units / deep_cost))
        if available_windows > 0:
            needed = min(needed, available_windows)
        return needed

    def _greedy_assign(
        self,
        windows: List[_EligibleWindow],
        sessions_needed: int,
    ) -> Tuple[List[str], int]:
        """
        Greedy interval scheduling with DEEP_MIN_GAP_DAYS cooldown.
        Mutates window.taken in place — shared pool across milestones.

        Returns:
            (assigned_days, sessions_assigned)
        """
        last_day_index = -99    # sentinel — no prior assignment
        sessions_assigned = 0
        assigned_days: List[str] = []

        for window in windows:
            if window.taken:
                continue

            gap = window.day_index - last_day_index
            if gap < DEEP_MIN_GAP_DAYS:
                continue

            # Valid window
            window.taken = True
            assigned_days.append(window.day)
            last_day_index = window.day_index
            sessions_assigned += 1

            if sessions_assigned == sessions_needed:
                break

        # Fallback — if nothing assigned, take any free window ignoring gap
        if sessions_assigned == 0 and sessions_needed > 0:
            for window in windows:
                if not window.taken:
                    window.taken = True
                    assigned_days.append(window.day)
                    sessions_assigned = 1
                    break

        return assigned_days, sessions_assigned