# PATH: stride_backend/core/execution/slot_allocator.py
# DOMAIN: SlotAllocator — real-time task pull engine.
# No LLM. No storage. Pure deterministic Python.

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from core.config import (
    DEEP_LOCKOUT_SENTINEL,
    MAX_CONSECUTIVE_PULLS,
    STALL_THRESHOLD_DAYS,
)
from core.schemas.contracts.execution_engine import (
    MilestoneAllocationData,
    QueuePullRequest,
    QueuePullResponse,
)
from core.schemas.contracts.shared import BoundaryError
from core.schemas.entities import Task
from core.schemas.enums import EnergyLevel, TaskStatus, TaskTag


class SlotAllocator:
    """
    Real-time task pull engine.

    Receives the current user state and active task pool.
    Returns the single best task to work on right now.

    Zero LLM calls. Zero storage imports.
    All inputs are passed by the API route.
    """

    def pull(
        self,
        request: QueuePullRequest,
        active_tasks: List[Task],
        milestone_data: List[MilestoneAllocationData],
        consumed_units: Dict[str, int],
    ) -> QueuePullResponse:
        """
        Determine and return the next task to pull.

        Args:
            request:        QueuePullRequest — last_task_tag, last_milestone_id,
                             and consecutive_pull_count are now server-VERIFIED
                             values computed by api/routes/tasks.py from
                             RawStore pull history (INF-03), not raw client
                             input. SlotAllocator itself is unchanged in how
                             it uses these fields — only their upstream
                             trustworthiness changed.
            active_tasks:   All AVAILABLE tasks for this user
            milestone_data: All ACTIVE milestones with min/max units
            consumed_units: Dict of milestone_id → units consumed this week

        Returns:
            QueuePullResponse with pulled_task and state_message
        """
        try:
            return self._run_pull(request, active_tasks, milestone_data, consumed_units)
        except Exception as e:
            return QueuePullResponse(
                pulled_task=None,
                state_message="NO_ELIGIBLE_TASKS",
                error=BoundaryError(
                    code="PULL_FAILURE",
                    message=f"SlotAllocator failed: {e}",
                    component="SlotAllocator",
                    retry_count=0,
                ),
            )

    def _run_pull(
        self,
        request: QueuePullRequest,
        active_tasks: List[Task],
        milestone_data: List[MilestoneAllocationData],
        consumed_units: Dict[str, int],
    ) -> QueuePullResponse:

        # Phase A — eligibility filter.
        # eligible_pre_ceiling is the pool right before the ceiling filter (filter 6)
        # runs. Comparing it against the final `eligible` pool lets Phase C tell
        # "ceiling filter emptied an otherwise-eligible pool" (-> ALL_CEILINGS_REACHED)
        # apart from "pool was already empty for other reasons" (-> NO_ELIGIBLE_TASKS).
        # Without this distinction, the ceiling filter removing every remaining task
        # in Phase A means Phase B never runs, and ALL_CEILINGS_REACHED could never
        # be reported even when every milestone has in fact hit its ceiling.
        eligible, eligible_pre_ceiling = self._filter_eligible(
            request, active_tasks, milestone_data, consumed_units
        )

        if not eligible:
            # DEEP lockout takes precedence as the most descriptive message
            if (request.last_task_tag == TaskTag.DEEP or
                    request.consecutive_pull_count == DEEP_LOCKOUT_SENTINEL):
                return QueuePullResponse(
                    pulled_task=None,
                    state_message="DEEP_LOCKOUT",
                )
            if eligible_pre_ceiling:
                return QueuePullResponse(
                    pulled_task=None,
                    state_message="ALL_CEILINGS_REACHED",
                )
            return QueuePullResponse(
                pulled_task=None,
                state_message="NO_ELIGIBLE_TASKS",
            )

        # Phase B — two-tier priority selection
        pulled_task, state_message = self._select_task(
            eligible, milestone_data, consumed_units
        )

        if pulled_task is None:
            return QueuePullResponse(
                pulled_task=None,
                state_message=state_message,
            )

        return QueuePullResponse(
            pulled_task=pulled_task,
            state_message=state_message,
            error=None,
        )

    # ── Phase A — Eligibility Filter ──────────────────────────────────────────

    def _filter_eligible(
        self,
        request: QueuePullRequest,
        active_tasks: List[Task],
        milestone_data: List[MilestoneAllocationData],
        consumed_units: Dict[str, int],
    ) -> Tuple[List[Task], List[Task]]:
        """
        Returns (eligible, eligible_pre_ceiling). See _run_pull for why both
        are needed.
        """

        # Build ceiling lookup
        ceiling_map: Dict[str, int] = {
            m.milestone_id: m.max_weekly_units for m in milestone_data
        }

        # Build completed-task lookup for dependency filter
        completed_ids = {
            t.task_id for t in active_tasks if t.status == TaskStatus.COMPLETED
        }

        # INF-03 (B-09): evaluated once per pull, not on a schedule — this
        # is the entire point of the fix. "now" is computed once here
        # rather than per-task so every task in this pull is judged
        # against the same instant.
        now = datetime.now(timezone.utc)

        eligible_pre_ceiling: List[Task] = []
        eligible: List[Task] = []

        for task in active_tasks:

            # Filters 1 & 2 — only AVAILABLE tasks proceed.
            # This also excludes SUPERSEDED tasks (replaced by breakdown tasks),
            # which the brief doesn't mention explicitly but which should never
            # be auto-pulled — they've been replaced by other tasks.
            if task.status != TaskStatus.AVAILABLE:
                continue

            # INF-03 (B-09): stagnation check. A task AVAILABLE for 7+ days
            # (STALL_THRESHOLD_DAYS) and still unpulled-to-completion gets
            # stalled_flag set to True on the Task object itself, mutated
            # in place. This is a flag, not an exclusion — the task STAYS
            # in the eligible pool (see _run_pull / _select_task, neither
            # of which is changed by this), so that if it's the one
            # ultimately pulled, the client receives stalled_flag=True on
            # pulled_task and can offer the force-pull-or-breakdown choice
            # (Flow 8 — out of scope for INF-03, per EM decision: this
            # brief stops at "the flag appears in the response", nothing
            # more). first_made_available_at is None for any task that has
            # never transitioned to AVAILABLE (defensive — should not
            # happen for a task already confirmed AVAILABLE above, but a
            # missing timestamp must never crash a pull).
            if task.first_made_available_at is not None:
                available_for = now - task.first_made_available_at
                if available_for.days >= STALL_THRESHOLD_DAYS:
                    task.stalled_flag = True

            # Filter 3 — dependency guard: all dependencies must be COMPLETED
            if task.dependencies:
                unmet = [dep for dep in task.dependencies if dep not in completed_ids]
                if unmet:
                    continue

            # Filter 4 — DEEP lockout
            if request.last_task_tag == TaskTag.DEEP:
                if task.tag == TaskTag.DEEP:
                    continue

            # Filter 5 — energy filter (skipped if force_pull)
            if not request.force_pull:
                if request.current_energy_level != EnergyLevel.HIGH:
                    if task.tag == TaskTag.DEEP:
                        continue

            # Filter 7 — clumping filter (force rotation after MAX_CONSECUTIVE_PULLS)
            if (request.consecutive_pull_count >= MAX_CONSECUTIVE_PULLS and
                    request.last_milestone_id is not None):
                if task.milestone_id == request.last_milestone_id:
                    continue

            # Filter 8 — DEEP sentinel check (force milestone rotation)
            if request.consecutive_pull_count == DEEP_LOCKOUT_SENTINEL:
                if task.milestone_id == request.last_milestone_id:
                    continue

            eligible_pre_ceiling.append(task)

            # Filter 6 — ceiling filter
            milestone_id = task.milestone_id
            consumed = consumed_units.get(milestone_id, 0)
            ceiling = ceiling_map.get(milestone_id, 0)
            if ceiling > 0 and consumed >= ceiling:
                continue

            eligible.append(task)

        return eligible, eligible_pre_ceiling

    # ── Phase B — Two-Tier Priority Selection ─────────────────────────────────

    def _select_task(
        self,
        eligible: List[Task],
        milestone_data: List[MilestoneAllocationData],
        consumed_units: Dict[str, int],
    ) -> Tuple[Optional[Task], str]:

        # Build eligible milestone set
        eligible_milestone_ids = {t.milestone_id for t in eligible}

        # Tier 1 — Safety Net: find starved milestones
        starved = [
            m for m in milestone_data
            if m.milestone_id in eligible_milestone_ids
            and m.min_weekly_units > 0
            and consumed_units.get(m.milestone_id, 0) < m.min_weekly_units
        ]

        if starved:
            # Sort by floor deficit ascending — most behind gets priority
            starved.sort(
                key=lambda m: consumed_units.get(m.milestone_id, 0) / m.min_weekly_units
            )
            target_milestone_id = starved[0].milestone_id
            task = self._first_task_for_milestone(eligible, target_milestone_id)
            return task, "PULLING"

        # Tier 2 — Growth Phase: all milestones above floor
        safe = [
            m for m in milestone_data
            if m.milestone_id in eligible_milestone_ids
            and consumed_units.get(m.milestone_id, 0) < m.max_weekly_units
        ]

        if not safe:
            return None, "ALL_CEILINGS_REACHED"

        # Sort by ceiling progress ascending — furthest from ceiling gets priority
        safe.sort(
            key=lambda m: consumed_units.get(m.milestone_id, 0) / m.max_weekly_units
        )
        target_milestone_id = safe[0].milestone_id
        task = self._first_task_for_milestone(eligible, target_milestone_id)
        return task, "MINIMUMS_MET"

    def _first_task_for_milestone(
        self,
        eligible: List[Task],
        milestone_id: str,
    ) -> Optional[Task]:
        """Return the first eligible task belonging to the target milestone."""
        for task in eligible:
            if task.milestone_id == milestone_id:
                return task
        return None