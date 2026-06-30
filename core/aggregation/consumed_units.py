# PATH: stride_backend/core/aggregation/consumed_units.py
# DOMAIN: Single source of truth for computing consumed_units per milestone,
# scoped to a given week. Replaces the two independent, unfiltered
# implementations previously in weekly.py and tasks.py.

from __future__ import annotations

from datetime import date, timedelta, timezone
from typing import Dict

from core.config import SLOT_UNIT_CONSTANTS
from storage.goal_store import GoalStore
from storage.raw_store import RawStore


def compute_consumed_units(
    user_id: str,
    week_start: date,
    goal_store: GoalStore,
    raw_store: RawStore,
) -> Dict[str, int]:
    """
    Returns {milestone_id: consumed_units} for COMPLETED tasks whose
    FeedbackEvent.completed_at falls within [week_start, week_start + 7 days).

    Source of truth is FeedbackEvent.completed_at (RawStore), not Task.status
    alone — Task carries no timestamp by design (current-state only).
    A task's slot-unit cost (tag → units) still comes from the Task entity
    itself, joined by task_id.
    """
    week_end = week_start + timedelta(days=7)

    raw_result = raw_store.get(user_id)
    if not raw_result.success:
        return {}

    tasks_result = goal_store.get_tasks_by_user(user_id)
    if not tasks_result.success:
        return {}

    tag_by_task_id = {t.task_id: t.tag for t in tasks_result.data}

    consumed: Dict[str, int] = {}

    for event in raw_result.data.feedback_events:
        completed_date = event.completed_at
        if completed_date.tzinfo is None:
            completed_date = completed_date.replace(tzinfo=timezone.utc)

        event_date = completed_date.date()
        if not (week_start <= event_date < week_end):
            continue

        tag = tag_by_task_id.get(event.task_id)
        if tag is None:
            # FeedbackEvent references a task no longer present — skip,
            # do not raise. Defensive: tasks are never hard-deleted per
            # architecture doc (SUPERSEDED is a soft-delete status), but
            # don't let a dangling reference break weekly aggregation.
            continue

        units = SLOT_UNIT_CONSTANTS.get(tag, 1)
        consumed[event.milestone_id] = consumed.get(event.milestone_id, 0) + units

    return consumed