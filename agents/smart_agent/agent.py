# PATH: stride_backend/agents/smart_agent/agent.py
# DOMAIN: SMART Agent — goal structuring and negotiation.
# Job ends when goal formulation is confirmed by user.

from __future__ import annotations

from datetime import date

from langchain_openai import ChatOpenAI

from agents.smart_agent.prompts import (
    GOAL_CREATION_NEGOTIATION_PROMPT,
    GOAL_STRUCTURING_PROMPT,
    GoalCreationNegotiationOutput,
    GoalStructuringOutput,
)
from core.schemas.contracts.goal_structuring import (
    Boundary1Input,
    Boundary1Output,
    SmartFormulation,
)
from core.schemas.contracts.shared import BoundaryError


async def _invoke_with_retries(chain, inputs: dict, retries: int = 3):
    """Invoke a LangChain chain with up to `retries` attempts.
    Raises the last exception if all attempts fail."""
    last_exc = None
    for attempt in range(retries):
        try:
            return await chain.ainvoke(inputs)
        except Exception as e:
            last_exc = e
    raise last_exc


def _error_output(
    user_id: str, message: str, attempt_count: int = 3
) -> Boundary1Output:
    """Build a typed failure output. Never raises — always returns a valid Boundary1Output."""
    return Boundary1Output(
        user_id=user_id,
        smart_formulation=SmartFormulation(
            specific="",
            measurable="",
            achievable="",
            relevant="",
            time_bound="",
        ),
        impact_score=1,
        extracted_deadline=None,
        viability_assessment="SmartAgent failed to produce a formulation.",
        conflict_flag=False,
        override_flag=False,
        override_reason=None,
        error=BoundaryError(
            code="PARSE_FAILURE",
            message=message,
            component="SmartAgent",
            retry_count=attempt_count,
        ),
        schema_version=2,
    )


class SmartAgent:

    def __init__(self, llm: ChatOpenAI) -> None:
        self._llm = llm

    async def structure_goal(self, input: Boundary1Input) -> Boundary1Output:
        """
        Receive a confirmed draft from DraftingAgent.
        Return a SMART formulation with impact_score and extracted_deadline.
        Does not write to storage.
        """
        draft = input.confirmed_draft
        chain = GOAL_STRUCTURING_PROMPT | self._llm.with_structured_output(
            GoalStructuringOutput
        )

        try:
            output: GoalStructuringOutput = await _invoke_with_retries(
                chain,
                {
                    "objectives": draft.get("objectives", []),
                    "proposed_milestones": draft.get("proposed_milestones", []),
                    "success_metrics": draft.get("success_metrics", []),
                    "user_context": draft.get("user_context", ""),
                    "today": date.today().isoformat(),
                    "existing_goal_summaries": [
                        g.model_dump() for g in input.existing_goal_summaries
                    ],
                    "distilled_model_snapshot": input.distilled_model_snapshot,
                },
            )
        except Exception as e:
            return _error_output(
                user_id=input.user_id,
                message=f"SmartAgent.structure_goal failed after 3 retries: {e}",
            )

        return Boundary1Output(
            user_id=input.user_id,
            smart_formulation=SmartFormulation(
                specific=output.specific,
                measurable=output.measurable,
                achievable=output.achievable,
                relevant=output.relevant,
                time_bound=output.time_bound,
            ),
            impact_score=output.impact_score,
            extracted_deadline=output.extracted_deadline,
            viability_assessment=output.viability_assessment,
            conflict_flag=output.conflict_flag,
            override_flag=False,
            override_reason=None,
            error=None,
            schema_version=2,
        )

    async def negotiate_goal_creation(
        self,
        input: Boundary1Input,
        previous_assessment: dict,
        user_response: str,
    ) -> Boundary1Output:
        """
        Receive user pushback on a prior SMART assessment.
        Return a revised formulation, or record an override if the user
        provides no new information.
        Does not write to storage.
        """
        draft = input.confirmed_draft
        chain = GOAL_CREATION_NEGOTIATION_PROMPT | self._llm.with_structured_output(
            GoalCreationNegotiationOutput
        )

        try:
            output: GoalCreationNegotiationOutput = await _invoke_with_retries(
                chain,
                {
                    "objectives": draft.get("objectives", []),
                    "proposed_milestones": draft.get("proposed_milestones", []),
                    "success_metrics": draft.get("success_metrics", []),
                    "previous_assessment": previous_assessment,
                    "user_response": user_response,
                    "user_context": draft.get("user_context", ""),
                    "today": date.today().isoformat(),
                },
            )
        except Exception as e:
            return _error_output(
                user_id=input.user_id,
                message=f"SmartAgent.negotiate_goal_creation failed after 3 retries: {e}",
            )

        return Boundary1Output(
            user_id=input.user_id,
            smart_formulation=SmartFormulation(
                specific=output.specific,
                measurable=output.measurable,
                achievable=output.achievable,
                relevant=output.relevant,
                time_bound=output.time_bound,
            ),
            impact_score=output.impact_score,
            extracted_deadline=output.extracted_deadline,
            viability_assessment=output.viability_assessment,
            conflict_flag=False,
            override_flag=output.override_flag,
            override_reason=output.override_reason,
            error=None,
            schema_version=2,
        )
