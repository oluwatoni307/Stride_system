# PATH: stride_backend/core/scheduling/tri_vector.py
# DOMAIN: Single source of truth for Tri-Vector weight computation
# (I × U × V, normalized) and corridor derivation. Extracted from
# api/routes/goals.py (Brief 030, Section 5.1) so that confirm_goal
# (single-goal call site) and the weekly cycle (cross-goal call site)
# share one implementation instead of two.
#
# Signature note: compute_tri_vector_weights takes goals_by_id (a dict,
# not a single Goal) so I/U are looked up per-milestone via its own
# parent goal, while avg_units and the final normalization are computed
# across the ENTIRE milestones list passed in — whatever scope the
# caller provides. confirm_goal passes only one goal's own milestones
# (goals_by_id = {goal.goal_id: goal}), reproducing the exact pre-Brief-030
# single-goal normalization. The weekly cycle passes every active
# milestone across every active goal for a user, achieving correct
# cross-goal normalization per the architecture doc's "Σ(W_raw across all
# ACTIVE milestones) = 1.0" rule.

from __future__ import annotations

from datetime import date
from typing import Dict, List

from core.config import FLOOR_FACTOR, SLOT_UNIT_CONSTANTS, URGENCY_BRACKETS
from core.schemas.entities import Goal, Milestone, Task


def compute_urgency(deadline: date) -> float:
    days_remaining = (deadline - date.today()).days
    for threshold, multiplier in URGENCY_BRACKETS:
        if days_remaining < threshold:
            return multiplier
    return 1.0


def compute_tri_vector_weights(
    milestones: List[Milestone],
    goals_by_id: Dict[str, Goal],
    task_graphs: Dict[str, List[Task]],
) -> Dict[str, float]:
    """
    Compute normalized tri_vector_weight for each milestone in `milestones`.
    I = parent goal's macro_impact (looked up via goals_by_id[m.goal_id])
    U = urgency multiplier from the parent goal's terminal_deadline
    V = slot units this milestone / avg slot units across ALL milestones
        passed in this call

    Normalization is global across the full `milestones` list — callers
    control scope by what they pass in (one goal's milestones, or every
    active milestone across every goal).

    A milestone whose goal_id isn't found in goals_by_id is skipped
    (not raised) — defensive, matches the dangling-reference skip
    convention in core/aggregation/consumed_units.py.
    """
    slot_units: Dict[str, int] = {}
    for m in milestones:
        tasks = task_graphs.get(m.milestone_id, [])
        total = sum(SLOT_UNIT_CONSTANTS.get(t.tag, 1) for t in tasks)
        slot_units[m.milestone_id] = total if total > 0 else 1

    avg_units = sum(slot_units.values()) / len(slot_units) if slot_units else 1.0

    raw_weights: Dict[str, float] = {}
    for m in milestones:
        goal = goals_by_id.get(m.goal_id)
        if goal is None:
            continue
        I = goal.macro_impact
        U = compute_urgency(goal.terminal_deadline)
        V = slot_units[m.milestone_id] / avg_units
        raw_weights[m.milestone_id] = I * U * V

    total = sum(raw_weights.values()) or 1.0
    return {mid: w / total for mid, w in raw_weights.items()}


def derive_corridor(
    normalized_weight: float,
    max_workable_hours: float,
) -> tuple[int, int]:
    weekly_units = round(max_workable_hours * 2.4)
    min_units = round(normalized_weight * weekly_units * FLOOR_FACTOR)
    max_units = round(normalized_weight * weekly_units)
    return max(min_units, 1), max(max_units, 1)