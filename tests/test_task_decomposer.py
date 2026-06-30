import pytest
from unittest.mock import AsyncMock, MagicMock

from agents.task_decomposer.agent import TaskDecomposer
from agents.task_decomposer.prompts import (
    BreakdownTaskOutput,
    StalledTaskBreakdownOutput,
    TaskGraphOutput,
    TaskOutput,
)
from core.schemas.contracts.task_decomposition import (
    StalledTaskBreakdownInput,
    StalledTaskBreakdownOutput as ContractStalledOutput,
    TaskDecompositionInput,
    TaskDecompositionOutput,
)
from core.schemas.enums import TaskTag


def _make_llm_mock(output) -> MagicMock:
    """Stand-in for the injected ChatOpenAI llm. with_structured_output must
    return a real LangChain Runnable — a bare MagicMock/AsyncMock is NOT a
    Runnable instance, so ChatPromptTemplate.__or__ coerces it into a
    RunnableLambda that calls __call__ instead of .ainvoke, silently
    bypassing any configured mock return value. RunnableLambda wrapping an
    async callable is invoked correctly via .ainvoke through the pipe.
    Pass an Exception instance as `output` to simulate an LLM failure."""
    from langchain_core.runnables import RunnableLambda

    async def _fake(_inputs):
        if isinstance(output, BaseException):
            raise output
        return output

    llm = MagicMock()
    llm.with_structured_output = MagicMock(return_value=RunnableLambda(_fake))
    return llm


def _sample_task_graph() -> TaskGraphOutput:
    return TaskGraphOutput(tasks=[
        TaskOutput(
            description="Set up project structure",
            tag="MECHANICAL",
            dependencies=[],
        ),
        TaskOutput(
            description="Implement authentication",
            tag="DEEP",
            dependencies=["Set up project structure"],
        ),
        TaskOutput(
            description="Write unit tests",
            tag="MODERATE",
            dependencies=["Implement authentication"],
        ),
    ])


def _make_decomposition_input() -> TaskDecompositionInput:
    return TaskDecompositionInput(
        milestone_id="milestone_001",
        milestone_description="Build Flutter authentication module",
        objectives=["Implement login", "Implement registration"],
        success_metrics=["Auth flow working end to end"],
        previous_task_logs=[],
    )


class TestTaskDecomposerDecompose:

    @pytest.mark.asyncio
    async def test_returns_decomposition_output(self):
        agent = TaskDecomposer(llm=_make_llm_mock(_sample_task_graph()))
        result = await agent.decompose(_make_decomposition_input())
        assert isinstance(result, TaskDecompositionOutput)

    @pytest.mark.asyncio
    async def test_milestone_id_passed_through(self):
        agent = TaskDecomposer(llm=_make_llm_mock(_sample_task_graph()))
        result = await agent.decompose(_make_decomposition_input())
        assert result.milestone_id == "milestone_001"

    @pytest.mark.asyncio
    async def test_tasks_populated(self):
        agent = TaskDecomposer(llm=_make_llm_mock(_sample_task_graph()))
        result = await agent.decompose(_make_decomposition_input())
        assert len(result.tasks) == 3

    @pytest.mark.asyncio
    async def test_task_tags_are_valid(self):
        agent = TaskDecomposer(llm=_make_llm_mock(_sample_task_graph()))
        result = await agent.decompose(_make_decomposition_input())
        for task in result.tasks:
            assert task.tag in TaskTag

    @pytest.mark.asyncio
    async def test_dependencies_preserved(self):
        agent = TaskDecomposer(llm=_make_llm_mock(_sample_task_graph()))
        result = await agent.decompose(_make_decomposition_input())
        auth_task = next(t for t in result.tasks
                         if "authentication" in t.description.lower())
        assert "Set up project structure" in auth_task.dependencies

    @pytest.mark.asyncio
    async def test_no_error_on_success(self):
        agent = TaskDecomposer(llm=_make_llm_mock(_sample_task_graph()))
        result = await agent.decompose(_make_decomposition_input())
        assert result.error is None

    @pytest.mark.asyncio
    async def test_error_output_on_llm_failure(self):
        agent = TaskDecomposer(llm=_make_llm_mock(Exception("LLM timeout")))
        result = await agent.decompose(_make_decomposition_input())
        assert result.error is not None
        assert result.error.component == "TaskDecomposer"
        assert result.tasks == []

    @pytest.mark.asyncio
    async def test_invalid_tag_defaults_to_moderate(self):
        graph = _sample_task_graph()
        graph.tasks[0].tag = "NONSENSE"
        agent = TaskDecomposer(llm=_make_llm_mock(graph))
        result = await agent.decompose(_make_decomposition_input())
        assert result.tasks[0].tag == TaskTag.MODERATE


