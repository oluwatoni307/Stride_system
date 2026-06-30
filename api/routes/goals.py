# PATH: stride_backend/api/routes/goals.py
# DOMAIN: Goal creation and management API routes — Flow 1, Flow 5

from __future__ import annotations

import graphlib
from datetime import date, datetime, timezone
from math import floor
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agents.drafting_agent.agent import DraftingAgent
from agents.smart_agent.agent import SmartAgent
from agents.task_decomposer.agent import TaskDecomposer
from api.dependencies import (
    get_drafting_agent,
    get_distilled_store,
    get_goal_store,
    get_onboarding_store,
    get_raw_store,
    get_scheduling_component,
    get_smart_agent,
    get_task_decomposer,
)
from core.config import DEEP_MIN_GAP_DAYS
from core.scheduling.capacity_conflict import (
    CapacityConflictError,
    check_capacity_conflict,
)
from core.scheduling.scheduling_component import SchedulingComponent
from core.scheduling.tri_vector import compute_tri_vector_weights, derive_corridor
from core.schemas.contracts.execution_engine import (
    MilestoneAllocationData,
    SlotAllocationInput,
)
from core.schemas.contracts.goal_drafting import (
    DraftingInput,
    DraftingOutput,
    DraftingRevisionInput,
)
from core.schemas.contracts.goal_structuring import Boundary1Input
from core.schemas.contracts.task_decomposition import TaskDecompositionInput
from core.schemas.entities import (
    Goal,
    Milestone,
    MilestoneStatus,
    Task,
    TaskStatus,
)
from core.schemas.enums import GoalStatus, TaskTag
from storage.distilled_store import DistilledStore
from storage.goal_store import GoalStore
from storage.onboarding_store import OnboardingStore
from storage.raw_store import RawStore

router = APIRouter(prefix="/goals", tags=["goals"])


# ── Request / Response models ────────────────────────────────────────────────

class DraftGoalRequest(BaseModel):
    user_id: str
    raw_goal: str
    user_context: str


class ReviseGoalDraftRequest(BaseModel):
    user_id: str
    previous_draft: dict
    user_response: str


class StructureGoalRequest(BaseModel):
    user_id: str
    confirmed_draft: dict
    existing_goal_summaries: List[dict] = []


class NegotiateStructureRequest(BaseModel):
    user_id: str
    confirmed_draft: dict
    previous_assessment: dict
    user_response: str
    existing_goal_summaries: List[dict] = []


class ConfirmGoalRequest(BaseModel):
    user_id: str
    confirmed_draft: dict
    smart_assessment: dict          # Boundary1Output as dict
    week_start: str                 # ISO date string


class UpdateGoalRequest(BaseModel):
    """Flow 5 — partial update. Optional fields left untouched if not provided."""
    user_id: str
    name: Optional[str] = None
    macro_impact: Optional[int] = None        # 1-5
    terminal_deadline: Optional[str] = None    # ISO date string
    status: Optional[str] = None               # ACTIVE | PAUSED | COMPLETED


class UpdateGoalResponse(BaseModel):
    goal: dict                                  # updated Goal as dict
    milestones_recomputed: List[str]            # milestone_ids whose weights changed


# ── Helpers ────────────────────────────────────────────────────────────────────

