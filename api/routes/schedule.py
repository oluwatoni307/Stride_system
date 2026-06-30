
# PATH: stride_backend/api/routes/schedule.py
# DOMAIN: Scheduling route — slot allocation for active milestones

from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.dependencies import get_distilled_store, get_goal_store
from core.scheduling.scheduling_component import SchedulingComponent
from core.schemas.contracts.execution_engine import (
    MilestoneAllocationData,
    SlotAllocationInput,
    SlotAllocationOutput,
)
from storage.distilled_store import DistilledStore
from storage.goal_store import GoalStore

router = APIRouter(prefix="/schedule", tags=["schedule"])


# ── Request model ──────────────────────────────────────────────────────────────

class AllocateSlotsRequest(BaseModel):
    user_id: str
    week_start: str         # ISO date string e.g. "2025-06-02"
    slot_grid: dict         # SlotGrid as dict — days, times, energy levels
    notes: Optional[str] = None


# ── Route ──────────────────────────────────────────────────────────────────────

@router.post("/allocate")
async def allocate_slots(
    request: AllocateSlotsRequest,
    goal_store: GoalStore = Depends(get_goal_store),
    distilled_store: DistilledStore = Depends(get_distilled_store),
):
    """
    Flow 3 Track B — Scheduling route.
    Fetches all active milestones, runs SchedulingComponent,
    returns DeepSessionPlans for the week.

    Also called:
    - On new goal confirmation (after TaskDecomposer runs)
    - On timetable edit (after negotiation)
    - On milestone edit (after negotiation)
    - On weekly reset
    """
    # Fetch all active milestones
    milestones_result = goal_store.get_active_milestones_by_user(request.user_id)
    if not milestones_result.success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch milestones: {milestones_result.error.message}",
        )

    milestones = milestones_result.data

    if not milestones:
        return {
            "user_id":           request.user_id,
            "week_start":        request.week_start,
            "deep_session_plans": [],
            "message":           "No active milestones found.",
        }

    # Build allocation input
    allocation_input = SlotAllocationInput(
        user_id=request.user_id,
        week_start=date.fromisoformat(request.week_start),
        milestones=[
            MilestoneAllocationData(
                milestone_id=m.milestone_id,
                tri_vector_weight=m.tri_vector_weight,
                min_weekly_units=m.min_weekly_units,
                max_weekly_units=m.max_weekly_units,
            )
            for m in milestones
        ],
        slot_grid=request.slot_grid,
        notes=request.notes,
    )

    # Run SchedulingComponent — deterministic, no LLM
    component = SchedulingComponent()
    output = component.allocate_slots(allocation_input)

    if output.error:
        raise HTTPException(
            status_code=500,
            detail=output.error.message,
        )

    return {
        "user_id":   request.user_id,
        "week_start": request.week_start,
        "deep_session_plans": [
            {
                "milestone_id":      plan.milestone_id,
                "assigned_days":     plan.assigned_days,
                "sessions_planned":  plan.sessions_planned,
                "sessions_needed":   plan.sessions_needed,
                "partial_allocation": plan.partial_allocation,
            }
            for plan in output.deep_session_plans
        ],
    }