class TestTaskDecomposerBreakdown:

    def _make_breakdown_input(self) -> StalledTaskBreakdownInput:
        return StalledTaskBreakdownInput(
            task_id="task_001",
            description="Implement full authentication system",
            tag=TaskTag.DEEP,
            milestone_id="milestone_001",
            milestone_description="Build Flutter authentication module",
        )

    def _sample_breakdown_output(self) -> StalledTaskBreakdownOutput:
        return StalledTaskBreakdownOutput(replacement_tasks=[
            BreakdownTaskOutput(
                description="Research Firebase Auth documentation",
                tag="MODERATE",
                dependencies=[],
            ),
            BreakdownTaskOutput(
                description="Implement login screen UI",
                tag="MODERATE",
                dependencies=["Research Firebase Auth documentation"],
            ),
            BreakdownTaskOutput(
                description="Wire login to Firebase backend",
                tag="MODERATE",
                dependencies=["Implement login screen UI"],
            ),
        ])

    @pytest.mark.asyncio
    async def test_returns_stalled_output(self):
        agent = TaskDecomposer(llm=_make_llm_mock(self._sample_breakdown_output()))
        result = await agent.breakdown_stalled_task(self._make_breakdown_input())
        assert isinstance(result, ContractStalledOutput)

    @pytest.mark.asyncio
    async def test_original_task_id_preserved(self):
        agent = TaskDecomposer(llm=_make_llm_mock(self._sample_breakdown_output()))
        result = await agent.breakdown_stalled_task(self._make_breakdown_input())
        assert result.original_task_id == "task_001"

    @pytest.mark.asyncio
    async def test_replacement_tasks_populated(self):
        agent = TaskDecomposer(llm=_make_llm_mock(self._sample_breakdown_output()))
        result = await agent.breakdown_stalled_task(self._make_breakdown_input())
        assert len(result.replacement_tasks) == 3

    @pytest.mark.asyncio
    async def test_no_deep_tasks_in_breakdown(self):
        agent = TaskDecomposer(llm=_make_llm_mock(self._sample_breakdown_output()))
        result = await agent.breakdown_stalled_task(self._make_breakdown_input())
        for task in result.replacement_tasks:
            assert task.tag != TaskTag.DEEP

    @pytest.mark.asyncio
    async def test_deep_tag_in_breakdown_forced_to_moderate(self):
        output = self._sample_breakdown_output()
        output.replacement_tasks[0].tag = "DEEP"
        agent = TaskDecomposer(llm=_make_llm_mock(output))
        result = await agent.breakdown_stalled_task(self._make_breakdown_input())
        assert result.replacement_tasks[0].tag == TaskTag.MODERATE

    @pytest.mark.asyncio
    async def test_no_error_on_success(self):
        agent = TaskDecomposer(llm=_make_llm_mock(self._sample_breakdown_output()))
        result = await agent.breakdown_stalled_task(self._make_breakdown_input())
        assert result.error is None

    @pytest.mark.asyncio
    async def test_error_on_llm_failure(self):
        agent = TaskDecomposer(llm=_make_llm_mock(Exception("timeout")))
        result = await agent.breakdown_stalled_task(self._make_breakdown_input())
        assert result.error is not None
        assert result.error.component == "TaskDecomposer"