def _resolve_dependencies(tasks: List[Task]) -> List[Task]:
    """
    Map dependency descriptions to task_ids using TopologicalSorter.
    Returns tasks with dependencies resolved to task_ids.
    Raises HTTPException 400 if cycle detected.
    """
    desc_to_id = {t.description: t.task_id for t in tasks}

    # Build dependency map using task_ids
    dep_map: Dict[str, List[str]] = {}
    for task in tasks:
        resolved = []
        for dep_desc in task.dependencies:
            dep_id = desc_to_id.get(dep_desc)
            if dep_id:
                resolved.append(dep_id)
        dep_map[task.task_id] = resolved
        task.dependencies = resolved

    # Validate — detect cycles
    try:
        sorter = graphlib.TopologicalSorter(dep_map)
        sorter.prepare()
    except graphlib.CycleError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Dependency cycle detected in task graph: {e}",
        )

    # Mark tasks with no unmet deps as AVAILABLE
    # INF-03 (B-09): first_made_available_at must be set the moment a task
    # becomes AVAILABLE — this is one of two transition points (the other
    # is the dependency-unlock loop in api/routes/tasks.py::complete_task).
    # A task that stays PENDING here is not stamped — it has no age to
    # measure until it actually becomes eligible to pull.
    tasks_with_deps = {tid for deps in dep_map.values() for tid in deps}
    now = datetime.now(timezone.utc)
    for task in tasks:
        if not task.dependencies:
            task.status = TaskStatus.AVAILABLE
            task.first_made_available_at = now
        else:
            task.status = TaskStatus.PENDING

    return tasks


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/draft")
async def draft_goal(
    request: DraftGoalRequest,
    drafting_agent: DraftingAgent = Depends(get_drafting_agent),
    distilled_store: DistilledStore = Depends(get_distilled_store),
):
    """
    Flow 1 Step 1 — DraftingAgent converts raw goal text into structured draft.
    """
    snapshot_result = distilled_store.get_model(request.user_id)
    snapshot = snapshot_result.data.model_dump() if snapshot_result.success else {}

    drafting_input = DraftingInput(
        user_id=request.user_id,
        raw_goal=request.raw_goal,
        user_context=request.user_context,
        distilled_model_snapshot=snapshot,
    )

    output = await drafting_agent.draft_goal(drafting_input)

    if output.error:
        raise HTTPException(status_code=500, detail=output.error.message)

    return output.model_dump()


@router.post("/draft/revise")
async def revise_goal_draft(
    request: ReviseGoalDraftRequest,
    drafting_agent: DraftingAgent = Depends(get_drafting_agent),
):
    """
    Flow 1 — DraftingAgent revises draft based on user feedback.
    """
    previous_draft = DraftingOutput(**request.previous_draft)

    revision_input = DraftingRevisionInput(
        user_id=request.user_id,
        previous_draft=previous_draft,
        user_response=request.user_response,
    )

    output = await drafting_agent.revise_draft(revision_input)

    if output.error:
        raise HTTPException(status_code=500, detail=output.error.message)

    return output.model_dump()


@router.post("/structure")
async def structure_goal(
    request: StructureGoalRequest,
    smart_agent: SmartAgent = Depends(get_smart_agent),
    distilled_store: DistilledStore = Depends(get_distilled_store),
):
    """
    Flow 1 Step 2 — SmartAgent fits confirmed draft to user context.
    Returns SMART formulation, impact_score, extracted_deadline.
    """
    snapshot_result = distilled_store.get_model(request.user_id)
    snapshot = snapshot_result.data.model_dump() if snapshot_result.success else {}

    boundary_input = Boundary1Input(
        user_id=request.user_id,
        confirmed_draft=request.confirmed_draft,
        distilled_model_snapshot=snapshot,
        existing_goal_summaries=request.existing_goal_summaries,
    )

    output = await smart_agent.structure_goal(boundary_input)

    if output.error:
        raise HTTPException(status_code=500, detail=output.error.message)

    return output.model_dump()


@router.post("/structure/negotiate")
async def negotiate_goal_structure(
    request: NegotiateStructureRequest,
    smart_agent: SmartAgent = Depends(get_smart_agent),
    distilled_store: DistilledStore = Depends(get_distilled_store),
):
    """
    Flow 1 — SmartAgent negotiates SMART formulation on user pushback.
    """
    snapshot_result = distilled_store.get_model(request.user_id)
    snapshot = snapshot_result.data.model_dump() if snapshot_result.success else {}

    boundary_input = Boundary1Input(
        user_id=request.user_id,
        confirmed_draft=request.confirmed_draft,
        distilled_model_snapshot=snapshot,
        existing_goal_summaries=request.existing_goal_summaries,
    )

    output = await smart_agent.negotiate_goal_creation(
        input=boundary_input,
        previous_assessment=request.previous_assessment,
        user_response=request.user_response,
    )

    if output.error:
        raise HTTPException(status_code=500, detail=output.error.message)

    return output.model_dump()


