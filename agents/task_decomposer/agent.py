# PATH: stride_backend/agents/task_decomposer/agent.py
# DOMAIN: TaskDecomposer — generates task graph for a milestone.
# Called once on milestone creation. Called again only for stagnation breakdown.

from __future__ import annotations

from langchain_openai import ChatOpenAI

from agents.task_decomposer.prompts import (
    STALLED_TASK_BREAKDOWN_PROMPT,
    TASK_DECOMPOSITION_PROMPT,
    StalledTaskBreakdownOutput,
    TaskGraphOutput,
)
from core.schemas.contracts.shared import BoundaryError
from core.schemas.contracts.task_decomposition import (
    StalledTaskBreakdownInput,
    StalledTaskBreakdownOutput as ContractStalledOutput,
    TaskDecompositionInput,
    TaskDecompositionOutput,
    TaskDraft,
)
from core.schemas.enums import TaskTag


async def _invoke_with_retries(chain, inputs: dict, retries: int = 3):
    """Invoke a LangChain chain with up to `retries` attempts.
    Raises the last exception if all attempts fail."""
    last_exc = None
    for _ in range(retries):
        try:
            return await chain.ainvoke(inputs)
        except Exception as e:
            last_exc = e
    raise last_exc


def _parse_tag(raw: str, allow_deep: bool = True) -> TaskTag:
    """Safely parse tag string. Defaults to MODERATE on invalid input."""
    try:
        tag = TaskTag(raw.upper())
        if not allow_deep and tag == TaskTag.DEEP:
            return TaskTag.MODERATE
        return tag
    except ValueError:
        return TaskTag.MODERATE


class TaskDecomposer:

    def __init__(self, llm: ChatOpenAI) -> None:
        self._llm = llm

    async def decompose(
        self, input: TaskDecompositionInput
    ) -> TaskDecompositionOutput:
        """
        Generate a complete task graph for a confirmed milestone.
        Tasks have tags and boolean dependency lists.
        Called once on milestone creation.
        Does not write to storage.
        """
        chain = TASK_DECOMPOSITION_PROMPT | self._llm.with_structured_output(
            TaskGraphOutput
        )

        try:
            output: TaskGraphOutput = await _invoke_with_retries(chain, {
                "milestone_description": input.milestone_description,
                "objectives":            input.objectives,
                "success_metrics":       input.success_metrics,
                "previous_task_logs":    [
                    t.model_dump() for t in input.previous_task_logs
                ],
            })
        except Exception as e:
            return TaskDecompositionOutput(
                milestone_id=input.milestone_id,
                tasks=[],
                error=BoundaryError(
                    code="PARSE_FAILURE",
                    message=f"TaskDecomposer.decompose failed after 3 retries: {e}",
                    component="TaskDecomposer",
                    retry_count=3,
                ),
                schema_version=1,
            )

        tasks = [
            TaskDraft(
                description=t.description,
                tag=_parse_tag(t.tag, allow_deep=True),
                dependencies=t.dependencies,
            )
            for t in output.tasks
        ]

        return TaskDecompositionOutput(
            milestone_id=input.milestone_id,
            tasks=tasks,
            error=None,
            schema_version=1,
        )

    async def breakdown_stalled_task(
        self, input: StalledTaskBreakdownInput
    ) -> ContractStalledOutput:
        """
        Break a stalled DEEP task into 2–4 smaller MODERATE or MECHANICAL tasks.
        The last replacement task inherits downstream deps of the original
        — the API route handles that remapping, not this agent.
        Does not write to storage.
        """
        chain = STALLED_TASK_BREAKDOWN_PROMPT | self._llm.with_structured_output(
            StalledTaskBreakdownOutput
        )

        try:
            output: StalledTaskBreakdownOutput = await _invoke_with_retries(chain, {
                "task_description":      input.description,
                "milestone_description": input.milestone_description,
            })
        except Exception as e:
            return ContractStalledOutput(
                original_task_id=input.task_id,
                replacement_tasks=[],
                error=BoundaryError(
                    code="PARSE_FAILURE",
                    message=f"TaskDecomposer.breakdown_stalled_task failed after 3 retries: {e}",
                    component="TaskDecomposer",
                    retry_count=3,
                ),
                schema_version=1,
            )

        replacement_tasks = [
            TaskDraft(
                description=t.description,
                tag=_parse_tag(t.tag, allow_deep=False),  # no DEEP in breakdown
                dependencies=t.dependencies,
            )
            for t in output.replacement_tasks
        ]

        return ContractStalledOutput(
            original_task_id=input.task_id,
            replacement_tasks=replacement_tasks,
            error=None,
            schema_version=1,
        )