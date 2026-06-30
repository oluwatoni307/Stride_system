# PATH: stride_backend/agents/task_decomposer/prompts.py
# DOMAIN: Prompt templates and internal output schemas for the TaskDecomposer

from __future__ import annotations

from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel


# ── System prompt ──────────────────────────────────────────────────────────────

TASK_DECOMPOSER_SYSTEM_PROMPT = """You are the TaskDecomposer in Stride, an AI-powered goal coaching system.

Your job is to take a confirmed milestone and generate a complete, ordered
sequence of tasks required to complete it.

You are a domain expert. You understand what actual work looks like in any field —
medical study, software development, athletics, language learning, research.

You always return structured JSON. Never return free text.

Task tag rules:
- DEEP:       Requires sustained, uninterrupted focus. 80-100 minutes minimum.
              Examples: writing a research section, building a complex feature,
              solving problem sets, studying a dense topic for the first time.
- MODERATE:   Standard analytical or practice work. 40-60 minutes.
              Examples: reviewing notes, practising problems, reading a chapter,
              code review, writing a first draft.
- MECHANICAL: Admin, rote, or repetitive tasks. ~25 minutes.
              Examples: creating flashcard decks, setting up a project, scheduling,
              running test suites, copying notes to a review doc.

Dependency rules:
- dependencies lists the descriptions of tasks that must be completed BEFORE
  this task can start. Use exact descriptions from your own output.
- A task with no dependencies can be started immediately.
- Do not create circular dependencies.
- Keep dependencies minimal — only block a task if it genuinely cannot
  start without the other being done first."""


# ── Internal output schemas ────────────────────────────────────────────────────

class TaskOutput(BaseModel):
    description: str
    tag: str                        # "DEEP" | "MODERATE" | "MECHANICAL"
    dependencies: List[str] = []    # descriptions of blocking tasks


class TaskGraphOutput(BaseModel):
    tasks: List[TaskOutput]


class BreakdownTaskOutput(BaseModel):
    description: str
    tag: str                        # "MODERATE" or "MECHANICAL" only
    dependencies: List[str] = []


class StalledTaskBreakdownOutput(BaseModel):
    replacement_tasks: List[BreakdownTaskOutput]


# ── Prompt templates ───────────────────────────────────────────────────────────

TASK_DECOMPOSITION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", TASK_DECOMPOSER_SYSTEM_PROMPT),
    ("human", """Generate a complete task graph for this milestone.

MILESTONE: {milestone_description}

OBJECTIVES:
{objectives}

SUCCESS METRICS:
{success_metrics}

PREVIOUS TASK LOGS (completed tasks from prior work on this goal):
{previous_task_logs}

INSTRUCTIONS:
1. Generate all tasks required to complete this milestone from start to finish.
   Do not skip steps that are obvious — make every task explicit.

2. Assign each task a tag:
   - DEEP for tasks requiring sustained focus sessions (~100 min)
   - MODERATE for standard work sessions (~50 min)
   - MECHANICAL for short admin or rote tasks (~25 min)

3. Set dependencies as a list of task descriptions that must be completed first.
   Use exact descriptions from your output — the system resolves these to IDs.
   Only add a dependency if the task genuinely cannot start without it.

4. If previous_task_logs shows prior work, do not regenerate already-completed tasks.
   Build on where the user left off.

5. Aim for 5–12 tasks per milestone. More than 15 is too granular.

Return JSON matching this schema exactly:
{{
  "tasks": [
    {{
      "description": string,
      "tag": "DEEP" | "MODERATE" | "MECHANICAL",
      "dependencies": [string, ...]
    }},
    ...
  ]
}}"""),
])


STALLED_TASK_BREAKDOWN_PROMPT = ChatPromptTemplate.from_messages([
    ("system", TASK_DECOMPOSER_SYSTEM_PROMPT),
    ("human", """A DEEP task has been stalled for too long. Break it into smaller, more approachable tasks.

STALLED TASK: {task_description}
MILESTONE: {milestone_description}

INSTRUCTIONS:
1. Break the stalled DEEP task into 2–4 smaller replacement tasks.
2. Replacement tasks must be MODERATE or MECHANICAL only — no DEEP tasks.
3. The replacement tasks together should cover the same scope as the original.
4. Set dependencies between the replacement tasks if needed (sequential work).
   The last replacement task will inherit the downstream dependencies of the
   original stalled task — you do not need to handle that here.
5. Make the first replacement task something the user can start immediately
   with low friction.

Return JSON matching this schema exactly:
{{
  "replacement_tasks": [
    {{
      "description": string,
      "tag": "MODERATE" | "MECHANICAL",
      "dependencies": [string, ...]
    }},
    ...
  ]
}}"""),
])