@router.post("/confirm")
async def confirm_goal(
    request: ConfirmGoalRequest,
    task_decomposer: TaskDecomposer = Depends(get_task_decomposer),
    scheduling_component: SchedulingComponent = Depends(get_scheduling_component),
    goal_store: GoalStore = Depends(get_goal_store),
    raw_store: RawStore = Depends(get_raw_store),
    distilled_store: DistilledStore = Depends(get_distilled_store),
    onboarding_store: OnboardingStore = Depends(get_onboarding_store),
):
    """
    Flow 1 Step 3 — Confirm goal. Writes Goal + Milestones, runs TaskDecomposer,
    runs SchedulingComponent, writes Tasks.
    """
    smart = request.smart_assessment
    draft = request.confirmed_draft

    # ── Capacity conflict check ────────────────────────────────────────────────
    onboarding_result = onboarding_store.get_profile(request.user_id)
    if not onboarding_result.success:
        raise HTTPException(
            status_code=400,
            detail=(
                "No OnboardingProfile found for this user. "
                "Complete onboarding (POST /onboarding/profile) before "
                "confirming a goal."
            ),
        )
    max_workable_hours = onboarding_result.data.max_workable_hours

    # ── Build Goal entity ───────────────────────────────────────────────────────
    # A goal with no extracted_deadline is valid — not every goal is
    # deadline-bound (e.g. open-ended habits, identity-driven goals).
    # terminal_deadline is still a required `date` field on the Goal schema
    # (Tri-Vector urgency math needs SOME date), so absence of a real
    # deadline maps to a far-future placeholder, landing permanently in the
    # lowest urgency bracket (U=1.0, >90 days) rather than being rejected.
    extracted_deadline = smart.get("extracted_deadline")
    if extracted_deadline:
        terminal_deadline = date.fromisoformat(extracted_deadline)
    else:
        terminal_deadline = date(2099, 12, 31)

    goal_id = str(uuid4())
    goal = Goal(
        goal_id=goal_id,
        user_id=request.user_id,
        name=smart.get("smart_formulation", {}).get("specific", "Unnamed Goal"),
        status=GoalStatus.ACTIVE,
        macro_impact=smart.get("impact_score", 3),
        terminal_deadline=terminal_deadline,
    )

    # ── Build Milestone entities (V=1.0 placeholder) ───────────────────────────
    # NOTE (INF-01b): these Milestone objects are built and mutated in memory
    # only at this stage. Nothing is persisted until the capacity check below
    # passes — see INF-01b for why this ordering matters.
    proposed_milestones = draft.get("proposed_milestones", [])
    milestones: List[Milestone] = []
    for pm in proposed_milestones:
        milestones.append(Milestone(
            milestone_id=str(uuid4()),
            goal_id=goal_id,
            user_id=request.user_id,
            description=pm.get("description", ""),
            objectives=pm.get("objectives", []),
            success_metrics=draft.get("success_metrics", []),
            tri_vector_weight=0.0,      # placeholder — computed after tasks
            min_weekly_units=0,
            max_weekly_units=0,
            status=MilestoneStatus.STAGED,
        ))

    # ── Run TaskDecomposer per milestone ────────────────────────────────────────
    # In-memory only — task_graphs feeds Tri-Vector computation below.
    # No goal_store writes happen here (INF-01b): the previous version wrote
    # Goal and Milestone rows to storage at this point, before the capacity
    # check existed downstream. If a later check failed (or, before INF-01,
    # if nothing failed at all), those rows were left behind permanently —
    # a phantom ACTIVE goal with no tasks. Decomposition itself has no
    # persistence side effect, so it can safely run before the check too.
    task_graphs: Dict[str, List[Task]] = {}
    for m in milestones:
        decomp_input = TaskDecompositionInput(
            milestone_id=m.milestone_id,
            milestone_description=m.description,
            objectives=m.objectives,
            success_metrics=m.success_metrics,
            previous_task_logs=[],
        )
        decomp_output = await task_decomposer.decompose(decomp_input)
        if decomp_output.error:
            raise HTTPException(
                status_code=500, detail=decomp_output.error.message
            )

        # Build Task entities from drafts
        tasks = [
            Task(
                task_id=str(uuid4()),
                milestone_id=m.milestone_id,
                goal_id=goal_id,
                user_id=request.user_id,
                description=td.description,
                tag=td.tag,
                dependencies=list(td.dependencies),
                status=TaskStatus.PENDING,
            )
            for td in decomp_output.tasks
        ]

        # Resolve dependencies
        tasks = _resolve_dependencies(tasks)
        task_graphs[m.milestone_id] = tasks

    # ── INF-04 (B-03): normalize cross-goal, not single-goal ───────────────────
    # compute_tri_vector_weights normalizes weights to sum to 1.0 across
    # ONLY the milestones list passed in. Passing just this goal's own
    # milestones (the previous behavior) makes this new goal's weights sum
    # to 1.0 against itself alone — as if it were the user's only
    # commitment — which produces a min_weekly_units that is NOT
    # comparable to existing milestones' min_weekly_units (each normalized
    # under a different, earlier scope). The capacity check below then
    # summed two numbers computed under incompatible normalization scopes,
    # which is why it fired for some personas and not others depending on
    # how the mismatch happened to fall relative to their threshold.
    #
    # Fix: fetch existing active milestones (and their parent goals) up
    # front, and normalize ONCE across existing + new combined — the same
    # pattern update_goal already uses below for its own recompute.
    existing_milestones_result = goal_store.get_active_milestones_by_user(
        request.user_id
    )
    if not existing_milestones_result.success:
        raise HTTPException(
            status_code=500, detail=existing_milestones_result.error.message
        )
    existing_milestones = existing_milestones_result.data

    # Build goals_by_id covering both the new goal and every distinct goal
    # represented among the existing active milestones, so I/U lookups
    # resolve correctly for all of them.
    goals_by_id: Dict[str, Goal] = {goal.goal_id: goal}
    for m in existing_milestones:
        if m.goal_id not in goals_by_id:
            g_result = goal_store.get_goal(request.user_id, m.goal_id)
            if not g_result.success:
                raise HTTPException(
                    status_code=500, detail=g_result.error.message
                )
            goals_by_id[m.goal_id] = g_result.data

    # Existing milestones' tasks are already persisted — rebuild their
    # task_graphs from storage so V (slot units) is computed correctly for
    # them too. task_graphs for the NEW milestones already exists from the
    # TaskDecomposer loop above.
    for m in existing_milestones:
        if m.milestone_id not in task_graphs:
            tasks_result = goal_store.get_tasks_by_milestone(m.milestone_id)
            if not tasks_result.success:
                raise HTTPException(
                    status_code=500, detail=tasks_result.error.message
                )
            task_graphs[m.milestone_id] = tasks_result.data

    combined_milestones = existing_milestones + milestones
    weights = compute_tri_vector_weights(
        combined_milestones, goals_by_id, task_graphs
    )

    # Re-derive corridors for the NEW milestones (in memory only — not yet
    # persisted, per INF-01b: a 409 below must leave storage untouched).
    for m in milestones:
        w = weights[m.milestone_id]
        min_u, max_u = derive_corridor(w, max_workable_hours)
        m.tri_vector_weight = w
        m.min_weekly_units = min_u
        m.max_weekly_units = max_u
        m.status = MilestoneStatus.ACTIVE
        # No goal_store.upsert_milestone() call here (INF-01b) — these
        # milestones now hold real, non-placeholder min_weekly_units, which
        # is exactly what the capacity check below needs, but they are
        # still in-memory objects only at this point.

    # Re-derive corridors for EXISTING milestones too — their normalized
    # weight may have shifted now that the new goal entered the pool, so
    # their stored min/max_weekly_units are stale relative to this
    # combined scope. Held in memory until the capacity check passes;
    # written alongside the new goal's milestones afterward.
    for m in existing_milestones:
        w = weights[m.milestone_id]
        min_u, max_u = derive_corridor(w, max_workable_hours)
        m.tri_vector_weight = w
        m.min_weekly_units = min_u
        m.max_weekly_units = max_u

    # ── B-03 capacity conflict check (INF-01b: runs BEFORE any writes) ─────────
    # Locked formula (do not change): new_total_min_weekly_units >
    # max_workable_hours x 3. Must run after derive_corridor() — it needs
    # real min_weekly_units, not tag-based proxies — and must not be moved
    # to structure_goal. Per INF-01b, it must also run before any
    # goal_store writes for THIS goal, so that a 409 leaves storage
    # untouched rather than persisting a half-confirmed ACTIVE goal.
    #
    # Cumulative across the user's other ACTIVE milestones (other goals),
    # not just this goal's own milestones in isolation — otherwise a user
    # could never trip the threshold by adding goals one at a time
    # regardless of how many they already have active, which would defeat
    # the purpose of a capacity gate.
    #
    # INF-04: existing_active_total now uses existing_milestones' freshly
    # re-derived min_weekly_units (combined-scope normalization) rather
    # than re-fetching and summing their stale stored values — those two
    # numbers are no longer the same thing, and using the stale one here
    # would silently reintroduce the scope mismatch this fix exists to
    # close.
    existing_active_total = sum(
        em.min_weekly_units for em in existing_milestones
    )

    try:
        check_capacity_conflict(
            existing_active_min_weekly_units=existing_active_total,
            new_milestones=milestones,
            max_workable_hours=max_workable_hours,
        )
    except CapacityConflictError as e:
        # No writes have occurred for this goal at this point — goal_id was
        # generated in memory but never persisted, so returning 409 here
        # leaves storage exactly as it was before this request. See
        # INF-01b success condition: goal_store.json should show no trace
        # of this goal after a 409. existing_milestones' re-derived
        # corridors are also still in-memory only — a 409 here means
        # their stored values remain whatever they were before this
        # request, which is correct: nothing should change if the new
        # goal never gets confirmed.
        raise HTTPException(
            status_code=409,
            detail={
                "error": "capacity_conflict",
                "message": e.message,
                "goal_id": goal_id,
                "new_total_min_weekly_units": e.new_total_min_weekly_units,
                "threshold": e.threshold,
                "max_workable_hours": e.max_workable_hours,
                "breaching_milestones": [
                    {
                        "milestone_id": b.milestone_id,
                        "description": b.description,
                        "min_weekly_units": b.min_weekly_units,
                    }
                    for b in e.breaching_milestones
                ],
            },
        )

    # ── Capacity check passed — persist Goal, Milestones, Tasks ────────────────
    # All writes for this goal happen from this point on, only after the
    # capacity check above has passed.
    goal_write = goal_store.upsert_goal(goal)
    if not goal_write.success:
        raise HTTPException(status_code=500, detail=goal_write.error.message)

    for m in milestones:
        m_write = goal_store.upsert_milestone(m)
        if not m_write.success:
            raise HTTPException(status_code=500, detail=m_write.error.message)

    # INF-04: existing milestones' corridors were re-derived above under the
    # new combined cross-goal normalization scope — persist those too, or
    # their stored min/max_weekly_units stay stale until the next weekly
    # cycle or edit touches them.
    for m in existing_milestones:
        m_write = goal_store.upsert_milestone(m)
        if not m_write.success:
            raise HTTPException(status_code=500, detail=m_write.error.message)

    for task_list in task_graphs.values():
        for task in task_list:
            t_write = goal_store.upsert_task(task)
            if not t_write.success:
                raise HTTPException(
                    status_code=500, detail=t_write.error.message
                )

    # ── Run SchedulingComponent ──────────────────────────────────────────────────
    week_start = date.fromisoformat(request.week_start)

    slot_grid_result = onboarding_store.get_slot_grid(request.user_id, week_start)
    if not slot_grid_result.success:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No SlotGrid found for user {request.user_id}, week "
                f"{week_start.isoformat()}. Onboarding may be incomplete, "
                f"or this week's grid has not been generated."
            ),
        )
    slot_grid = slot_grid_result.data

    allocation_input = SlotAllocationInput(
        user_id=request.user_id,
        week_start=week_start,
        milestones=[
            MilestoneAllocationData(
                milestone_id=m.milestone_id,
                tri_vector_weight=m.tri_vector_weight,
                min_weekly_units=m.min_weekly_units,
                max_weekly_units=m.max_weekly_units,
            )
            for m in milestones
        ],
        slot_grid=slot_grid.model_dump(),
        notes="goal confirmation",
    )

    allocation_output = scheduling_component.allocate_slots(allocation_input)

    if allocation_output.error:
        # Non-fatal — log and continue. Scheduling failure should not
        # block goal creation.
        pass

    return {
        "goal_id": goal_id,
        "milestone_ids": [m.milestone_id for m in milestones],
        "task_counts": {
            mid: len(tasks) for mid, tasks in task_graphs.items()
        },
        "deep_session_plans": (
            [p.model_dump() for p in allocation_output.deep_session_plans]
            if not allocation_output.error else []
        ),
        "status": "confirmed",
    }


