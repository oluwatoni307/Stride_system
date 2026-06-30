# PATH: stride_backend/tests/test_goal_routes.py

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.routes.goals import router
from core.schemas.contracts.goal_drafting import DraftingOutput, ProposedMilestone
from core.schemas.contracts.goal_structuring import Boundary1Output, SmartFormulation
from core.schemas.contracts.task_decomposition import TaskDecompositionOutput, TaskDraft
from core.schemas.contracts.execution_engine import SlotAllocationOutput, DeepSessionPlan
from core.schemas.enums import TaskTag


# ── App setup ──────────────────────────────────────────────────────────────────

app = FastAPI()
app.include_router(router)
client = TestClient(app)


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _mock_drafting_output() -> DraftingOutput:
    return DraftingOutput(
        user_id="user_001",
        objectives=["Pass biochemistry finals"],
        proposed_milestones=[
            ProposedMilestone(
                description="Master Metabolism",
                objectives=["Understand glycolysis"],
                suggested_tag=TaskTag.DEEP,
            )
        ],
        success_metrics=["Score 70%+"],
        schema_version=1,
    )


def _mock_boundary1_output() -> Boundary1Output:
    return Boundary1Output(
        user_id="user_001",
        smart_formulation=SmartFormulation(
            specific="Pass biochemistry finals with 70%+",
            measurable="Score 70% or above",
            achievable="Achievable with consistent study",
            relevant="Required for graduation",
            time_bound="By exam date",
        ),
        impact_score=5,
        extracted_deadline="2025-12-01",
        viability_assessment="Viable given 6 weeks.",
        conflict_flag=False,
        override_flag=False,
        schema_version=2,
    )


def _mock_task_decomposition_output(milestone_id: str) -> TaskDecompositionOutput:
    return TaskDecompositionOutput(
        milestone_id=milestone_id,
        tasks=[
            TaskDraft(
                description="Study glycolysis pathway",
                tag=TaskTag.DEEP,
                dependencies=[],
            ),
            TaskDraft(
                description="Create flashcards",
                tag=TaskTag.MECHANICAL,
                dependencies=["Study glycolysis pathway"],
            ),
        ],
        schema_version=1,
    )


def _mock_slot_allocation_output() -> SlotAllocationOutput:
    return SlotAllocationOutput(
        user_id="user_001",
        week_start=date(2025, 6, 2),
        deep_session_plans=[
            DeepSessionPlan(
                milestone_id="any",
                assigned_days=["Monday", "Thursday"],
                sessions_planned=2,
                sessions_needed=2,
                partial_allocation=False,
            )
        ],
    )


# Brief 029: confirm_goal now reads max_workable_hours from OnboardingStore
# instead of trusting a hardcoded default. Tests that exercise confirm_goal
# must mock OnboardingStore.get_profile (and get_slot_grid, for tests that
# reach the scheduling step) the same way DistilledStore.get_model is
# already mocked elsewhere in this file.
def _mock_onboarding_profile_result(max_workable_hours: float = 10.0) -> MagicMock:
    return MagicMock(
        success=True,
        data=MagicMock(max_workable_hours=max_workable_hours),
    )


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestDraftGoalRoute:

    def test_returns_200_on_valid_request(self):
        with patch(
            "api.routes.goals.DraftingAgent.draft_goal",
            new_callable=AsyncMock,
            return_value=_mock_drafting_output(),
        ), patch(
            "api.routes.goals.DistilledStore.get_model",
            return_value=MagicMock(success=False),
        ):
            response = client.post("/goals/draft", json={
                "user_id": "user_001",
                "raw_goal": "I want to pass my biochemistry finals",
                "user_context": "Final year medical student",
            })
            assert response.status_code == 200

    def test_response_contains_objectives(self):
        with patch(
            "api.routes.goals.DraftingAgent.draft_goal",
            new_callable=AsyncMock,
            return_value=_mock_drafting_output(),
        ), patch(
            "api.routes.goals.DistilledStore.get_model",
            return_value=MagicMock(success=False),
        ):
            response = client.post("/goals/draft", json={
                "user_id": "user_001",
                "raw_goal": "Pass biochemistry",
                "user_context": "Student",
            })
            data = response.json()
            assert "objectives" in data
            assert len(data["objectives"]) > 0

    def test_returns_500_on_agent_error(self):
        error_output = _mock_drafting_output()
        from core.schemas.contracts.shared import BoundaryError
        error_output.error = BoundaryError(
            code="PARSE_FAILURE",
            message="LLM failed",
            component="DraftingAgent",
            retry_count=3,
        )
        with patch(
            "api.routes.goals.DraftingAgent.draft_goal",
            new_callable=AsyncMock,
            return_value=error_output,
        ), patch(
            "api.routes.goals.DistilledStore.get_model",
            return_value=MagicMock(success=False),
        ):
            response = client.post("/goals/draft", json={
                "user_id": "user_001",
                "raw_goal": "Pass biochemistry",
                "user_context": "Student",
            })
            assert response.status_code == 500


