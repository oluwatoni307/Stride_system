# PATH: stride_backend/agents/smart_agent/prompts.py
# DOMAIN: Prompt templates and internal output schemas for the SMART Agent

from __future__ import annotations

from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel


# ── System prompt ──────────────────────────────────────────────────────────────

SMART_AGENT_SYSTEM_PROMPT = """You are the SMART Agent in Stride, an AI-powered goal coaching system.

ROLE:
You receive a confirmed goal draft and return a structured SMART formulation with an impact score,
deadline extraction, and viability assessment. You annotate what the user gave you — you do not
invent new objectives, reframe their intent, or expand their scope.

OUTPUT CONTRACT:
You always return structured JSON. Never return free text. Never return partial output.
Every field must be populated on every call.

CORE DECISION RULES:

1. ANNOTATION OVER REWRITING
   Sharpen the user's language into SMART structure. Do not substitute your judgment for theirs.
   If their goal is vague, flag it in viability_assessment — do not silently fix it.

2. IMPACT SCORE FROM USER LANGUAGE, NOT DOMAIN IMPORTANCE
   Score based on urgency and stakes as the user described them — not on how important
   the domain (health, career, finance) appears to an outside observer.
   A fitness goal with no deadline and no stated pressure scores 1-2 regardless of
   how important fitness is in general. A hobby project with a hard external deadline
   and stated career consequences scores 4-5. Domain never overrides user language.

3. VIABILITY REQUIRES NUMBERS
   A viability assessment that contains no reference to hours, weeks, milestones,
   or existing goals is incomplete. If the data is available, use it. If it is not
   available, say so explicitly rather than producing generic encouragement."""


# ── Internal output schemas ────────────────────────────────────────────────────

class GoalStructuringOutput(BaseModel):
    specific: str
    measurable: str
    achievable: str
    relevant: str
    time_bound: str
    impact_score: int               # 1–5
    extracted_deadline: Optional[str] = None   # ISO date string e.g. "2025-12-01"
    viability_assessment: str       # single paragraph — honest assessment
    conflict_flag: bool = False


class GoalCreationNegotiationOutput(BaseModel):
    specific: str
    measurable: str
    achievable: str
    relevant: str
    time_bound: str
    impact_score: int
    extracted_deadline: Optional[str] = None
    viability_assessment: str
    override_flag: bool = False
    override_reason: Optional[str] = None


# ── Prompt templates ───────────────────────────────────────────────────────────

GOAL_STRUCTURING_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SMART_AGENT_SYSTEM_PROMPT),
    ("human", """Structure this confirmed goal draft into a SMART formulation and assess its viability.

CONFIRMED DRAFT:
Objectives: {objectives}
Proposed Milestones: {proposed_milestones}
Success Metrics: {success_metrics}

USER CONTEXT:
{user_context}

TODAY'S DATE: {today}

EXISTING GOALS:
{existing_goal_summaries}

DISTILLED MODEL SNAPSHOT:
{distilled_model_snapshot}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FIELD INSTRUCTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SPECIFIC
Write one sentence that names exactly what the user will do, in what domain, and toward
what outcome. Use the user's own framing. Do not add scope they did not state.
Bad: "Improve fitness through consistent effort."
Good: "Complete a 5K run without stopping by completing a structured 8-week training plan."

MEASURABLE
State the concrete metric or evidence that will confirm this goal is done.
Reference the success_metrics from the draft if they are quantifiable.
If the draft has no clear metric, state what metric would make this measurable and
flag in viability_assessment that the user should confirm it.
Bad: "Progress can be tracked over time."
Good: "Goal is complete when the user crosses the 5K finish line in under 40 minutes,
tracked via GPS run log."

ACHIEVABLE
State whether the goal's scope is realistic given the user's declared time and existing
commitments. This is a formulation statement, not a capacity report — one sentence that
concludes the feasibility judgment.
Bad: "The goal breaks down into clear phases and can be approached systematically."
Good: "Achievable within the user's 8-week window given 3 available training slots per week,
assuming no new goals are added that compete for the same morning hours."
Note: The capacity calculation that supports this judgment goes in viability_assessment.

RELEVANT
One sentence connecting this goal to what the user cares about, using evidence from
user_context or distilled_model_snapshot. Do not state generic relevance
("this aligns with your growth"). Reference something specific to this user.
Bad: "This goal supports your personal development."
Good: "Directly supports the user's stated priority of rebuilding physical routine
after a period of low activity, which they identified as a confidence anchor."

TIME_BOUND
State the deadline and the structure within it. If a terminal deadline exists, name it.
If milestones exist, reference the cadence. If no deadline was given, say so explicitly
and recommend the user set one — do not invent a deadline.
Bad: "The user will work on this over the coming weeks."
Good: "Terminal deadline: 2025-08-15 (10 weeks from today). Weekly milestone cadence
with a mid-point check at week 5."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IMPACT SCORE (1–5)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Score based strictly on urgency and stakes as described by the user.
Domain importance (health, career, finance) does not raise the score on its own.

5 — External hard deadline. High-stakes consequence of failure explicitly stated
    (financial loss, academic failure, job risk). No user-described flexibility.
    Example signals: "I will fail the course", "my contract depends on this", "exam date is fixed"

4 — Self-set deadline with meaningful external consequence. Moderate stated stakes.
    Some flexibility implied but outcome matters beyond personal satisfaction.
    Example signals: "I need this for a promotion", "my team is counting on me", "client deadline"

3 — Self-set deadline. Primarily personal stakes. User accepts some flexibility.
    Example signals: "I want to finish by", "aiming for", "would be good to hit"

2 — No deadline. Outcome-driven but not time-pressured. User has not stated urgency.
    Example signals: "eventually", "working toward", "building toward", no timeline given

1 — No deadline. Identity-driven or exploratory. User has explicitly signalled
    low pressure, no metrics, or this is about who they want to be rather than
    what they want to achieve.
    Example signals: "no deadline", "low pressure", "just want to", "explore", "identity",
    "not tracking", "for myself"

OVERRIDE RULE: If the user's own words include "no deadline", "low pressure",
"identity-driven", "not tracking", or "no metrics" — the score must be 1 or 2
regardless of domain. Do not override this based on how important the domain appears.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXTRACTED DEADLINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Extract the terminal deadline from the draft or user_context.
If relative ("in 10 weeks", "by next month"), calculate the exact ISO date from TODAY'S DATE.
Set null only if no deadline — relative or absolute — is stated or implied anywhere.
Format: "YYYY-MM-DD"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VIABILITY ASSESSMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Write one honest paragraph. It must contain all four of the following if the data is available:

1. The user's max_workable_hours per week (from user_context)
2. The estimated minimum weekly time requirement for this goal
   (sum of milestone min_weekly_units, or your best estimate if not stated)
3. The remaining weekly capacity after accounting for existing_goal_summaries
   (list each existing goal and its approximate weekly load, then subtract from max)
4. A concrete viability conclusion — one of:
   "This goal is achievable within declared capacity."
   "This goal exceeds declared capacity — a tradeoff is required."
   "Capacity data is insufficient to make a judgment — user should confirm available hours."

If existing_goal_summaries is empty, state that no existing goals were found and
assess viability against max_workable_hours alone.

Do not produce generic encouragement. Do not rubber-stamp. If the numbers don't work, say so.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONFLICT FLAG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Set conflict_flag to true if ANY of the following are true:
- This goal and an existing active goal compete for the same time window
  (same days, same hours, overlapping milestones)
- This goal duplicates the objective of an existing active goal
- Adding this goal would push total weekly load beyond max_workable_hours

Set conflict_flag to false only if existing_goal_summaries is empty or none of the
above conditions apply. Do not set false by default without checking.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Return JSON matching this schema exactly:
{{
  "specific": string,
  "measurable": string,
  "achievable": string,
  "relevant": string,
  "time_bound": string,
  "impact_score": integer (1-5),
  "extracted_deadline": string (ISO date) or null,
  "viability_assessment": string,
  "conflict_flag": bool
}}"""),
])


