# PATH: stride_backend/tests/test_weekly_route.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.routes.weekly import router
from core.schemas.contracts.execution_engine import WeeklyAggregatedSummary
from core.schemas.enums import TaskStatus, TaskTag


app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _mock_guidance_output():
    from agents.model_agent.prompts import WeeklyGuidanceOutput
    return WeeklyGuidanceOutput(
        guidance_type="full_guidance",
        recommendations=["Focus on deep work sessions", "Review stalled tasks"],
        cross_goal_observation="Both goals share similar skill requirements.",
        check_in_prompt=None,
        thin_input_flag=False,
        reasoning_summary="User completed 12 tasks with 80% utilization.",
    )


def _mock_store(tasks=None, milestones=None):
    store = MagicMock()
    store.get_tasks_by_user.return_value = MagicMock(
        success=True,
        data=tasks or [],
    )
    store.get_active_milestones_by_user.return_value = MagicMock(
        success=True,
        data=milestones or [],
    )
    store.get_active_goals.return_value = MagicMock(success=True, data=[])
    store.get_priority_list.return_value = MagicMock(success=False)
    store.get_model.return_value = MagicMock(success=False)
    store.get_model_snapshot.return_value = MagicMock(success=False)
    store.write_model_snapshot.return_value = MagicMock(success=True)
    return store


class TestWeeklyCycleRoute:

    def test_returns_200_on_valid_request(self):
        with patch("api.routes.weekly.get_goal_store",
                   return_value=lambda: _mock_store()), \
             patch("api.routes.weekly.get_raw_store",
                   return_value=lambda: _mock_store()), \
             patch("api.routes.weekly.get_distilled_store",
                   return_value=lambda: _mock_store()), \
             patch("api.routes.weekly.ModelAgentExecutor.get_weekly_guidance",
                   new_callable=AsyncMock,
                   return_value=_mock_guidance_output()), \
             patch("api.routes.weekly.settings.get_llm",
                   return_value=MagicMock()):
            response = client.post("/weekly/cycle", json={
                "user_id": "user_001",
                "week_start": "2025-06-02",
            })
            assert response.status_code == 200

    def test_response_contains_guidance(self):
        with patch("api.routes.weekly.ModelAgentExecutor.get_weekly_guidance",
                   new_callable=AsyncMock,
                   return_value=_mock_guidance_output()), \
             patch("api.routes.weekly.settings.get_llm",
                   return_value=MagicMock()), \
             patch("api.routes.weekly.GoalStore.get_tasks_by_user",
                   return_value=MagicMock(success=True, data=[])), \
             patch("api.routes.weekly.GoalStore.get_active_milestones_by_user",
                   return_value=MagicMock(success=True, data=[])), \
             patch("api.routes.weekly.GoalStore.get_active_goals",
                   return_value=MagicMock(success=True, data=[])), \
             patch("api.routes.weekly.DistilledStore.get_priority_list",
                   return_value=MagicMock(success=False)), \
             patch("api.routes.weekly.DistilledStore.get_model_snapshot",
                   return_value=MagicMock(success=False)), \
             patch("api.routes.weekly.DistilledStore.write_model_snapshot",
                   return_value=MagicMock(success=True)):
            response = client.post("/weekly/cycle", json={
                "user_id": "user_001",
                "week_start": "2025-06-02",
            })
            data = response.json()
            assert "guidance" in data
            assert "summary" in data

    def test_response_contains_summary_fields(self):
        with patch("api.routes.weekly.ModelAgentExecutor.get_weekly_guidance",
                   new_callable=AsyncMock,
                   return_value=_mock_guidance_output()), \
             patch("api.routes.weekly.settings.get_llm",
                   return_value=MagicMock()), \
             patch("api.routes.weekly.GoalStore.get_tasks_by_user",
                   return_value=MagicMock(success=True, data=[])), \
             patch("api.routes.weekly.GoalStore.get_active_milestones_by_user",
                   return_value=MagicMock(success=True, data=[])), \
             patch("api.routes.weekly.GoalStore.get_active_goals",
                   return_value=MagicMock(success=True, data=[])), \
             patch("api.routes.weekly.DistilledStore.get_priority_list",
                   return_value=MagicMock(success=False)), \
             patch("api.routes.weekly.DistilledStore.get_model_snapshot",
                   return_value=MagicMock(success=False)), \
             patch("api.routes.weekly.DistilledStore.write_model_snapshot",
                   return_value=MagicMock(success=True)):
            response = client.post("/weekly/cycle", json={
                "user_id": "user_001",
                "week_start": "2025-06-02",
            })
            summary = response.json()["summary"]
            assert "tasks_completed" in summary
            assert "deep_work_sessions" in summary
            assert "goals_below_floor" in summary

    def test_missing_user_id_returns_422(self):
        response = client.post("/weekly/cycle", json={
            "week_start": "2025-06-02",
        })
        assert response.status_code == 422

    def test_missing_week_start_returns_422(self):
        response = client.post("/weekly/cycle", json={
            "user_id": "user_001",
        })
        assert response.status_code == 422