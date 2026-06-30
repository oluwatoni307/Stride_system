# PATH: stride_backend/api/routes/tasks.py
# DOMAIN: Task execution routes — pull and complete

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agents.model_agent.executor import ModelAgentExecutor
from api.dependencies import (
    get_distilled_store,
    get_goal_store,
    get_raw_store,
    get_slot_allocator,
)
from core.aggregation.consumed_units import compute_consumed_units
from core.config import SLOT_UNIT_CONSTANTS
from core.execution.slot_allocator import SlotAllocator
from core.feedback.feedback_loop import FeedbackLoop
from core.schemas.contracts.execution_engine import (
    MilestoneAllocationData,
    QueuePullRequest,
)
from core.schemas.contracts.feedback_loop import Boundary3Input
from core.schemas.entities import PullEvent
from core.schemas.enums import EnergyLevel, TaskStatus, TaskTag
from storage.distilled_store import DistilledStore
from storage.goal_store import GoalStore
from storage.raw_store import RawStore

router = APIRouter(prefix="/tasks", tags=["tasks"])

# ── Request / Response models ────────────────────────────────────────────────

class PullTaskRequest(BaseModel):
    user_id: str
    current_energy_level: str          # "HIGH" | "MEDIUM" | "LOW"
    # INF-03 (B-05, B-06): last_task_tag, last_milestone_id, and
    # consecutive_pull_count are now ADVISORY ONLY — kept on the request
    # model for backward compatibility with existing callers (the runner /
    # persona scripts may still send consecutive_pull_count), but pull_task
    # below no longer forwards them to SlotAllocator. The server derives
    # its own verified values from RawStore.get_pull_history() instead.
    # Per INF-03's explicit constraint: "do not trust the client to report
    # this correctly." Nothing here was removed from the schema — only the
    # route's use of these fields changed.
    last_task_tag: Optional[str] = None
    last_milestone_id: Optional[str] = None
    consecutive_pull_count: int = 0
    force_pull: bool = False


class CompleteTaskRequest(BaseModel):
    user_id: str
    task_id: str
    goal_id: str
    milestone_id: str
    completion_timestamp: Optional[str] = None
    user_note: Optional[str] = None


# ── Helpers ────────────────────────────────────────────────────────────────────
# _get_consumed_units removed (Brief 030) — its unfiltered, full-history scan
# is replaced by core.aggregation.consumed_units.compute_consumed_units,
# scoped to the current week. See that module for the single source of
# truth; weekly.py's _build_weekly_summary uses the same function.

def _get_milestone_allocation_data(
    user_id: str,
    goal_store: GoalStore,
) -> list[MilestoneAllocationData]:
    """
    Fetch all ACTIVE milestones and return as MilestoneAllocationData list.
    """
    result = goal_store.get_active_milestones_by_user(user_id)
    if not result.success:
        return []

    return [
        MilestoneAllocationData(
            milestone_id=m.milestone_id,
            tri_vector_weight=m.tri_vector_weight,
            min_weekly_units=m.min_weekly_units,
            max_weekly_units=m.max_weekly_units,
        )
        for m in result.data
    ]