@router.patch("/{goal_id}")
async def update_goal(
    goal_id: str,
    request: UpdateGoalRequest,
    goal_store: GoalStore = Depends(get_goal_store),
    onboarding_store: OnboardingStore = Depends(get_onboarding_store),
):
    """
    Flow 5 — Goal Edit (CRUD). Pure Python, no LLM, no ModelAgentExecutor
    (matches D-16, D-23). Partial update: only provided fields are changed.

    If terminal_deadline or macro_impact changes, recomputes Tri-Vector
    weights via core.scheduling.tri_vector.compute_tri_vector_weights —
    the same shared function used by the weekly cycle (Brief 030) — across
    ALL of the user's active milestones (cross-goal, globally normalized),
    and writes back tri_vector_weight / min_weekly_units / max_weekly_units
    for any milestone whose computed values actually changed.
    """
    # ── 1. Fetch existing Goal ──────────────────────────────────────────────────
    goal_result = goal_store.get_goal(request.user_id, goal_id)
    if not goal_result.success:
        raise HTTPException(status_code=404, detail=goal_result.error.message)
    goal = goal_result.data

    # ── 2. Validate provided fields ─────────────────────────────────────────────
    if request.macro_impact is not None:
        if not (1 <= request.macro_impact <= 5):
            raise HTTPException(
                status_code=400,
                detail="macro_impact must be between 1 and 5 inclusive.",
            )

    parsed_deadline: Optional[date] = None
    if request.terminal_deadline is not None:
        try:
            parsed_deadline = date.fromisoformat(request.terminal_deadline)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"terminal_deadline {request.terminal_deadline!r} is not "
                    "a valid ISO date (YYYY-MM-DD)."
                ),
            )

    parsed_status: Optional[GoalStatus] = None
    if request.status is not None:
        try:
            parsed_status = GoalStatus(request.status)
        except ValueError:
            valid = ", ".join(s.value for s in GoalStatus)
            raise HTTPException(
                status_code=400,
                detail=(
                    f"status {request.status!r} is not a valid GoalStatus. "
                    f"Valid values: {valid}"
                ),
            )

    # ── 3. Apply only provided changes ──────────────────────────────────────────
    deadline_changed = False
    impact_changed = False

    if request.name is not None:
        goal.name = request.name

    if (
        request.macro_impact is not None
        and request.macro_impact != goal.macro_impact
    ):
        goal.macro_impact = request.macro_impact
        impact_changed = True

    if parsed_deadline is not None and parsed_deadline != goal.terminal_deadline:
        goal.terminal_deadline = parsed_deadline
        deadline_changed = True

    if parsed_status is not None:
        goal.status = parsed_status

    # ── 4. Write updated Goal ───────────────────────────────────────────────────
    write_result = goal_store.upsert_goal(goal)
    if not write_result.success:
        raise HTTPException(status_code=500, detail=write_result.error.message)

    # ── 5. Recompute Tri-Vector if terminal_deadline or macro_impact changed
    recomputed_ids: List[str] = []

    if deadline_changed or impact_changed:
        milestones_result = goal_store.get_active_milestones_by_user(
            request.user_id
        )
        if not milestones_result.success:
            raise HTTPException(
                status_code=500, detail=milestones_result.error.message
            )
        active_milestones = milestones_result.data

        if active_milestones:
            onboarding_result = onboarding_store.get_profile(request.user_id)
            if not onboarding_result.success:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "No OnboardingProfile found for this user — required "
                        "to recompute weekly unit corridors."
                    ),
                )
            max_workable_hours = onboarding_result.data.max_workable_hours

            # Rebuild task_graphs from storage (these milestones already
            # have real tasks, unlike confirm_goal's freshly-decomposed set).
            task_graphs: Dict[str, List[Task]] = {}
            for m in active_milestones:
                tasks_result = goal_store.get_tasks_by_milestone(
                    m.milestone_id
                )
                if not tasks_result.success:
                    raise HTTPException(
                        status_code=500, detail=tasks_result.error.message
                    )
                task_graphs[m.milestone_id] = tasks_result.data

            # Build goals_by_id for every distinct goal represented among
            # this user's active milestones — compute_tri_vector_weights
            # looks up I/U per-milestone via its own parent goal, but
            # normalizes across the FULL milestones list passed in, so
            # passing every active milestone for the user here gives true
            # cross-goal normalization (same call shape as the weekly
            # cycle in Brief 030).
            goals_by_id: Dict[str, Goal] = {goal.goal_id: goal}
            for m in active_milestones:
                if m.goal_id not in goals_by_id:
                    g_result = goal_store.get_goal(request.user_id, m.goal_id)
                    if not g_result.success:
                        raise HTTPException(
                            status_code=500, detail=g_result.error.message
                        )
                    goals_by_id[m.goal_id] = g_result.data

            all_weights = compute_tri_vector_weights(
                active_milestones, goals_by_id, task_graphs
            )

            # INF-02 (B-12): report every milestone included in THIS
            # recompute pass, not only the subset whose stored value
            # happens to differ from before. The recompute itself already
            # runs unconditionally whenever deadline_changed or
            # impact_changed is True (see the `if` above this block) — that
            # part was never the problem. The bug was here: a milestone
            # whose urgency bracket didn't cross a boundary (e.g. a deadline
            # extension that stays within >90d) produces an identical w,
            # min_u, and max_u to what was already stored, so the old
            # `changed` filter silently dropped it from
            # milestones_recomputed even though it was genuinely
            # recomputed. compute_tri_vector_weights normalizes across the
            # FULL active_milestones list passed in (sum to 1.0 across that
            # whole set) — reporting only a "changed" subset can never sum
            # to 1.0 except by coincidence, since it's an arbitrary partial
            # slice of a normalized distribution. Reporting the full set
            # this pass touched is what makes that invariant hold.
            for m in active_milestones:
                w = all_weights[m.milestone_id]
                min_u, max_u = derive_corridor(w, max_workable_hours)
                m.tri_vector_weight = w
                m.min_weekly_units = min_u
                m.max_weekly_units = max_u
                m_write = goal_store.upsert_milestone(m)
                if not m_write.success:
                    raise HTTPException(
                        status_code=500, detail=m_write.error.message
                    )
                recomputed_ids.append(m.milestone_id)

    # ── 6. Return ────────────────────────────────────────────────────────────────
    return UpdateGoalResponse(
        goal=goal.model_dump(),
        milestones_recomputed=recomputed_ids,
    )