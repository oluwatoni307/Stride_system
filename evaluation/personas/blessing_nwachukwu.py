"""
evaluation/personas/blessing_nwachukwu.py

Persona 5 — Blessing Nwachukwu. 23, Enugu. Post-NYSC, job-hunting.
High energy, anxious about peers, fast-paced. Arrives wanting to do too much.

Layer B targets:
  - Capacity conflict trigger    (Day 1: 3 goals simultaneously)
  - Mid-week pro-rata adjustment (goals confirmed same week)
  - Ceiling reached              (Month 2: fast output exhausts max_weekly_units)
  - Anti-clumping                (Month 2: consecutive pulls from same milestone)
  - Urgency multiplier           (Month 3: job interview short deadline)
  - Tri-Vector normalization     (all multi-milestone points)

CAPACITY CONFLICT MATH:
  max_workable_hours = 20.0 (no job, no dependents, high availability)
  conflict threshold = 20.0 × 3 = 60 min_weekly_units
  Three goals submitted simultaneously. If each goal's milestones each
  carry min_weekly_units ≥ 3, the combined total (3 goals × 2+ milestones
  × 3 units) should comfortably exceed 60 — forcing the conflict.
  The system's response to this is the key Layer B check.
  If conflict does NOT trigger: Layer B Fail — log it.

NOTE: Blessing has high capacity but the conflict threshold is proportionally
higher too (× 3 of 20hrs = 60 units). The scripts submits all 3 goals in
week 1 in quick succession. The third confirm_goal call is the trigger point.
"""

USER_ID = "blessing_nwachukwu"

CONTEXT: dict = {}

# Capacity: no job, no dependents. Full days available.
# High max_workable_hours — but the conflict threshold scales with this,
# so submitting 3 goals simultaneously should still trigger it.
ONBOARDING_PAYLOAD = {
    "user_id": USER_ID,
    "max_workable_hours": 20.0,
    "weekday_blocks": [
        {
            "label": "morning deep work",
            "start_time": "08:00",
            "end_time": "12:00",
            "energy_level": "HIGH",
        },
        {
            "label": "afternoon session",
            "start_time": "14:00",
            "end_time": "17:00",
            "energy_level": "MEDIUM",
        },
    ],
    "weekend_blocks": [
        {
            "label": "Saturday morning",
            "start_time": "09:00",
            "end_time": "12:00",
            "energy_level": "HIGH",
        },
        {
            "label": "Sunday light work",
            "start_time": "15:00",
            "end_time": "17:00",
            "energy_level": "LOW",
        },
    ],
}


def _current_week_monday() -> str:
    from datetime import date, timedelta
    today = date.today()
    return (today - timedelta(days=today.weekday())).isoformat()


WEEK_1_MONDAY = _current_week_monday()


def _week_date(n: int) -> str:
    from datetime import date, timedelta
    anchor = date.fromisoformat(WEEK_1_MONDAY)
    return (anchor + timedelta(weeks=n - 1)).isoformat()


