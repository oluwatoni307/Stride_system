"""
Tests for PATCH /goals/{goal_id} — Brief 032, Flow 5 Goal Edit.

Run with: PYTHONPATH=. pytest tests/test_goal_patch.py -v
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from tinydb import TinyDB
from tinydb.storages import MemoryStorage

from api.dependencies import get_goal_store, get_onboarding_store
from core.schemas.entities import (
    EnergyBlock,
    Goal,
    Milestone,
    OnboardingProfile,
    Task,
)
from core.schemas.enums import (
    EnergyLevel,
    GoalStatus,
    MilestoneStatus,
    TaskStatus,
    TaskTag,
)
from main import app
from storage.goal_store import GoalStore
from storage.onboarding_store import OnboardingStore


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def goal_store() -> GoalStore:
    db = TinyDB(storage=MemoryStorage)
    return GoalStore(db)


@pytest.fixture
def onboarding_store() -> OnboardingStore:
    db = TinyDB(storage=MemoryStorage)
    store = OnboardingStore(db)
    block = EnergyBlock(
        label="morning", start_time="09:00", end_time="12:00",
        energy_level=EnergyLevel.HIGH,
    )
    store.upsert_profile(OnboardingProfile(
        user_id="user-1",
        max_workable_hours=10.0,
        weekday_blocks=[block],
        weekend_blocks=[block],
    ))
    return store


@pytest.fixture
def client(goal_store, onboarding_store):
    app.dependency_overrides[get_goal_store] = lambda: goal_store
    app.dependency_overrides[get_onboarding_store] = lambda: onboarding_store
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def make_goal(goal_store, **overrides) -> Goal:
    defaults = dict(
        goal_id="goal-1",
        user_id="user-1",
        name="Original Name",
        status=GoalStatus.ACTIVE,
        macro_impact=3,
        terminal_deadline=date.today() + timedelta(days=60),
    )
    defaults.update(overrides)
    goal = Goal(**defaults)
    goal_store.upsert_goal(goal)
    return goal


def make_milestone(goal_store, goal_id, user_id, **overrides) -> Milestone:
    defaults = dict(
        milestone_id=f"m-{goal_id}-{overrides.get('milestone_id', 'x')}",
        goal_id=goal_id,
        user_id=user_id,
        description="A milestone",
        status=MilestoneStatus.ACTIVE,
        tri_vector_weight=0.5,
        min_weekly_units=1,
        max_weekly_units=2,
    )
    defaults.update(overrides)
    if "milestone_id" not in overrides:
        defaults["milestone_id"] = f"m-{goal_id}-{id(overrides)}"
    m = Milestone(**defaults)
    goal_store.upsert_milestone(m)
    return m


def make_task(goal_store, milestone_id, goal_id, user_id, tag=TaskTag.MODERATE, task_id=None):
    t = Task(
        task_id=task_id or f"t-{milestone_id}-{tag}",
        milestone_id=milestone_id,
        goal_id=goal_id,
        user_id=user_id,
        description="A task",
        tag=tag,
        status=TaskStatus.AVAILABLE,
    )
    goal_store.upsert_task(t)
    return t


# ── 404 ──────────────────────────────────────────────────────────────────────

def test_patch_unknown_goal_returns_404(client):
    resp = client.patch(
        "/goals/does-not-exist",
        json={"user_id": "user-1", "name": "New Name"},
    )
    assert resp.status_code == 404


# ── Validation ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad_value", [0, 6, -1, 100])
def test_patch_invalid_macro_impact_returns_400(client, goal_store, bad_value):
    make_goal(goal_store)
    resp = client.patch(
        "/goals/goal-1",
        json={"user_id": "user-1", "macro_impact": bad_value},
    )
    assert resp.status_code == 400


def test_patch_invalid_deadline_returns_400(client, goal_store):
    make_goal(goal_store)
    resp = client.patch(
        "/goals/goal-1",
        json={"user_id": "user-1", "terminal_deadline": "not-a-date"},
    )
    assert resp.status_code == 400


def test_patch_invalid_status_returns_400(client, goal_store):
    make_goal(goal_store)
    resp = client.patch(
        "/goals/goal-1",
        json={"user_id": "user-1", "status": "NOT_A_REAL_STATUS"},
    )
    assert resp.status_code == 400


def test_patch_valid_macro_impact_boundaries_accepted(client, goal_store):
    make_goal(goal_store)
    for val in (1, 5):
        resp = client.patch(
            "/goals/goal-1",
            json={"user_id": "user-1", "macro_impact": val},
        )
        assert resp.status_code == 200, resp.text


# ── Partial-update semantics ─────────────────────────────────────────────────

def test_patch_only_changes_provided_fields(client, goal_store):
    original_deadline = date.today() + timedelta(days=60)
    make_goal(goal_store, name="Original Name", macro_impact=3,
               terminal_deadline=original_deadline)

    resp = client.patch(
        "/goals/goal-1",
        json={"user_id": "user-1", "name": "Updated Name Only"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["goal"]["name"] == "Updated Name Only"
    assert body["goal"]["macro_impact"] == 3
    assert body["goal"]["terminal_deadline"] == original_deadline.isoformat()
    # No recompute should have been triggered for a name-only change.
    assert body["milestones_recomputed"] == []


def test_patch_name_only_does_not_touch_milestones(client, goal_store):
    make_goal(goal_store)
    m = make_milestone(goal_store, "goal-1", "user-1", milestone_id="m-1",
                        tri_vector_weight=0.42, min_weekly_units=3, max_weekly_units=5)
    make_task(goal_store, "m-1", "goal-1", "user-1")

    resp = client.patch(
        "/goals/goal-1",
        json={"user_id": "user-1", "name": "Renamed"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["milestones_recomputed"] == []

    refetched = goal_store.get_milestones_by_goal("goal-1").data[0]
    assert refetched.tri_vector_weight == 0.42
    assert refetched.min_weekly_units == 3
    assert refetched.max_weekly_units == 5


def test_patch_immutable_fields_not_editable(client, goal_store):
    """goal_id and user_id are not part of UpdateGoalRequest's editable
    fields — confirms the request schema itself enforces immutability
    (extra fields are ignored by default pydantic behavior, not errored,
    but they have no effect on the entity)."""
    make_goal(goal_store)
    resp = client.patch(
        "/goals/goal-1",
        json={"user_id": "user-1", "goal_id": "goal-999"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["goal"]["goal_id"] == "goal-1"


# ── Status update ────────────────────────────────────────────────────────────

def test_patch_status_update(client, goal_store):
    make_goal(goal_store)
    resp = client.patch(
        "/goals/goal-1",
        json={"user_id": "user-1", "status": "PAUSED"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["goal"]["status"] == "PAUSED"
    # status change alone should not trigger recompute
    assert resp.json()["milestones_recomputed"] == []


# ── Recompute triggering ─────────────────────────────────────────────────────

def test_patch_macro_impact_change_triggers_recompute(client, goal_store):
    make_goal(goal_store, macro_impact=2)
    make_milestone(goal_store, "goal-1", "user-1", milestone_id="m-1")
    make_task(goal_store, "m-1", "goal-1", "user-1")

    resp = client.patch(
        "/goals/goal-1",
        json={"user_id": "user-1", "macro_impact": 5},
    )
    assert resp.status_code == 200, resp.text
    assert "m-goal-1-m-1" in resp.json()["milestones_recomputed"] or \
           len(resp.json()["milestones_recomputed"]) >= 1


def test_patch_deadline_change_triggers_recompute(client, goal_store):
    make_goal(goal_store, terminal_deadline=date.today() + timedelta(days=120))
    make_milestone(goal_store, "goal-1", "user-1", milestone_id="m-1")
    make_task(goal_store, "m-1", "goal-1", "user-1")

    resp = client.patch(
        "/goals/goal-1",
        # Moves deadline into the <7-day urgency bracket (U: 1.0 -> 2.0)
        json={"user_id": "user-1", "terminal_deadline": (date.today() + timedelta(days=3)).isoformat()},
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["milestones_recomputed"]) >= 1


def test_patch_no_relevant_change_skips_recompute_entirely(client, goal_store, monkeypatch):
    """If neither terminal_deadline nor macro_impact change, the route
    should not even call get_active_milestones_by_user — confirms the
    'only when actually changed' gate, not just an empty result."""
    make_goal(goal_store, macro_impact=3)
    make_milestone(goal_store, "goal-1", "user-1", milestone_id="m-1")
    make_task(goal_store, "m-1", "goal-1", "user-1")

    called = {"flag": False}
    original = GoalStore.get_active_milestones_by_user

    def spy(self, user_id):
        called["flag"] = True
        return original(self, user_id)

    monkeypatch.setattr(GoalStore, "get_active_milestones_by_user", spy)

    resp = client.patch(
        "/goals/goal-1",
        json={"user_id": "user-1", "macro_impact": 3, "name": "Same Impact"},
    )
    assert resp.status_code == 200, resp.text
    assert called["flag"] is False


def test_patch_recompute_only_returns_milestones_whose_weight_actually_changed(client, goal_store):
    """Two milestones under the same goal with different task loads —
    after recompute, both get new weights (since I or U changed for the
    whole goal), so both should appear as recomputed in this case."""
    make_goal(goal_store, macro_impact=2)
    make_milestone(goal_store, "goal-1", "user-1", milestone_id="m-1")
    make_milestone(goal_store, "goal-1", "user-1", milestone_id="m-2")
    make_task(goal_store, "m-goal-1-m-1", "goal-1", "user-1", task_id="t1")
    make_task(goal_store, "m-goal-1-m-2", "goal-1", "user-1", task_id="t2")

    resp = client.patch(
        "/goals/goal-1",
        json={"user_id": "user-1", "macro_impact": 5},
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["milestones_recomputed"]) == 2


def test_patch_recompute_writes_back_to_store(client, goal_store):
    make_goal(goal_store, macro_impact=1,
               terminal_deadline=date.today() + timedelta(days=120))
    make_milestone(goal_store, "goal-1", "user-1", milestone_id="m-1",
                    tri_vector_weight=0.0, min_weekly_units=0, max_weekly_units=0)
    make_task(goal_store, "m-goal-1-m-1", "goal-1", "user-1", task_id="t1")

    resp = client.patch(
        "/goals/goal-1",
        json={"user_id": "user-1", "macro_impact": 5},
    )
    assert resp.status_code == 200, resp.text

    refetched = goal_store.get_milestones_by_goal("goal-1").data[0]
    assert refetched.tri_vector_weight != 0.0
    assert refetched.max_weekly_units > 0


# ── Cross-goal normalization (post-Brief-030-extraction) ────────────────────

def test_patch_recompute_spans_other_goals_milestones_too(client, goal_store):
    """The OTHER goal's milestones (not the one being edited) should
    also get touched by recompute, since get_active_milestones_by_user
    is user-wide, not goal-scoped, and the route now calls the shared
    compute_tri_vector_weights once across all of a user's active
    milestones (global cross-goal normalization, per the Brief 032
    addendum)."""
    make_goal(goal_store, goal_id="goal-1", macro_impact=2)
    make_goal(goal_store, goal_id="goal-2", macro_impact=4,
              terminal_deadline=date.today() + timedelta(days=200))

    make_milestone(goal_store, "goal-1", "user-1", milestone_id="m-1",
                    tri_vector_weight=0.0, min_weekly_units=0, max_weekly_units=0)
    make_milestone(goal_store, "goal-2", "user-1", milestone_id="m-2",
                    tri_vector_weight=0.0, min_weekly_units=0, max_weekly_units=0)
    make_task(goal_store, "m-goal-1-m-1", "goal-1", "user-1", task_id="t1")
    make_task(goal_store, "m-goal-2-m-2", "goal-2", "user-1", task_id="t2")

    resp = client.patch(
        "/goals/goal-1",
        json={"user_id": "user-1", "macro_impact": 5},
    )
    assert resp.status_code == 200, resp.text

    # goal-2's milestone should ALSO have been recomputed (touched),
    # even though its goal wasn't the one edited, because the recompute
    # pass is user-wide and globally normalized.
    goal2_milestone = goal_store.get_milestones_by_goal("goal-2").data[0]
    assert goal2_milestone.tri_vector_weight != 0.0


def test_patch_global_normalization_sums_to_one_across_goals(client, goal_store):
    """Brief 032 Addendum acceptance criterion: create 2 goals with
    active milestones for the same user, PATCH one goal's deadline,
    assert ALL active milestones for that user (across both goals)
    still sum to 1.0. This is the specific case the old per-goal-group
    workaround would have gotten wrong (it summed to 1.0 WITHIN each
    goal separately, i.e. 2.0 total across two goals, not 1.0 globally).
    """
    make_goal(goal_store, goal_id="goal-1", macro_impact=2,
              terminal_deadline=date.today() + timedelta(days=120))
    make_goal(goal_store, goal_id="goal-2", macro_impact=4,
              terminal_deadline=date.today() + timedelta(days=200))

    make_milestone(goal_store, "goal-1", "user-1", milestone_id="m-1",
                    tri_vector_weight=0.0, min_weekly_units=0, max_weekly_units=0)
    make_milestone(goal_store, "goal-1", "user-1", milestone_id="m-1b",
                    tri_vector_weight=0.0, min_weekly_units=0, max_weekly_units=0)
    make_milestone(goal_store, "goal-2", "user-1", milestone_id="m-2",
                    tri_vector_weight=0.0, min_weekly_units=0, max_weekly_units=0)
    make_task(goal_store, "m-goal-1-m-1", "goal-1", "user-1", task_id="t1", tag=TaskTag.DEEP)
    make_task(goal_store, "m-goal-1-m-1b", "goal-1", "user-1", task_id="t1b", tag=TaskTag.MECHANICAL)
    make_task(goal_store, "m-goal-2-m-2", "goal-2", "user-1", task_id="t2", tag=TaskTag.MODERATE)

    # PATCH goal-1's deadline — this should trigger a global recompute
    # spanning every active milestone for user-1, across BOTH goals.
    resp = client.patch(
        "/goals/goal-1",
        json={"user_id": "user-1", "terminal_deadline": (date.today() + timedelta(days=5)).isoformat()},
    )
    assert resp.status_code == 200, resp.text

    all_milestones = []
    all_milestones.extend(goal_store.get_milestones_by_goal("goal-1").data)
    all_milestones.extend(goal_store.get_milestones_by_goal("goal-2").data)

    total_weight = sum(m.tri_vector_weight for m in all_milestones)
    assert total_weight == pytest.approx(1.0, abs=1e-9), (
        f"Expected global normalization to sum to 1.0 across all active "
        f"milestones for the user, got {total_weight}. The old per-goal-"
        f"group workaround would have produced ~{len({'goal-1', 'goal-2'})}.0 here."
    )



def test_patch_no_onboarding_profile_returns_400_on_recompute(client, goal_store):
    empty_db = TinyDB(storage=MemoryStorage)
    app.dependency_overrides[get_onboarding_store] = lambda: OnboardingStore(empty_db)
    make_goal(goal_store, macro_impact=2)
    make_milestone(goal_store, "goal-1", "user-1", milestone_id="m-1")
    make_task(goal_store, "m-goal-1-m-1", "goal-1", "user-1", task_id="t1")

    resp = client.patch(
        "/goals/goal-1",
        json={"user_id": "user-1", "macro_impact": 5},
    )
    assert resp.status_code == 400


# ── Zero LLM / no ModelAgentExecutor (structural confirmation) ───────────────

def test_patch_route_has_no_llm_or_agent_dependencies():
    """Structural check: the update_goal route function's dependency
    signature only references GoalStore and OnboardingStore — no agent,
    no LLM client. Confirms D-16/D-23 compliance without needing to mock
    an LLM and assert it was never called."""
    import inspect
    from api.routes.goals import update_goal

    sig = inspect.signature(update_goal)
    param_annotations = [str(p.annotation) for p in sig.parameters.values()]
    assert not any("Agent" in a for a in param_annotations)
    assert not any("LLM" in a for a in param_annotations)