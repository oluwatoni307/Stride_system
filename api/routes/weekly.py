# PATH: stride_backend/api/routes/weekly.py
# DOMAIN: Weekly cycle route — guidance generation + state reset

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agents.model_agent.executor import ModelAgentExecutor
from api.dependencies import (
    get_distilled_store,
    get_goal_store,
    get_onboarding_store,
    get_raw_store,
)
from core.aggregation.consumed_units import compute_consumed_units
from core.config import settings
from core.scheduling.slot_grid_generator import generate_slot_grid
from core.scheduling.tri_vector import compute_tri_vector_weights, derive_corridor
from core.schemas.contracts.execution_engine import (
    MilestoneUtilization,
    WeeklyAggregatedSummary,
)
from core.schemas.enums import GoalStatus, TaskTag
from storage.distilled_store import DistilledStore
from storage.goal_store import GoalStore
from storage.onboarding_store import OnboardingStore
from storage.raw_store import RawStore

router = APIRouter(prefix="/weekly", tags=["weekly"])


# ── Request model ──────────────────────────────────────────────────────────────

class WeeklyCycleRequest(BaseModel):
    user_id: str
    week_start: str     # ISO date string e.g. "2025-06-02"


# ── Expiry check ───────────────────────────────────────────────────────────────

def _expire_overdue_goals(
    user_id: str,
    week_start: str,
    goal_store: GoalStore,
) -> List[str]:
    """
    Fix 4A — Brief PROMPT-01.
    Before building the weekly summary, check every ACTIVE goal whose
    terminal_deadline has passed. Mark it EXPIRED so:
      - it is excluded from utilization calculations
      - the guidance prompt can surface a closure/extension prompt to the user

    Returns a list of expired goal_ids so the weekly route can pass them
    to the guidance prompt as context.

    Runs after Track B (weights are current) and before _build_weekly_summary
    (so expired goals don't appear in goals_below_floor or milestone_utilization).
    """
    week_start_date = date.fromisoformat(week_start)
    expired_goal_ids: List[str] = []

    active_goals_result = goal_store.get_active_goals(user_id)
    if not active_goals_result.success:
        return expired_goal_ids

    for goal in active_goals_result.data:
        if goal.terminal_deadline is None:
            continue
        deadline = (
            goal.terminal_deadline
            if isinstance(goal.terminal_deadline, date)
            else date.fromisoformat(str(goal.terminal_deadline))
        )
        if deadline < week_start_date:
            goal.status = GoalStatus.EXPIRED
            goal_store.upsert_goal(goal)
            expired_goal_ids.append(goal.goal_id)

    return expired_goal_ids


# ── Aggregation helper ─────────────────────────────────────────────────────────