SCRIPT = [
    # ─────────────── MONTH 1 — 3 goals day 1, capacity conflict ─────────────
    # Goal 1: Land a job. Urgent framing, no fixed deadline yet.
    {
        "week": 1,
        "event_type": "draft_goal",
        "path": "/goals/draft",
        "payload": {
            "user_id": USER_ID,
            "raw_goal": "Land a job in tech or product management as fast as possible.",
            "user_context": (
                "Just finished NYSC, actively job-hunting. No income yet, "
                "living with parents. High urgency — peers are already "
                "employed. Has lots of free time to dedicate."
            ),
        },
        "save_as": "job_draft",
    },
    {
        "week": 1,
        "event_type": "structure_goal",
        "path": "/goals/structure",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{job_draft}}",
            "existing_goal_summaries": [],
        },
        "save_as": "job_structured",
    },
    {
        "week": 1,
        "event_type": "confirm_goal",
        "path": "/goals/confirm",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{job_draft}}",
            "smart_assessment": "{{job_structured}}",
            "week_start": WEEK_1_MONDAY,
        },
        "save_as": "job_confirmed",
    },
    # Goal 2: Learn a skill (e.g. SQL/data analytics). Also urgent framing.
    {
        "week": 1,
        "event_type": "draft_goal",
        "path": "/goals/draft",
        "payload": {
            "user_id": USER_ID,
            "raw_goal": "Learn SQL and data analytics properly — I keep seeing it in job listings.",
            "user_context": (
                "Wants to add this skill to strengthen job applications. "
                "Frames it as urgent. Already submitted a job-search goal "
                "this same session."
            ),
        },
        "save_as": "skill_draft",
    },
    {
        "week": 1,
        "event_type": "structure_goal",
        "path": "/goals/structure",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{skill_draft}}",
            "existing_goal_summaries": "{{ACTIVE_GOAL_SUMMARIES}}",
        },
        "save_as": "skill_structured",
    },
    {
        "week": 1,
        "event_type": "confirm_goal",
        "path": "/goals/confirm",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{skill_draft}}",
            "smart_assessment": "{{skill_structured}}",
            "week_start": WEEK_1_MONDAY,
        },
        "save_as": "skill_confirmed",
    },
    # Goal 3: Build a portfolio project. Also framed as urgent.
    # This third confirm_goal is the capacity conflict trigger point.
    {
        "week": 1,
        "event_type": "draft_goal",
        "path": "/goals/draft",
        "payload": {
            "user_id": USER_ID,
            "raw_goal": (
                "Build a portfolio project — a data dashboard or product "
                "case study — that I can show in interviews."
            ),
            "user_context": (
                "Wants this done ASAP to support job applications. "
                "Already submitted job-search and SQL learning goals today."
            ),
        },
        "save_as": "portfolio_draft",
    },
    {
        "week": 1,
        "event_type": "structure_goal",
        "path": "/goals/structure",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{portfolio_draft}}",
            "existing_goal_summaries": "{{ACTIVE_GOAL_SUMMARIES}}",
        },
        "save_as": "portfolio_structured",
        "notes": (
            "Layer A Criterion 2 (Goal Viability): three concurrent urgent "
            "goals submitted on day 1. Does structure_goal surface a "
            "viability concern at this point, or produce another unchecked "
            "milestone plan?"
        ),
    },
    {
        "week": 1,
        "event_type": "confirm_goal",
        "path": "/goals/confirm",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{portfolio_draft}}",
            "smart_assessment": "{{portfolio_structured}}",
            "week_start": WEEK_1_MONDAY,
        },
        "save_as": "portfolio_confirmed",
        "expect_status": 409,
        "notes": (
            "Layer B: capacity conflict trigger. This is the 3rd goal "
            "confirm in week 1. new_total_min_weekly_units should exceed "
            "max_workable_hours × 3 = 60 here. If the system does NOT "
            "raise a conflict, that is a Layer B Fail. "
            "Layer B: mid-week pro-rata — all three goals confirmed same "
            "week, mid-week pro-rata adjustment should apply to at least "
            "the 2nd and 3rd goals. "
            "expect_status=409 set after confirming the B-03 fix (INF-01) "
            "fires correctly on this step — see core/scheduling/"
            "capacity_conflict.py. The harness halts here by design; this "
            "is the correct, expected stopping point for this script, not "
            "a failure to chase further."
        ),
    },

    # ─────────────── MONTH 2 — High output, ceiling test ────────────────────
    # Blessing is fast-moving. Pull multiple times in a single week to
    # exhaust max_weekly_units. Layer B: ceiling reached check.
    # Also tests anti-clumping — 3rd consecutive pull from same milestone
    # should be redirected.
    {
        "week": 1,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "HIGH",
            "consecutive_pull_count": 0,
        },
        "save_as": "pull_w1_a",
    },
    {
        "week": 1,
        "event_type": "complete_task",
        "path": "/tasks/complete",
        "payload": {
            "user_id": USER_ID,
            "task_id": "{{pull_w1_a.pulled_task.task_id}}",
            "goal_id": "{{pull_w1_a.pulled_task.goal_id}}",
            "milestone_id": "{{pull_w1_a.pulled_task.milestone_id}}",
        },
    },
    {
        "week": 1,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(1)},
    },
    {
        "week": 2,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "HIGH",
            "consecutive_pull_count": 0,
        },
        "save_as": "pull_w2_a",
    },
    {
        "week": 2,
        "event_type": "complete_task",
        "path": "/tasks/complete",
        "payload": {
            "user_id": USER_ID,
            "task_id": "{{pull_w2_a.pulled_task.task_id}}",
            "goal_id": "{{pull_w2_a.pulled_task.goal_id}}",
            "milestone_id": "{{pull_w2_a.pulled_task.milestone_id}}",
        },
    },
    # Second pull same week — consecutive_pull_count=1.
    {
        "week": 2,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "HIGH",
            "consecutive_pull_count": 1,
        },
        "save_as": "pull_w2_b",
    },
    {
        "week": 2,
        "event_type": "complete_task",
        "path": "/tasks/complete",
        "payload": {
            "user_id": USER_ID,
            "task_id": "{{pull_w2_b.pulled_task.task_id}}",
            "goal_id": "{{pull_w2_b.pulled_task.goal_id}}",
            "milestone_id": "{{pull_w2_b.pulled_task.milestone_id}}",
        },
    },
    # Third pull same week — if pull_w2_a and pull_w2_b were from the same
    # milestone, this should trigger anti-clumping and redirect elsewhere.
    # Layer B: anti-clumping check.
    {
        "week": 2,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "HIGH",
            "consecutive_pull_count": 2,
        },
        "save_as": "pull_w2_c",
        "notes": (
            "Layer B: anti-clumping check. If pull_w2_a and pull_w2_b "
            "were from the same MODERATE/MECHANICAL milestone, this pull "
            "should exclude that milestone and serve from elsewhere. "
            "Verify milestone_id on pull_w2_c differs from pull_w2_a/b."
        ),
    },
    {
        "week": 2,
        "event_type": "complete_task",
        "path": "/tasks/complete",
        "payload": {
            "user_id": USER_ID,
            "task_id": "{{pull_w2_c.pulled_task.task_id}}",
            "goal_id": "{{pull_w2_c.pulled_task.goal_id}}",
            "milestone_id": "{{pull_w2_c.pulled_task.milestone_id}}",
        },
    },
    # Fourth pull — ceiling test. If all milestones have hit max_weekly_units,
    # this should return ALL_CEILINGS_REACHED.
    {
        "week": 2,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "MEDIUM",
            "consecutive_pull_count": 3,
        },
        "save_as": "pull_w2_ceiling",
        "notes": (
            "Layer B: ceiling reached check. After 3 completions in week 2, "
            "active milestones may have hit max_weekly_units. If this pull "
            "returns ALL_CEILINGS_REACHED, that is a Pass. If it returns "
            "another task without having met ceiling, verify whether "
            "max_weekly_units was actually exhausted — may not be a Fail "
            "if capacity genuinely remains."
        ),
    },
    {
        "week": 2,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(2)},
    },
    {
        "week": 4,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(5)},
    },

    # ─────────────── MONTH 3 — Interview, urgency spike ──────────────────────
    # First-round job interview — short deadline, urgency spike.
    # Layer B: urgency multiplier on job goal (7–30d bracket, U=1.5).
    {
        "week": 9,
        "event_type": "edit_goal_deadline",
        "method": "PATCH",
        "path": "/goals/{{job_confirmed.goal_id}}",
        "payload": {
            "user_id": USER_ID,
            "terminal_deadline": _week_date(11),  # ~2 weeks from week 9
        },
        "save_as": "job_urgency_update",
        "notes": (
            "First-round interview in 2 weeks. Layer B: urgency multiplier "
            "— deadline shifts into 7–30d bracket (U=1.5). Tri-Vector "
            "weights should shift sharply toward job goal. "
            "Layer A Criterion 3: does guidance communicate explicitly what "
            "this means for skill and portfolio goals this week?"
        ),
    },
    {
        "week": 9,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "HIGH",
            "consecutive_pull_count": 0,
        },
        "save_as": "pull_w9_a",
    },
    {
        "week": 9,
        "event_type": "complete_task",
        "path": "/tasks/complete",
        "payload": {
            "user_id": USER_ID,
            "task_id": "{{pull_w9_a.pulled_task.task_id}}",
            "goal_id": "{{pull_w9_a.pulled_task.goal_id}}",
            "milestone_id": "{{pull_w9_a.pulled_task.milestone_id}}",
        },
    },
    {
        "week": 9,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(9)},
    },
    {
        "week": 11,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(13)},
    },

    # ─────────────── MONTH 4 — Interview didn't convert ──────────────────────
    # Disappointment. Blessing is frustrated. She doesn't submit anything
    # new — just a pull, which reflects someone showing up but deflated.
    # Layer A Criterion 1: does guidance acknowledge the emotional context
    # of a missed opportunity, or barrel through with task allocation?
    # TODO: Tuni — decide whether the job goal stays ACTIVE or gets paused
    # here. Pausing it triggers weight recompute (Layer B). Keeping it
    # active is more realistic for someone who hasn't given up.
    # Recommendation: keep ACTIVE, reduce urgency via deadline extension
    # (simulates her accepting she needs a longer horizon).
    {
        "week": 13,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "LOW",
            "consecutive_pull_count": 0,
        },
        "save_as": "pull_w13_a",
        "notes": (
            "Post-rejection check-in. Low energy reflects disappointment. "
            "Layer A Criterion 1: does the guidance tone reflect her "
            "situation, or is it obliviously upbeat?"
        ),
    },
    {
        "week": 13,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(14)},
    },

    # ─────────────── MONTH 5 — Recalibrates, doubles down on portfolio ───────
    # Voluntarily pauses skill goal, focuses on portfolio.
    # Layer B: weight recompute on goal exit (skill goal paused).
    {
        "week": 17,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "HIGH",
            "consecutive_pull_count": 0,
        },
        "save_as": "pull_w17_a",
    },
    {
        "week": 17,
        "event_type": "complete_task",
        "path": "/tasks/complete",
        "payload": {
            "user_id": USER_ID,
            "task_id": "{{pull_w17_a.pulled_task.task_id}}",
            "goal_id": "{{pull_w17_a.pulled_task.goal_id}}",
            "milestone_id": "{{pull_w17_a.pulled_task.milestone_id}}",
        },
    },
    {
        "week": 17,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(17)},
    },
    {
        "week": 18,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "HIGH",
            "consecutive_pull_count": 0,
        },
        "save_as": "pull_w18_a",
    },
    {
        "week": 18,
        "event_type": "complete_task",
        "path": "/tasks/complete",
        "payload": {
            "user_id": USER_ID,
            "task_id": "{{pull_w18_a.pulled_task.task_id}}",
            "goal_id": "{{pull_w18_a.pulled_task.goal_id}}",
            "milestone_id": "{{pull_w18_a.pulled_task.milestone_id}}",
        },
    },
    {
        "week": 18,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(19)},
    },

    # ─────────────── MONTH 6 — Job lands, portfolio concludes ────────────────
    # TODO: Toni — pick whether job offer arrives in week 21 or 22.
    # Portfolio goal either completes (natural close) or is superseded.
    # Onboarding-to-new-role goal not scripted here — add it post-decision.
    {
        "week": 21,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "HIGH",
            "consecutive_pull_count": 0,
        },
        "save_as": "pull_w21_a",
    },
    {
        "week": 21,
        "event_type": "complete_task",
        "path": "/tasks/complete",
        "payload": {
            "user_id": USER_ID,
            "task_id": "{{pull_w21_a.pulled_task.task_id}}",
            "goal_id": "{{pull_w21_a.pulled_task.goal_id}}",
            "milestone_id": "{{pull_w21_a.pulled_task.milestone_id}}",
        },
    },
    {
        "week": 21,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(21)},
    },
    {
        "week": 23,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(23)},
    },
]