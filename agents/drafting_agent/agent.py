# PATH: stride_backend/agents/drafting_agent/agent.py
# DOMAIN: Drafting Agent — converts raw goal intent into structured draft.
# Job ends when user confirms draft. Passes to SmartAgent.

from __future__ import annotations

from langchain_openai import ChatOpenAI

from agents.drafting_agent.prompts import (
    GOAL_DRAFT_REVISION_PROMPT,
    GOAL_DRAFTING_PROMPT,
    GoalDraftOutput,
)
from core.schemas.contracts.goal_drafting import (
    DraftingInput,
    DraftingOutput,
    DraftingRevisionInput,
    ProposedMilestone,
)
from core.schemas.contracts.shared import BoundaryError
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


def _error_output(user_id: str, message: str, retry_count: int = 3) -> DraftingOutput:
    """Build a typed failure output. Never raises."""
    return DraftingOutput(
        user_id=user_id,
        objectives=[],
        proposed_milestones=[],
        success_metrics=[],
        error=BoundaryError(
            code="PARSE_FAILURE",
            message=message,
            component="DraftingAgent",
            retry_count=retry_count,
        ),
        schema_version=1,
    )


def _parse_tag(raw: str) -> TaskTag:
    """Safely parse suggested_tag from LLM output. Defaults to MODERATE."""
    try:
        return TaskTag(raw.upper())
    except ValueError:
        return TaskTag.MODERATE


class DraftingAgent:

    def __init__(self, llm: ChatOpenAI) -> None:
        self._llm = llm

    async def draft_goal(self, input: DraftingInput) -> DraftingOutput:
        """
        Receive raw goal text and user context.
        Return a structured draft: objectives, milestones, success metrics.
        Does not write to storage.
        """
        chain = GOAL_DRAFTING_PROMPT | self._llm.with_structured_output(
            GoalDraftOutput
        )

        try:
            output: GoalDraftOutput = await _invoke_with_retries(chain, {
                "raw_goal":                  input.raw_goal,
                "user_context":              input.user_context,
                "distilled_model_snapshot":  input.distilled_model_snapshot,
            })
        except Exception as e:
            return _error_output(
                user_id=input.user_id,
                message=f"DraftingAgent.draft_goal failed after 3 retries: {e}",
            )

        milestones = [
            ProposedMilestone(
                description=m.description,
                objectives=m.objectives,
                suggested_tag=_parse_tag(m.suggested_tag),
            )
            for m in output.proposed_milestones
        ]

        return DraftingOutput(
            user_id=input.user_id,
            objectives=output.objectives,
            proposed_milestones=milestones,
            success_metrics=output.success_metrics,
            error=None,
            schema_version=1,
        )

    async def revise_draft(self, input: DraftingRevisionInput) -> DraftingOutput:
        """
        Receive user feedback on a previous draft.
        Return a revised draft with the requested changes applied.
        Does not write to storage.
        """
        prev = input.previous_draft
        chain = GOAL_DRAFT_REVISION_PROMPT | self._llm.with_structured_output(
            GoalDraftOutput
        )

        try:
            output: GoalDraftOutput = await _invoke_with_retries(chain, {
                "previous_objectives":     prev.objectives,
                "previous_milestones":     [
                    m.model_dump() for m in prev.proposed_milestones
                ],
                "previous_success_metrics": prev.success_metrics,
                "user_response":           input.user_response,
            })
        except Exception as e:
            return _error_output(
                user_id=input.previous_draft.user_id,
                message=f"DraftingAgent.revise_draft failed after 3 retries: {e}",
            )

        milestones = [
            ProposedMilestone(
                description=m.description,
                objectives=m.objectives,
                suggested_tag=_parse_tag(m.suggested_tag),
            )
            for m in output.proposed_milestones
        ]

        return DraftingOutput(
            user_id=input.previous_draft.user_id,
            objectives=output.objectives,
            proposed_milestones=milestones,
            success_metrics=output.success_metrics,
            error=None,
            schema_version=1,
        )