def _build_weekly_summary(
    user_id: str,
    week_start: str,
    goal_store: GoalStore,
    raw_store: RawStore,
) -> WeeklyAggregatedSummary:
    """
    Python aggregates raw data into a typed summary, scoped to the given
    week. LLM reads this summary — never raw events.

    consumed_units, tasks_completed, deep_work_sessions, and
    mechanical_bias_pct are all sourced from FeedbackEvent.completed_at
    (via RawStore), filtered to [week_start, week_start + 7 days) — not
    from an unfiltered Task.status scan (Brief 030, fixes a real bug:
    a task completed in week 1 was still counting toward week 8's totals).
    tasks_stalled stays a full Task scan, unchanged in meaning —
    stalled_flag is a current-state flag with no time dimension to filter on.
    """
    week_start_date = date.fromisoformat(week_start)
    week_end_date = week_start_date + timedelta(days=7)

    milestones_result = goal_store.get_active_milestones_by_user(user_id)
    milestones = milestones_result.data if milestones_result.success else []

    consumed = compute_consumed_units(
        user_id=user_id,
        week_start=week_start_date,
        goal_store=goal_store,
        raw_store=raw_store,
    )

    raw_result = raw_store.get(user_id)
    events_this_week = []
    if raw_result.success:
        for event in raw_result.data.feedback_events:
            completed_date = event.completed_at
            if completed_date.tzinfo is None:
                completed_date = completed_date.replace(tzinfo=timezone.utc)
            if week_start_date <= completed_date.date() < week_end_date:
                events_this_week.append(event)

    tasks_result = goal_store.get_tasks_by_user(user_id)
    all_tasks = tasks_result.data if tasks_result.success else []
    tag_by_task_id = {t.task_id: t.tag for t in all_tasks}
    stalled_count = sum(1 for t in all_tasks if t.stalled_flag)

    tasks_completed = len(events_this_week)
    deep_work_sessions = sum(
        1 for e in events_this_week
        if tag_by_task_id.get(e.task_id) == TaskTag.DEEP
    )
    mechanical_completed = sum(
        1 for e in events_this_week
        if tag_by_task_id.get(e.task_id) == TaskTag.MECHANICAL
    )
    mechanical_bias_pct = (
        mechanical_completed / tasks_completed if tasks_completed > 0 else 0.0
    )

    # Build milestone utilization
    milestone_utilization: List[MilestoneUtilization] = []
    goals_below_floor: List[str] = []

    for m in milestones:
        consumed_units = consumed.get(m.milestone_id, 0)
        max_units = m.max_weekly_units if m.max_weekly_units > 0 else 1
        utilization_pct = consumed_units / max_units
        below_floor = consumed_units < m.min_weekly_units

        milestone_utilization.append(MilestoneUtilization(
            milestone_id=m.milestone_id,
            description=m.description,
            consumed_units=consumed_units,
            max_weekly_units=m.max_weekly_units,
            utilization_pct=utilization_pct,
            below_floor=below_floor,
        ))

        if below_floor:
            goals_below_floor.append(m.goal_id)

    return WeeklyAggregatedSummary(
        user_id=user_id,
        week_start=week_start,
        milestones_active=len(milestones),
        tasks_completed=tasks_completed,
        tasks_stalled=stalled_count,
        deep_work_sessions=deep_work_sessions,
        mechanical_bias_pct=mechanical_bias_pct,
        milestone_utilization=milestone_utilization,
        goals_below_floor=list(set(goals_below_floor)),
    )


# ── Track B helper ──────────────────────────────────────────────────────────────

def _run_track_b(
    user_id: str,
    week_start: str,
    goal_store: GoalStore,
    onboarding_store: OnboardingStore,
) -> None:
    """
    Brief 030, Section 5 (as amended by the post-execution addendum). In order:
      1. Recompute Tri-Vector weights for all active milestones, cross-goal
         normalized (single shared implementation, see core/scheduling/tri_vector.py)
      2. Write updated weights back
      3. Regenerate SlotGrid for the new week

    STAGED → ACTIVE promotion was deliberately removed (D-38-revised):
    STAGED milestones stay paused until the user manually re-activates
    them. GoalStore.get_staged_milestones_by_user still exists for that
    future manual-reactivation endpoint, just not called from here.

    All gated on an OnboardingProfile existing. If none exists, this is a
    no-op, not an error — a user without a profile couldn't have confirmed
    a goal in the first place (Brief 029's confirm_goal precondition), so
    this isn't a reachable state for an active user.
    """
    onboarding_result = onboarding_store.get_profile(user_id)
    if not onboarding_result.success:
        return

    max_workable_hours = onboarding_result.data.max_workable_hours

    # ── 1 & 2: Tri-Vector recompute + write-back ────────────────────────────
    active_milestones_result = goal_store.get_active_milestones_by_user(user_id)
    active_milestones = (
        active_milestones_result.data if active_milestones_result.success else []
    )

    if active_milestones:
        goal_ids = {m.goal_id for m in active_milestones}
        goals_by_id = {}
        for gid in goal_ids:
            g_result = goal_store.get_goal(user_id, gid)
            if g_result.success:
                goals_by_id[gid] = g_result.data

        task_graphs = {}
        for m in active_milestones:
            t_result = goal_store.get_tasks_by_milestone(m.milestone_id)
            task_graphs[m.milestone_id] = t_result.data if t_result.success else []

        weights = compute_tri_vector_weights(active_milestones, goals_by_id, task_graphs)

        for m in active_milestones:
            w = weights.get(m.milestone_id)
            if w is None:
                # Parent goal lookup failed for this milestone — skip rather
                # than crash the weekly cycle; matches the dangling-reference
                # skip convention used in compute_consumed_units.
                continue
            min_u, max_u = derive_corridor(w, max_workable_hours)
            m.tri_vector_weight = w
            m.min_weekly_units = min_u
            m.max_weekly_units = max_u
            goal_store.upsert_milestone(m)

    # ── 3: Regenerate SlotGrid for the new week ─────────────────────────────
    # NOTE (D-38-revised, Brief 030 addendum): STAGED → ACTIVE promotion was
    # removed from this function. STAGED milestones do not auto-promote on
    # the weekly cycle — they stay paused until the user manually
    # re-activates them via an explicit action. GoalStore.get_staged_
    # milestones_by_user still exists and is available for that future
    # endpoint; it's just not called from here anymore.
    new_week_start = date.fromisoformat(week_start)
    new_grid = generate_slot_grid(onboarding_result.data, new_week_start)
    onboarding_store.upsert_slot_grid(new_grid)