def _derive_verified_pull_state(raw_store: RawStore, user_id: str):
    """
    INF-03 (B-05, B-06): compute the server's own ground truth for
    last_task_tag, last_milestone_id, and consecutive_pull_count from
    RawStore's pull history, instead of trusting whatever a client sends.

    Returns (last_task_tag: Optional[TaskTag], last_milestone_id: Optional[str],
             consecutive_pull_count: int).

    last_task_tag — the tag of the single most recent pull, or None if
    this user has never pulled before. Because pull history is recorded
    on EVERY successful pull (not just DEEP ones), "the last pull was
    non-DEEP" is directly visible as the most recent entry's tag — which
    is exactly what "lockout resets after one non-DEEP pull" (B-05's
    constraint) means: no separate reset bookkeeping is needed, the
    history itself already encodes it.

    last_milestone_id / consecutive_pull_count — derived together by
    scanning backwards from the most recent pull while the milestone_id
    stays the same. If the last pull was milestone X and the one before
    it was also X, consecutive_pull_count=2 and last_milestone_id=X. If
    the last pull was X but the prior one was Y, consecutive_pull_count=1.
    This is a genuine per-milestone streak, not a global pull counter —
    which is what B-06 requires.
    """
    history_result = raw_store.get_pull_history(user_id)
    if not history_result.success or not history_result.data.recent_pulls:
        return None, None, 0

    recent = history_result.data.recent_pulls  # oldest-first
    last_event = recent[-1]
    last_task_tag = last_event.tag
    last_milestone_id = last_event.milestone_id

    consecutive = 0
    for event in reversed(recent):
        if event.milestone_id == last_milestone_id:
            consecutive += 1
        else:
            break

    return last_task_tag, last_milestone_id, consecutive


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/pull")
async def pull_task(
    request: PullTaskRequest,
    goal_store: GoalStore = Depends(get_goal_store),
    raw_store: RawStore = Depends(get_raw_store),
    slot_allocator: SlotAllocator = Depends(get_slot_allocator),
):
    """
    Flow 2 — Pull next task for the user based on current energy level.

    INF-03: last_task_tag / last_milestone_id / consecutive_pull_count are
    now derived server-side from RawStore pull history (see
    _derive_verified_pull_state), not taken from the request body. The
    request fields still exist on PullTaskRequest for backward
    compatibility but are no longer read here.
    """
    # Validate energy level
    try:
        energy = EnergyLevel(request.current_energy_level.upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid energy level: {request.current_energy_level}",
        )

    # INF-03 (B-05, B-06): server-verified pull state, replacing the old
    # direct pass-through of request.last_task_tag / last_milestone_id /
    # consecutive_pull_count. See _derive_verified_pull_state for why this
    # is computed from RawStore rather than trusted from the client.
    verified_last_tag, verified_last_milestone_id, verified_consecutive = (
        _derive_verified_pull_state(raw_store, request.user_id)
    )

    # Build pull request
    pull_request = QueuePullRequest(
        user_id=request.user_id,
        current_energy_level=energy,
        last_task_tag=verified_last_tag,
        last_milestone_id=verified_last_milestone_id,
        consecutive_pull_count=verified_consecutive,
        force_pull=request.force_pull,
    )

    # Fetch active tasks and milestone data
    active_tasks_result = goal_store.get_available_tasks_by_user(request.user_id)
    active_tasks = active_tasks_result.data if active_tasks_result.success else []

    milestone_data = _get_milestone_allocation_data(request.user_id, goal_store)

    # consumed_units scoped to the current week (Brief 030) — was previously
    # an unfiltered full-history scan via the now-deleted _get_consumed_units.
    current_week_start = date.today() - timedelta(days=date.today().weekday())
    consumed_units = compute_consumed_units(
        user_id=request.user_id,
        week_start=current_week_start,
        goal_store=goal_store,
        raw_store=raw_store,
    )

    # Run SlotAllocator
    response = slot_allocator.pull(
        request=pull_request,
        active_tasks=active_tasks,
        milestone_data=milestone_data,
        consumed_units=consumed_units,
    )

    if response.error:
        raise HTTPException(status_code=500, detail=response.error.message)

    # INF-04 (B-09): SlotAllocator._filter_eligible mutates stalled_flag on
    # the in-memory Task objects inside active_tasks during eligibility
    # filtering (any AVAILABLE task whose first_made_available_at is 7+
    # days old gets stalled_flag=True), but SlotAllocator has zero storage
    # imports by design — that mutation never reaches storage on its own.
    # Without this write-back, the flag is only ever visible in the HTTP
    # response if the exact task that crossed the threshold also happens
    # to be the one _select_task chooses THIS pull (response.pulled_task
    # is one of these same objects), and even then the next /tasks/pull
    # re-fetches active_tasks fresh from storage and the flag reverts to
    # whatever's actually persisted (False) — so it would also fail to
    # show up reliably across calls. Persist every task whose flag is now
    # True so the state is durable in storage regardless of which task
    # gets pulled this time. Runs whether or not a task was pulled this
    # turn (e.g. DEEP_LOCKOUT can still leave stalled non-DEEP tasks sitting
    # in active_tasks that deserve to have their flag saved).
    for task in active_tasks:
        if task.stalled_flag:
            write_result = goal_store.upsert_task(task)
            if not write_result.success:
                raise HTTPException(
                    status_code=500, detail=write_result.error.message
                )

    # INF-03 (B-05, B-06): record this pull as the new most-recent history
    # entry, so the NEXT pull's _derive_verified_pull_state call sees it.
    # Only recorded when a task was actually pulled — a pull that returns
    # no task (DEEP_LOCKOUT, ALL_CEILINGS_REACHED, NO_ELIGIBLE_TASKS) has
    # nothing to record and must not reset or advance the streak.
    if response.pulled_task is not None:
        raw_store.record_pull(
            user_id=request.user_id,
            task_id=response.pulled_task.task_id,
            tag=response.pulled_task.tag,
            milestone_id=response.pulled_task.milestone_id,
            pulled_at=datetime.now(timezone.utc),
        )

    return {
        "pulled_task": (
            response.pulled_task.model_dump()
            if response.pulled_task else None
        ),
        "state_message": response.state_message,
    }


