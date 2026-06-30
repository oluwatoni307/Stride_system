# PATH: stride_backend/api/routes/onboarding.py
# DOMAIN: Onboarding API routes — OnboardingProfile creation/update and
# SlotGrid generation.

from __future__ import annotations

from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.dependencies import get_onboarding_store, get_raw_store
from core.scheduling.slot_grid_generator import generate_slot_grid
from core.schemas.entities import EnergyBlock, OnboardingProfile, SlotGrid
from core.validation.onboarding import validate_onboarding_profile
from storage.onboarding_store import OnboardingStore
from storage.raw_store import RawStore

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _current_week_start() -> date:
    """
    Monday of the current week. Matches the convention used elsewhere for
    'current week' (date.today() minus weekday offset) — no separate
    timezone-aware or alternate convention introduced here.
    """
    today = date.today()
    return today - timedelta(days=today.weekday())


# ── Request / Response models ──────────────────────────────────────────────────

class CreateOnboardingProfileRequest(BaseModel):
    user_id: str
    max_workable_hours: float
    weekday_blocks: List[EnergyBlock]
    weekend_blocks: List[EnergyBlock]


class CreateOnboardingProfileResponse(BaseModel):
    profile: OnboardingProfile
    slot_grid: SlotGrid


class UpdateEnergyBlocksRequest(BaseModel):
    weekday_blocks: Optional[List[EnergyBlock]] = None
    weekend_blocks: Optional[List[EnergyBlock]] = None


class UpdateEnergyBlocksResponse(BaseModel):
    profile: OnboardingProfile
    slot_grid: SlotGrid


class GetOnboardingProfileResponse(BaseModel):
    profile: OnboardingProfile


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/profile", response_model=CreateOnboardingProfileResponse)
async def create_onboarding_profile(
    request: CreateOnboardingProfileRequest,
    onboarding_store: OnboardingStore = Depends(get_onboarding_store),
    raw_store: RawStore = Depends(get_raw_store),
):
    """
    Creates (or replaces) a user's OnboardingProfile, validates it, and
    generates + persists the current week's SlotGrid from it.

    Also initializes RawStore for this user_id — RawStore.append_feedback_event
    (used by /tasks/complete) requires a RawUserModel to already exist, and
    onboarding is the conceptually correct "this user now exists" moment to
    create it. Without this, the first task completion for any new user
    crashes with "No RawUserModel for user {user_id}".
    """
    profile = OnboardingProfile(
        user_id=request.user_id,
        max_workable_hours=request.max_workable_hours,
        weekday_blocks=request.weekday_blocks,
        weekend_blocks=request.weekend_blocks,
    )

    validation = validate_onboarding_profile(profile)
    if not validation.success:
        raise HTTPException(status_code=400, detail=validation.error.message)

    write_result = onboarding_store.upsert_profile(profile)
    if not write_result.success:
        raise HTTPException(status_code=500, detail=write_result.error.message)

    week_start = _current_week_start()
    slot_grid = generate_slot_grid(profile, week_start)

    grid_write = onboarding_store.upsert_slot_grid(slot_grid)
    if not grid_write.success:
        raise HTTPException(status_code=500, detail=grid_write.error.message)

    # Initialize RawStore for this user. ALREADY_EXISTS is not an error
    # here — it just means this user_id already has a RawUserModel (e.g.
    # a retried onboarding call); fall through and continue normally.
    raw_init_result = raw_store.initialise_user(request.user_id)
    if not raw_init_result.success and raw_init_result.error.code != "ALREADY_EXISTS":
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize RawStore for user: {raw_init_result.error.message}",
        )

    return CreateOnboardingProfileResponse(profile=profile, slot_grid=slot_grid)


@router.patch("/profile/{user_id}/energy-blocks", response_model=UpdateEnergyBlocksResponse)
async def update_energy_blocks(
    user_id: str,
    request: UpdateEnergyBlocksRequest,
    onboarding_store: OnboardingStore = Depends(get_onboarding_store),
):
    """
    Merges provided weekday_blocks / weekend_blocks updates onto the
    existing profile, re-validates, and regenerates the SlotGrid for the
    CURRENT week only (not past weeks).
    """
    existing = onboarding_store.get_profile(user_id)
    if not existing.success:
        raise HTTPException(status_code=404, detail=existing.error.message)

    profile = existing.data
    if request.weekday_blocks is not None:
        profile.weekday_blocks = request.weekday_blocks
    if request.weekend_blocks is not None:
        profile.weekend_blocks = request.weekend_blocks

    validation = validate_onboarding_profile(profile)
    if not validation.success:
        raise HTTPException(status_code=400, detail=validation.error.message)

    write_result = onboarding_store.upsert_profile(profile)
    if not write_result.success:
        raise HTTPException(status_code=500, detail=write_result.error.message)

    week_start = _current_week_start()
    slot_grid = generate_slot_grid(profile, week_start)

    grid_write = onboarding_store.upsert_slot_grid(slot_grid)
    if not grid_write.success:
        raise HTTPException(status_code=500, detail=grid_write.error.message)

    return UpdateEnergyBlocksResponse(profile=profile, slot_grid=slot_grid)


@router.get("/profile/{user_id}", response_model=GetOnboardingProfileResponse)
async def get_onboarding_profile(
    user_id: str,
    onboarding_store: OnboardingStore = Depends(get_onboarding_store),
):
    """
    Returns 404 if no profile exists — this is how the client knows to
    route a user into onboarding vs. the main app.
    """
    result = onboarding_store.get_profile(user_id)
    if not result.success:
        raise HTTPException(status_code=404, detail=result.error.message)

    return GetOnboardingProfileResponse(profile=result.data)