# PATH: stride_backend/agents/model_agent/executor.py
# DOMAIN: ModelAgentExecutor — sole writer across all stores.
# Handles post-creation flows: edits, weekly guidance, distillation, feedback.

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from langchain_openai import ChatOpenAI

from agents.model_agent.prompts import (
    GOAL_EDIT_NEGOTIATION_PROMPT,
    TASK_EDIT_NEGOTIATION_PROMPT,
    TIMETABLE_EDIT_NEGOTIATION_PROMPT,
    WEEKLY_GUIDANCE_PROMPT,
    GoalEditNegotiationOutput,
    TaskEditNegotiationOutput,
    TimetableEditNegotiationOutput,
    WeeklyGuidanceOutput,
)
from core.schemas.contracts.execution_engine import WeeklyAggregatedSummary
from core.schemas.contracts.feedback_loop import Boundary3Input, Boundary3Output
from core.schemas.contracts.shared import BoundaryError
from core.schemas.entities import (
    FeedbackEvent,
    GoalStatus,
    PhaseTransition,
    Task,
    TaskStatus,
)
from storage.distilled_store import DistilledStore
from storage.goal_store import GoalStore
from storage.raw_store import RawStore


# ── Retry helper ───────────────────────────────────────────────────────────────

async def _invoke_with_retries(chain, inputs: dict, retries: int = 3):
    last_exc = None
    for _ in range(retries):
        try:
            return await chain.ainvoke(inputs)
        except Exception as e:
            last_exc = e
    raise last_exc


# ── Executor ───────────────────────────────────────────────────────────────────

