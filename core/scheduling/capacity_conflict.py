# PATH: stride_backend/core/scheduling/capacity_conflict.py
# DOMAIN: B-03 capacity conflict check — runs at goal confirmation (confirm_goal),
# never at structure_goal. Locked formula: new_total_min_weekly_units >
# max_workable_hours x 3. See goal_structuring.py Boundary1Output.conflict_flag
# for the SEPARATE, model-generated prose signal — that field is advisory only
# and must never be treated as a substitute for this deterministic check.

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from core.schemas.entities import Milestone


@dataclass
class CapacityConflictDetail:
    milestone_id: str
    description: str
    min_weekly_units: int


class CapacityConflictError(Exception):
    """
    Raised by check_capacity_conflict when a user's total committed
    min_weekly_units (existing ACTIVE milestones + the milestones from the
    goal being confirmed) would exceed max_workable_hours x 3.

    Carries enough structured detail for api/routes/goals.py to build a 409
    response body that names the offending milestone(s) by id and
    description, as required by the Layer A evaluator.
    """

    def __init__(
        self,
        new_total_min_weekly_units: int,
        threshold: float,
        max_workable_hours: float,
        breaching_milestones: List[CapacityConflictDetail],
    ) -> None:
        self.new_total_min_weekly_units = new_total_min_weekly_units
        self.threshold = threshold
        self.max_workable_hours = max_workable_hours
        self.breaching_milestones = breaching_milestones

        names = ", ".join(
            f"{m.description!r} ({m.min_weekly_units} units)"
            for m in breaching_milestones
        )
        message = (
            f"Capacity conflict: confirming this goal would bring total "
            f"committed weekly units to {new_total_min_weekly_units}, "
            f"exceeding the threshold of {threshold:g} "
            f"(max_workable_hours={max_workable_hours:g} x 3). "
            f"New milestone(s) contributing to the breach: {names}."
        )
        super().__init__(message)
        self.message = message


def check_capacity_conflict(
    existing_active_min_weekly_units: int,
    new_milestones: List[Milestone],
    max_workable_hours: float,
) -> None:
    """
    Deterministic B-03 check. Locked formula — do not alter:

        new_total_min_weekly_units > max_workable_hours x 3  =>  conflict

    `existing_active_min_weekly_units` is the sum of min_weekly_units across
    the user's ALREADY-ACTIVE milestones (other goals), so that confirming
    several goals in sequence is correctly evaluated cumulatively rather
    than each goal being checked in isolation against an empty baseline.

    `new_milestones` must already have real (post-derive_corridor)
    min_weekly_units populated — this function does not compute them.

    Raises CapacityConflictError if the threshold is breached. Returns None
    (no return value) on pass — caller proceeds with persistence as normal.
    """
    new_milestones_total = sum(m.min_weekly_units for m in new_milestones)
    new_total_min_weekly_units = (
        existing_active_min_weekly_units + new_milestones_total
    )
    threshold = max_workable_hours * 3

    if new_total_min_weekly_units > threshold:
        breaching = [
            CapacityConflictDetail(
                milestone_id=m.milestone_id,
                description=m.description,
                min_weekly_units=m.min_weekly_units,
            )
            for m in new_milestones
            if m.min_weekly_units > 0
        ]
        raise CapacityConflictError(
            new_total_min_weekly_units=new_total_min_weekly_units,
            threshold=threshold,
            max_workable_hours=max_workable_hours,
            breaching_milestones=breaching,
        )