# ── Route ──────────────────────────────────────────────────────────────────────

@router.post("/cycle")
async def run_weekly_cycle(
    request: WeeklyCycleRequest,
    goal_store: GoalStore = Depends(get_goal_store),
    raw_store: RawStore = Depends(get_raw_store),
    distilled_store: DistilledStore = Depends(get_distilled_store),
    onboarding_store: OnboardingStore = Depends(get_onboarding_store),
):
    """
    Flow 3 — Weekly cycle.
    Track A: Aggregate weekly data → run GuidanceAgent → write DistilledModel.
    Track B: Recompute Tri-Vector weights (cross-goal), regenerate SlotGrid
             for the new week. STAGED milestones are left untouched
             (D-38-revised — no auto-promotion; manual re-activation only).

    Execution order:
      1. Track B — recompute weights so floors are current before summary reads them
      2. Expiry check — mark EXPIRED goals before summary build excludes them
      3. Build summary — expired goals already removed from active set
      4. Run guidance — receives expired_goal_ids for closure/extension prompting
    """
    # 1. Track B runs FIRST — recomputes min_weekly_units/max_weekly_units for
    #    this week before anything reads them. Previously Track B ran after
    #    the summary was built, so goals_below_floor was always judged against
    #    last week's floor, not this week's (off-by-one-cycle bug).
    _run_track_b(
        user_id=request.user_id,
        week_start=request.week_start,
        goal_store=goal_store,
        onboarding_store=onboarding_store,
    )

    # 2. Expiry check — Fix 4A (Brief PROMPT-01).
    #    Runs after Track B (weights current) and before summary build
    #    (expired goals excluded from milestone_utilization and goals_below_floor).
    expired_goal_ids = _expire_overdue_goals(
        user_id=request.user_id,
        week_start=request.week_start,
        goal_store=goal_store,
    )

    # 3. Build aggregated summary — pure Python, no LLM
    #    get_active_goals now excludes EXPIRED goals set in step 2.
    weekly_summary = _build_weekly_summary(
        user_id=request.user_id,
        week_start=request.week_start,
        goal_store=goal_store,
        raw_store=raw_store,
    )

    # 4. Fetch onboarding profile for capacity context passed to guidance prompt
    onboarding_result = onboarding_store.get_profile(request.user_id)
    max_workable_hours = (
        onboarding_result.data.max_workable_hours
        if onboarding_result.success else None
    )

    # 5. Run weekly guidance — LLM call
    executor = ModelAgentExecutor(
        raw_store=raw_store,
        distilled_store=distilled_store,
        goal_store=goal_store,
        llm=settings.get_llm(),
    )

    guidance_output = await executor.get_weekly_guidance(
        user_id=request.user_id,
        weekly_summary=weekly_summary,
        max_workable_hours=max_workable_hours,
        expired_goal_ids=expired_goal_ids,
    )

    return {
        "user_id": request.user_id,
        "week_start": request.week_start,
        "guidance": {
            "guidance_type":          guidance_output.guidance_type,
            "recommendations":        guidance_output.recommendations,
            "cross_goal_observation": guidance_output.cross_goal_observation,
            "check_in_prompt":        guidance_output.check_in_prompt,
            "thin_input_flag":        guidance_output.thin_input_flag,
            "reasoning_summary":      guidance_output.reasoning_summary,
        },
        "summary": {
            "milestones_active":     weekly_summary.milestones_active,
            "tasks_completed":       weekly_summary.tasks_completed,
            "tasks_stalled":         weekly_summary.tasks_stalled,
            "deep_work_sessions":    weekly_summary.deep_work_sessions,
            "mechanical_bias_pct":   weekly_summary.mechanical_bias_pct,
            "goals_below_floor":     weekly_summary.goals_below_floor,
            "milestone_utilization": [
                m.model_dump() for m in weekly_summary.milestone_utilization
            ],
            "expired_goal_ids":      expired_goal_ids,
        },
    }