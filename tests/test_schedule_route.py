# PATH: stride_backend/tests/test_schedule_route.py

import pytest
from unittest.mock import MagicMock, patch
from datetime import date
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.routes.schedule import router
from core.schemas.contracts.execution_engine import (
    DeepSessionPlan,
    SlotAllocationOutput,
)
from core.schemas.entities import Milestone
from core.schemas.enums import MilestoneStatus

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _make_milestone(milestone_id: str) -> Milestone:
    return Milestone(
        milestone_id=milestone_id,
        goal_id="goal_001",
        user_id="user_001",
        description=f"Milestone {milestone_id}",
        tri_vector_weight=0.5,
        min_weekly_units=2,
        max_weekly_units=8,
        status=MilestoneStatus.ACTIVE,
    )


def _make_slot_grid():
    return {
        "user_id": "user_001",
        "week_start": "2025-06-02",
        "slots": [
            {"day": "Monday",    "start_time": "09:00", "energy_level": "HIGH"},
            {"day": "Wednesday", "start_time": "09:00", "energy_level": "HIGH"},
            {"day": "Friday",    "start_time": "09:00", "energy_level": "HIGH"},
        ],
    }


def _mock_allocation_output(milestone_id: str = "m1") -> SlotAllocationOutput:
    return SlotAllocationOutput(
        user_id="user_001",
        week_start=date(2025, 6, 2),
        deep_session_plans=[
            DeepSessionPlan(
                milestone_id=milestone_id,
                assigned_days=["Monday", "Thursday"],
                sessions_planned=2,
                sessions_needed=2,
                partial_allocation=False,
            )
        ],
    )


class TestAllocateSlotsRoute:

    def test_returns_200_on_valid_request(self):
        with patch("api.routes.schedule.GoalStore.get_active_milestones_by_user",
                   return_value=MagicMock(
                       success=True,
                       data=[_make_milestone("m1")]
                   )), \
             patch("api.routes.schedule.SchedulingComponent.allocate_slots",
                   return_value=_mock_allocation_output()):
            response = client.post("/schedule/allocate", json={
                "user_id":   "user_001",
                "week_start": "2025-06-02",
                "slot_grid":  _make_slot_grid(),
            })
            assert response.status_code == 200

    def test_returns_deep_session_plans(self):
        with patch("api.routes.schedule.GoalStore.get_active_milestones_by_user",
                   return_value=MagicMock(
                       success=True,
                       data=[_make_milestone("m1")]
                   )), \
             patch("api.routes.schedule.SchedulingComponent.allocate_slots",
                   return_value=_mock_allocation_output()):
            response = client.post("/schedule/allocate", json={
                "user_id":   "user_001",
                "week_start": "2025-06-02",
                "slot_grid":  _make_slot_grid(),
            })
            data = response.json()
            assert "deep_session_plans" in data
            assert len(data["deep_session_plans"]) == 1

    def test_plan_contains_expected_fields(self):
        with patch("api.routes.schedule.GoalStore.get_active_milestones_by_user",
                   return_value=MagicMock(
                       success=True,
                       data=[_make_milestone("m1")]
                   )), \
             patch("api.routes.schedule.SchedulingComponent.allocate_slots",
                   return_value=_mock_allocation_output()):
            response = client.post("/schedule/allocate", json={
                "user_id":   "user_001",
                "week_start": "2025-06-02",
                "slot_grid":  _make_slot_grid(),
            })
            plan = response.json()["deep_session_plans"][0]
            assert "milestone_id" in plan
            assert "assigned_days" in plan
            assert "sessions_planned" in plan
            assert "partial_allocation" in plan

    def test_empty_milestones_returns_200_with_empty_plans(self):
        with patch("api.routes.schedule.GoalStore.get_active_milestones_by_user",
                   return_value=MagicMock(success=True, data=[])):
            response = client.post("/schedule/allocate", json={
                "user_id":   "user_001",
                "week_start": "2025-06-02",
                "slot_grid":  _make_slot_grid(),
            })
            assert response.status_code == 200
            data = response.json()
            assert data["deep_session_plans"] == []
            assert "message" in data

    def test_milestone_store_failure_returns_500(self):
        with patch("api.routes.schedule.GoalStore.get_active_milestones_by_user",
                   return_value=MagicMock(
                       success=False,
                       error=MagicMock(message="DB error")
                   )):
            response = client.post("/schedule/allocate", json={
                "user_id":   "user_001",
                "week_start": "2025-06-02",
                "slot_grid":  _make_slot_grid(),
            })
            assert response.status_code == 500

    def test_missing_user_id_returns_422(self):
        response = client.post("/schedule/allocate", json={
            "week_start": "2025-06-02",
            "slot_grid":  _make_slot_grid(),
        })
        assert response.status_code == 422

    def test_missing_slot_grid_returns_422(self):
        response = client.post("/schedule/allocate", json={
            "user_id":    "user_001",
            "week_start": "2025-06-02",
        })
        assert response.status_code == 422