class TestStructureGoalRoute:

    def test_returns_200_on_valid_request(self):
        with patch(
            "api.routes.goals.SmartAgent.structure_goal",
            new_callable=AsyncMock,
            return_value=_mock_boundary1_output(),
        ), patch(
            "api.routes.goals.DistilledStore.get_model",
            return_value=MagicMock(success=False),
        ):
            response = client.post("/goals/structure", json={
                "user_id": "user_001",
                "confirmed_draft": {
                    "objectives": ["Pass finals"],
                    "proposed_milestones": [],
                    "success_metrics": ["Score 70%+"],
                },
            })
            assert response.status_code == 200

    def test_response_contains_impact_score(self):
        with patch(
            "api.routes.goals.SmartAgent.structure_goal",
            new_callable=AsyncMock,
            return_value=_mock_boundary1_output(),
        ), patch(
            "api.routes.goals.DistilledStore.get_model",
            return_value=MagicMock(success=False),
        ):
            response = client.post("/goals/structure", json={
                "user_id": "user_001",
                "confirmed_draft": {},
            })
            data = response.json()
            assert "impact_score" in data
            assert data["impact_score"] == 5


class TestConfirmGoalRoute:

    def test_returns_400_if_no_deadline(self):
        # Must mock OnboardingStore.get_profile to succeed so the route
        # reaches the extracted_deadline check this test actually targets,
        # rather than 400ing earlier on the (now-required) onboarding check.
        with patch(
            "api.routes.goals.OnboardingStore.get_profile",
            return_value=_mock_onboarding_profile_result(),
        ):
            response = client.post("/goals/confirm", json={
                "user_id": "user_001",
                "confirmed_draft": {
                    "proposed_milestones": [],
                    "success_metrics": [],
                },
                "smart_assessment": {
                    "impact_score": 3,
                    "smart_formulation": {"specific": "Test goal"},
                    # no extracted_deadline
                },
                "week_start": "2025-06-02",
                # slot_grid removed — ConfirmGoalRequest no longer accepts it
                # per Brief 029; slot_grid is now fetched server-side from
                # OnboardingStore inside confirm_goal.
            })
            assert response.status_code == 400
            assert "extracted_deadline" in response.json()["detail"]

    def test_returns_400_if_no_onboarding_profile(self):
        # New coverage for Brief 029: an unonboarded user must get a clear
        # 400 pointing them at POST /onboarding/profile, never a silent
        # fallback to a default max_workable_hours.
        with patch(
            "api.routes.goals.OnboardingStore.get_profile",
            return_value=MagicMock(success=False, error=MagicMock(message="No OnboardingProfile for user user_002")),
        ):
            response = client.post("/goals/confirm", json={
                "user_id": "user_002",
                "confirmed_draft": {
                    "proposed_milestones": [],
                    "success_metrics": [],
                },
                "smart_assessment": {
                    "impact_score": 3,
                    "smart_formulation": {"specific": "Test goal"},
                    "extracted_deadline": "2025-12-01",
                },
                "week_start": "2025-06-02",
            })
            assert response.status_code == 400
            assert "OnboardingProfile" in response.json()["detail"]