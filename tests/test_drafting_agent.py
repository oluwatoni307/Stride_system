import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.drafting_agent.agent import DraftingAgent
from agents.drafting_agent.prompts import GoalDraftOutput, ProposedMilestoneOutput
from core.schemas.contracts.goal_drafting import (
    DraftingInput,
    DraftingOutput,
    DraftingRevisionInput,
)
from core.schemas.enums import TaskTag


def _make_llm_mock(output) -> MagicMock:
    """Stand-in for the injected ChatOpenAI llm. with_structured_output must
    return a real LangChain Runnable — a bare MagicMock/AsyncMock is NOT a
    Runnable instance, so ChatPromptTemplate.__or__ coerces it into a
    RunnableLambda that calls __call__ instead of .ainvoke, silently
    bypassing any configured mock return value. RunnableLambda wrapping an
    async callable is invoked correctly via .ainvoke through the pipe."""
    from langchain_core.runnables import RunnableLambda

    async def _fake(_inputs):
        if isinstance(output, BaseException):
            raise output
        return output

    llm = MagicMock()
    llm.with_structured_output = MagicMock(return_value=RunnableLambda(_fake))
    return llm


def _sample_draft_output() -> GoalDraftOutput:
    return GoalDraftOutput(
        objectives=["Understand core biochemistry concepts"],
        proposed_milestones=[
            ProposedMilestoneOutput(
                description="Master Metabolism",
                objectives=["Understand glycolysis", "Understand TCA cycle"],
                suggested_tag="DEEP",
            ),
            ProposedMilestoneOutput(
                description="Master Enzymes",
                objectives=["Understand enzyme kinetics"],
                suggested_tag="MODERATE",
            ),
        ],
        success_metrics=["Score 70%+ on biochemistry finals"],
    )


def _make_drafting_input() -> DraftingInput:
    return DraftingInput(
        user_id="user_001",
        raw_goal="I want to pass my biochemistry finals",
        user_context="Final year medical student",
        distilled_model_snapshot={},
    )


class TestDraftingAgentDraftGoal:

    @pytest.mark.asyncio
    async def test_returns_drafting_output(self):
        agent = DraftingAgent(llm=_make_llm_mock(_sample_draft_output()))
        result = await agent.draft_goal(_make_drafting_input())
        assert isinstance(result, DraftingOutput)

    @pytest.mark.asyncio
    async def test_user_id_passed_through(self):
        agent = DraftingAgent(llm=_make_llm_mock(_sample_draft_output()))
        result = await agent.draft_goal(_make_drafting_input())
        assert result.user_id == "user_001"

    @pytest.mark.asyncio
    async def test_objectives_populated(self):
        agent = DraftingAgent(llm=_make_llm_mock(_sample_draft_output()))
        result = await agent.draft_goal(_make_drafting_input())
        assert len(result.objectives) > 0

    @pytest.mark.asyncio
    async def test_milestones_populated(self):
        agent = DraftingAgent(llm=_make_llm_mock(_sample_draft_output()))
        result = await agent.draft_goal(_make_drafting_input())
        assert len(result.proposed_milestones) > 0

    @pytest.mark.asyncio
    async def test_milestone_tags_are_valid_task_tags(self):
        agent = DraftingAgent(llm=_make_llm_mock(_sample_draft_output()))
        result = await agent.draft_goal(_make_drafting_input())
        for m in result.proposed_milestones:
            assert m.suggested_tag in TaskTag

    @pytest.mark.asyncio
    async def test_success_metrics_populated(self):
        agent = DraftingAgent(llm=_make_llm_mock(_sample_draft_output()))
        result = await agent.draft_goal(_make_drafting_input())
        assert len(result.success_metrics) > 0

    @pytest.mark.asyncio
    async def test_no_error_on_success(self):
        agent = DraftingAgent(llm=_make_llm_mock(_sample_draft_output()))
        result = await agent.draft_goal(_make_drafting_input())
        assert result.error is None

    @pytest.mark.asyncio
    async def test_error_output_on_llm_failure(self):
        agent = DraftingAgent(llm=_make_llm_mock(Exception("LLM timeout")))
        result = await agent.draft_goal(_make_drafting_input())
        assert result.error is not None
        assert result.error.component == "DraftingAgent"
        assert result.objectives == []

    @pytest.mark.asyncio
    async def test_invalid_tag_defaults_to_moderate(self):
        output = _sample_draft_output()
        output.proposed_milestones[0].suggested_tag = "INVALID_TAG"
        agent = DraftingAgent(llm=_make_llm_mock(output))
        result = await agent.draft_goal(_make_drafting_input())
        assert result.proposed_milestones[0].suggested_tag == TaskTag.MODERATE


class TestDraftingAgentReviseDraft:

    def _make_revision_input(self) -> DraftingRevisionInput:
        prev = DraftingOutput(
            user_id="user_001",
            objectives=["Understand core biochemistry concepts"],
            proposed_milestones=[],
            success_metrics=["Score 70%+"],
            schema_version=1,
        )
        return DraftingRevisionInput(
            user_id="user_001",
            previous_draft=prev,
            user_response="Can you add a milestone for lipid biochemistry?",
        )

    @pytest.mark.asyncio
    async def test_returns_drafting_output(self):
        agent = DraftingAgent(llm=_make_llm_mock(_sample_draft_output()))
        result = await agent.revise_draft(self._make_revision_input())
        assert isinstance(result, DraftingOutput)

    @pytest.mark.asyncio
    async def test_user_id_preserved_from_previous_draft(self):
        agent = DraftingAgent(llm=_make_llm_mock(_sample_draft_output()))
        result = await agent.revise_draft(self._make_revision_input())
        assert result.user_id == "user_001"

    @pytest.mark.asyncio
    async def test_error_output_on_llm_failure(self):
        agent = DraftingAgent(llm=_make_llm_mock(Exception("timeout")))
        result = await agent.revise_draft(self._make_revision_input())
        assert result.error is not None
        assert result.error.component == "DraftingAgent"