@router.post("/complete")
async def complete_task(
    request: CompleteTaskRequest,
    goal_store: GoalStore = Depends(get_goal_store),
    raw_store: RawStore = Depends(get_raw_store),
    distilled_store: DistilledStore = Depends(get_distilled_store),
):
    """
    Flow 3 — Mark task as complete. Writes FeedbackEvent, updates task status.
    """
    # Verify task exists
    task_result = goal_store.get_task(request.task_id)
    if not task_result.success:
        raise HTTPException(
            status_code=404,
            detail=f"Task {request.task_id} not found.",
        )

    # Package completion event
    feedback_loop = FeedbackLoop()
    boundary_input = feedback_loop.package_completion_event(
        user_id=request.user_id,
        task_id=request.task_id,
        goal_id=request.goal_id,
        milestone_id=request.milestone_id,
        completion_timestamp=request.completion_timestamp,
        user_note=request.user_note,
    )

    # Process via ModelAgentExecutor
    executor = ModelAgentExecutor(
        raw_store=raw_store,
        distilled_store=distilled_store,
        goal_store=goal_store,
        llm=None,   # not needed for task completion — no LLM call
    )

    output = await executor.process_task_completion(boundary_input)

    if output.error:
        raise HTTPException(status_code=500, detail=output.error.message)

    # Unlock dependent tasks
    # INF-03 (B-09): stamp first_made_available_at the moment a task
    # transitions to AVAILABLE here — this is the second of the two
    # transition points (the other is _resolve_dependencies in
    # api/routes/goals.py, for tasks AVAILABLE from initial creation).
    all_tasks_result = goal_store.get_tasks_by_milestone(request.milestone_id)
    if all_tasks_result.success:
        now = datetime.now(timezone.utc)
        for task in all_tasks_result.data:
            if task.status == TaskStatus.PENDING:
                unmet = [
                    dep for dep in task.dependencies
                    if dep != request.task_id
                    and goal_store.get_task(dep).data.status != TaskStatus.COMPLETED
                    if goal_store.get_task(dep).success
                ]
                if not unmet:
                    task.status = TaskStatus.AVAILABLE
                    task.first_made_available_at = now
                    goal_store.upsert_task(task)

    return {
        "task_id": request.task_id,
        "success": output.success,
        "state": "COMPLETED",
    }