class ModelAgentExecutor:
    """
    Sole writer across all stores.
    Handles all post-creation flows:
      - Edit negotiation (goal, task, timetable, milestone)
      - Task completion processing
      - Weekly guidance and distillation
    """

    def __init__(
        self,
        raw_store: RawStore,
        distilled_store: DistilledStore,
        goal_store: GoalStore,
        llm: ChatOpenAI,
    ) -> None:
        self._raw_store = raw_store
        self._distilled_store = distilled_store
        self._goal_store = goal_store
        self._llm = llm

    # ── 1. negotiate_goal_edit ─────────────────────────────────────────────────

    async def negotiate_goal_edit(
        self,
        user_id: str,
        goal_id: str,
        proposed_edit: str,
        user_response: str,
    ) -> GoalEditNegotiationOutput:

        goal_result = self._goal_store.get_goal(user_id, goal_id)
        if not goal_result.success:
            return GoalEditNegotiationOutput(
                edit_accepted=False,
                override_flag=False,
                edit_summary="Goal lookup failed.",
                pushback_rationale=goal_result.error.message,
            )

        snapshot_result = self._distilled_store.get_model_snapshot(user_id)
        if not snapshot_result.success:
            return GoalEditNegotiationOutput(
                edit_accepted=False,
                override_flag=False,
                edit_summary="Distilled model lookup failed.",
                pushback_rationale=snapshot_result.error.message,
            )

        chain = GOAL_EDIT_NEGOTIATION_PROMPT | self._llm.with_structured_output(
            GoalEditNegotiationOutput
        )

        try:
            output: GoalEditNegotiationOutput = await _invoke_with_retries(chain, {
                "current_goal":            goal_result.data.model_dump(),
                "proposed_edit":           proposed_edit,
                "user_response":           user_response,
                "distilled_model_snapshot": snapshot_result.data.model_dump(),
            })
        except Exception as e:
            return GoalEditNegotiationOutput(
                edit_accepted=False,
                override_flag=False,
                edit_summary="LLM chain failed after 3 retries.",
                pushback_rationale=str(e),
            )

        if output.edit_accepted and output.revised_goal_description:
            goal = goal_result.data
            goal.name = output.revised_goal_description
            self._goal_store.upsert_goal(goal)

        if output.override_flag:
            self._write_phase_transition(
                user_id=user_id,
                goal_id=goal_id,
                reason=output.override_reason or "User override on goal edit.",
                from_status=goal_result.data.status,
                to_status=goal_result.data.status,
            )

        return output

    # ── 2. negotiate_task_edit ─────────────────────────────────────────────────

    async def negotiate_task_edit(
        self,
        user_id: str,
        task_id: str,
        proposed_edit: str,
        user_response: str,
    ) -> TaskEditNegotiationOutput:

        task_result = self._goal_store.get_task(task_id)
        if not task_result.success:
            return TaskEditNegotiationOutput(
                edit_accepted=False,
                override_flag=False,
                edit_summary="Task lookup failed.",
                pushback_rationale=task_result.error.message,
            )

        task = task_result.data
        goal_result = self._goal_store.get_goal(user_id, task.goal_id)
        goal_context = (
            goal_result.data.name if goal_result.success
            else "Goal context unavailable."
        )

        snapshot_result = self._distilled_store.get_model_snapshot(user_id)
        if not snapshot_result.success:
            return TaskEditNegotiationOutput(
                edit_accepted=False,
                override_flag=False,
                edit_summary="Distilled model lookup failed.",
                pushback_rationale=snapshot_result.error.message,
            )

        chain = TASK_EDIT_NEGOTIATION_PROMPT | self._llm.with_structured_output(
            TaskEditNegotiationOutput
        )

        try:
            output: TaskEditNegotiationOutput = await _invoke_with_retries(chain, {
                "current_task":            task.model_dump(),
                "proposed_edit":           proposed_edit,
                "user_response":           user_response,
                "goal_context":            goal_context,
                "distilled_model_snapshot": snapshot_result.data.model_dump(),
            })
        except Exception as e:
            return TaskEditNegotiationOutput(
                edit_accepted=False,
                override_flag=False,
                edit_summary="LLM chain failed after 3 retries.",
                pushback_rationale=str(e),
            )

        if output.edit_accepted and output.revised_task_description:
            task.description = output.revised_task_description
            self._goal_store.upsert_task(task)

        if output.override_flag:
            self._write_phase_transition(
                user_id=user_id,
                goal_id=task.goal_id,
                reason=output.override_reason or "User override on task edit.",
                from_status=GoalStatus.ACTIVE,
                to_status=GoalStatus.ACTIVE,
            )

        return output

    # ── 3. negotiate_timetable_edit ────────────────────────────────────────────

    async def negotiate_timetable_edit(
        self,
        user_id: str,
        proposed_edit: str,
        user_response: str,
        current_timetable_summary: str,
    ) -> TimetableEditNegotiationOutput:

        snapshot_result = self._distilled_store.get_model_snapshot(user_id)
        if not snapshot_result.success:
            return TimetableEditNegotiationOutput(
                edit_accepted=False,
                priority_conflict_flagged=False,
                override_flag=False,
                edit_summary="Distilled model lookup failed.",
                pushback_rationale=snapshot_result.error.message,
            )

        priority_result = self._distilled_store.get_priority_list(user_id)
        priority_snapshot = (
            priority_result.data.model_dump()
            if priority_result.success else {}
        )

        chain = TIMETABLE_EDIT_NEGOTIATION_PROMPT | self._llm.with_structured_output(
            TimetableEditNegotiationOutput
        )

        try:
            output: TimetableEditNegotiationOutput = await _invoke_with_retries(chain, {
                "current_timetable_summary": current_timetable_summary,
                "proposed_edit":            proposed_edit,
                "user_response":            user_response,
                "distilled_model_snapshot": snapshot_result.data.model_dump(),
                "priority_list_snapshot":   priority_snapshot,
            })
        except Exception as e:
            return TimetableEditNegotiationOutput(
                edit_accepted=False,
                priority_conflict_flagged=False,
                override_flag=False,
                edit_summary="LLM chain failed after 3 retries.",
                pushback_rationale=str(e),
            )

        if output.override_flag and output.priority_conflict_flagged:
            if priority_result.success:
                self._distilled_store.write_priority_list(priority_result.data)
            self._write_phase_transition(
                user_id=user_id,
                goal_id="timetable",
                reason="User override on timetable edit with priority conflict.",
                from_status=GoalStatus.ACTIVE,
                to_status=GoalStatus.ACTIVE,
            )

        return output

    # ── 4. process_task_completion ─────────────────────────────────────────────

    async def process_task_completion(
        self,
        boundary_input: Boundary3Input,
    ) -> Boundary3Output:
        """
        Write feedback event to RawStore first.
        Then update task status to COMPLETED in GoalStore.
        No significance check in v1 — weekly distillation only.
        """
        event = FeedbackEvent(
            id=str(uuid4()),
            task_id=boundary_input.task_id,
            goal_id=boundary_input.goal_id,
            user_id=boundary_input.user_id,
            milestone_id=boundary_input.milestone_id,
            completed_at=datetime.fromisoformat(boundary_input.completion_timestamp),
            note=boundary_input.user_note,
            significance_check_triggered=False,
        )

        # Write event first — always
        write_result = self._raw_store.append_feedback_event(
            boundary_input.user_id, event
        )
        if not write_result.success:
            return Boundary3Output(
                user_id=boundary_input.user_id,
                task_id=boundary_input.task_id,
                success=False,
                error=BoundaryError(
                    code="WRITE_ERROR",
                    message=write_result.error.message,
                    component="ModelAgentExecutor",
                    retry_count=0,
                ),
            )

        # Update task status
        task_update = self._goal_store.update_task_status(
            boundary_input.task_id, TaskStatus.COMPLETED
        )
        if not task_update.success:
            return Boundary3Output(
                user_id=boundary_input.user_id,
                task_id=boundary_input.task_id,
                success=False,
                error=BoundaryError(
                    code="WRITE_ERROR",
                    message=task_update.error.message,
                    component="ModelAgentExecutor",
                    retry_count=0,
                ),
            )

        return Boundary3Output(
            user_id=boundary_input.user_id,
            task_id=boundary_input.task_id,
            success=True,
            error=None,
        )

    # ── 5. get_weekly_guidance ─────────────────────────────────────────────────

    async def get_weekly_guidance(
        self,
        user_id: str,
        weekly_summary: WeeklyAggregatedSummary,
        max_workable_hours: Optional[int] = None,
        expired_goal_ids: Optional[List[str]] = None,
    ) -> WeeklyGuidanceOutput:
        """
        Receive pre-aggregated weekly summary from Python.
        Generate qualitative guidance text.
        Run weekly distillation — update DistilledModel.

        max_workable_hours: fetched from onboarding profile in weekly.py and
        passed through so the prompt can compute the expected activity range
        for disposition calibration (Fix 2, Brief PROMPT-01).

        expired_goal_ids: goals marked EXPIRED in the weekly cycle expiry check
        (Fix 4A/4B, Brief PROMPT-01). Passed to the prompt so guidance can
        surface a closure/extension prompt before any other recommendations.
        """
        active_goals_result = self._goal_store.get_active_goals(user_id)
        active_goals = (
            [g.model_dump() for g in active_goals_result.data]
            if active_goals_result.success else []
        )

        priority_result = self._distilled_store.get_priority_list(user_id)
        priority_snapshot = (
            priority_result.data.model_dump()
            if priority_result.success else {}
        )

        chain = WEEKLY_GUIDANCE_PROMPT | self._llm.with_structured_output(
            WeeklyGuidanceOutput
        )

        try:
            output: WeeklyGuidanceOutput = await _invoke_with_retries(chain, {
                "user_id":                user_id,
                "max_workable_hours":     max_workable_hours or "not available",
                "weekly_summary":         weekly_summary.model_dump(),
                "active_goals":           active_goals,
                "priority_list_snapshot": priority_snapshot,
                "expired_goal_ids":       expired_goal_ids or [],
            })
        except Exception as e:
            return WeeklyGuidanceOutput(
                guidance_type="check_in_prompt",
                recommendations=[],
                thin_input_flag=True,
                reasoning_summary="LLM chain failed after 3 retries.",
                check_in_prompt="How are you getting on with your goals this week?",
            )

        # Update DistilledModel with latest active goals
        snapshot_result = self._distilled_store.get_model_snapshot(user_id)
        if snapshot_result.success:
            snapshot = snapshot_result.data
            self._distilled_store.write_model_snapshot(snapshot)

        return output

    # ── Private helpers ────────────────────────────────────────────────────────

    def _write_phase_transition(
        self,
        user_id: str,
        goal_id: str,
        reason: str,
        from_status: GoalStatus,
        to_status: GoalStatus,
    ) -> None:
        transition = PhaseTransition(
            id=str(uuid4()),
            goal_id=goal_id,
            user_id=user_id,
            from_status=from_status.value,
            to_status=to_status.value,
            transitioned_at=datetime.now(timezone.utc),
            reason=reason,
        )
        self._raw_store.append_phase_transition(user_id, transition)