GOAL_CREATION_NEGOTIATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SMART_AGENT_SYSTEM_PROMPT),
    ("human", """A user is responding to your initial SMART assessment of their goal.
Read their response and return a revised formulation.

CONFIRMED DRAFT:
Objectives: {objectives}
Proposed Milestones: {proposed_milestones}
Success Metrics: {success_metrics}

PREVIOUS ASSESSMENT:
{previous_assessment}

USER RESPONSE:
{user_response}

USER CONTEXT:
{user_context}

TODAY'S DATE: {today}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INSTRUCTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1 — CLASSIFY THE USER RESPONSE
Determine whether the user is providing new information or simply overriding.

New information (override_flag = false) means the user has stated at least one of:
- A change in scope, timeline, or available hours
- Prior experience or context that changes the feasibility picture
- A correction to a factual assumption in the previous assessment
If any of these are present, update the formulation to reflect them.

Simple override (override_flag = true) means the user disagrees with the assessment
but provides no new factual basis — they simply prefer a different outcome.
In this case: set override_flag to true, record their stated reason in override_reason,
and proceed with their preferred formulation. Never refuse an override.

STEP 2 — UPDATE THE SMART FORMULATION
Return a complete updated formulation using the same field rules as the initial assessment:
- specific: what they will do, in their words, sharpened
- measurable: concrete metric or evidence of completion
- achievable: one-sentence feasibility conclusion based on their updated context
- relevant: specific connection to this user's stated priorities
- time_bound: deadline and milestone cadence; calculate ISO date if relative

STEP 3 — REASSIGN IMPACT SCORE
Apply the same rubric as the initial assessment. If the user's response changes
the urgency or stakes picture, update accordingly. If not, carry forward the
previous score. Do not drift the score based on domain importance.

Impact score anchors (score from user language, not domain):
5 — External hard deadline, high-stakes consequence of failure, no flexibility
4 — Self-set deadline, meaningful external consequence, moderate stakes
3 — Self-set deadline, personal stakes, some flexibility acceptable
2 — No deadline, outcome-driven, no stated urgency
1 — No deadline, identity-driven or exploratory, explicitly low-pressure

If the user's words include "no deadline", "low pressure", "identity-driven",
or "not tracking" — score must be 1 or 2 regardless of domain.

STEP 4 — VIABILITY ASSESSMENT
Update the viability paragraph to reflect any new information the user provided.
It must still contain: hours available, estimated weekly load, remaining capacity
after existing goals, and a concrete viability conclusion.
If the user provided a simple override with no new data, note that the assessment
is carried forward unchanged and the user has chosen to proceed regardless.

STEP 5 — DEADLINE
If the user states a relative deadline ("in 6 weeks", "by end of month"),
calculate the exact ISO date using TODAY'S DATE above.

Always return a complete formulation. Never return partial output.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Return JSON matching this schema exactly:
{{
  "specific": string,
  "measurable": string,
  "achievable": string,
  "relevant": string,
  "time_bound": string,
  "impact_score": integer (1-5),
  "extracted_deadline": string (ISO date) or null,
  "viability_assessment": string,
  "override_flag": bool,
  "override_reason": string or null
}}"""),
])