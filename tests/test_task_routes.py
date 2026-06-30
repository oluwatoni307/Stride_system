# PATH: stride_backend/tests/test_task_routes.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.routes.tasks import router
from core.schemas.contracts.execution_engine import QueuePullResponse
from core.schemas.contracts.feedback_loop import Boundary3Output
from core.schemas.entities import Task
from core.schemas.enums import TaskStatus, TaskTag


app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _make_task(task_id: str = "task_001") -> Task:
    return Task(
        task_id=task_id,
        milestone_id="milestone_001",
        goal_id="goal_001",
        user_id="user_001",
        description="Study glycolysis",
        tag=TaskTag.DEEP,
        dependencies=[],
        status=TaskStatus.AVAILABLE,
    )


class TestPullTaskRoute:

    def test_returns_200_on_valid_pull(self):
        pull_response = QueuePullResponse(
            pulled_task=_make_task(),
            state_message="PULLING",
        )
        with patch(
            "api.routes.tasks.SlotAllocator.pull",
            return_value=pull_response,
        ), patch(
            "api.routes.tasks.GoalStore.get_available_tasks_by_user",
            return_value=MagicMock(success=True, data=[_make_task()]),
        ), patch(
            "api.routes.tasks.GoalStore.get_active_milestones_by_user",
            return_value=MagicMock(success=True, data=[]),
        ), patch(
            "api.routes.tasks.GoalStore.get_tasks_by_user",
            return_value=MagicMock(success=True, data=[]),
        ):
            response = client.post("/tasks/pull", json={
                "user_id": "user_001",
                "current_energy_level": "HIGH",
            })
            assert response.status_code == 200

    def test_returns_pulled_task_in_response(self):
        pull_response = QueuePullResponse(
            pulled_task=_make_task(),
            state_message="PULLING",
        )
        with patch(
            "api.routes.tasks.SlotAllocator.pull",
            return_value=pull_response,
        ), patch(
            "api.routes.tasks.GoalStore.get_available_tasks_by_user",
            return_value=MagicMock(success=True, data=[]),
        ), patch(
            "api.routes.tasks.GoalStore.get_active_milestones_by_user",
            return_value=MagicMock(success=True, data=[]),
        ), patch(
            "api.routes.tasks.GoalStore.get_tasks_by_user",
            return_value=MagicMock(success=True, data=[]),
        ):
            response = client.post("/tasks/pull", json={
                "user_id": "user_001",
                "current_energy_level": "HIGH",
            })
            data = response.json()
            assert data["pulled_task"] is not None
            assert data["state_message"] == "PULLING"

    def test_returns_400_on_invalid_energy_level(self):
        response = client.post("/tasks/pull", json={
            "user_id": "user_001",
            "current_energy_level": "EXTREME",
        })
        assert response.status_code == 400

    def test_no_eligible_tasks_returns_200_with_none(self):
        pull_response = QueuePullResponse(
            pulled_task=None,
            state_message="NO_ELIGIBLE_TASKS",
        )
        with patch(
            "api.routes.tasks.SlotAllocator.pull",
            return_value=pull_response,
        ), patch(
            "api.routes.tasks.GoalStore.get_available_tasks_by_user",
            return_value=MagicMock(success=True, data=[]),
        ), patch(
            "api.routes.tasks.GoalStore.get_active_milestones_by_user",
            return_value=MagicMock(success=True, data=[]),
        ), patch(
            "api.routes.tasks.GoalStore.get_tasks_by_user",
            return_value=MagicMock(success=True, data=[]),
        ):
            response = client.post("/tasks/pull", json={
                "user_id": "user_001",
                "current_energy_level": "LOW",
            })
            assert response.status_code == 200
            assert response.json()["pulled_task"] is None
            assert response.json()["state_message"] == "NO_ELIGIBLE_TASKS"


class TestCompleteTaskRoute:

    def test_returns_200_on_valid_completion(self):
        completion_output = Boundary3Output(
            user_id="user_001",
            task_id="task_001",
            success=True,
        )
        with patch(
            "api.routes.tasks.GoalStore.get_task",
            return_value=MagicMock(success=True, data=_make_task()),
        ), patch(
            "api.routes.tasks.ModelAgentExecutor.process_task_completion",
            new_callable=AsyncMock,
            return_value=completion_output,
        ), patch(
            "api.routes.tasks.GoalStore.get_tasks_by_milestone",
            return_value=MagicMock(success=True, data=[]),
        ):
            response = client.post("/tasks/complete", json={
                "user_id": "user_001",
                "task_id": "task_001",
                "goal_id": "goal_001",
                "milestone_id": "milestone_001",
            })
            assert response.status_code == 200

    def test_returns_404_if_task_not_found(self):
        with patch(
            "api.routes.tasks.GoalStore.get_task",
            return_value=MagicMock(success=False),
        ):
            response = client.post("/tasks/complete", json={
                "user_id": "user_001",
                "task_id": "nonexistent",
                "goal_id": "goal_001",
                "milestone_id": "milestone_001",
            })
            assert response.status_code == 404

    def test_response_contains_success_true(self):
        completion_output = Boundary3Output(
            user_id="user_001",
            task_id="task_001",
            success=True,
        )
        with patch(
            "api.routes.tasks.GoalStore.get_task",
            return_value=MagicMock(success=True, data=_make_task()),
        ), patch(
            "api.routes.tasks.ModelAgentExecutor.process_task_completion",
            new_callable=AsyncMock,
            return_value=completion_output,
        ), patch(
            "api.routes.tasks.GoalStore.get_tasks_by_milestone",
            return_value=MagicMock(success=True, data=[]),
        ):
            response = client.post("/tasks/complete", json={
                "user_id": "user_001",
                "task_id": "task_001",
                "goal_id": "goal_001",
                "milestone_id": "milestone_001",
            })
            assert response.json()["success"] is True