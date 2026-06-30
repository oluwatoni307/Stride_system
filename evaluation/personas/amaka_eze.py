"""
evaluation/personas/amaka_eze.py

Persona 1 — Amaka Eze. See protocol doc for full character description.
Methodical, anxious about falling behind, over-plans/under-executes,
skeptical but curious. Low-to-moderate weekly capacity (full-time job +
part-time MSc), evenings and weekends only.

CONTEXT dict is mutated at runtime by runner.py to carry forward response
data (e.g. confirmed_draft) between steps that need it.
"""

USER_ID = "amaka_eze"

CONTEXT: dict = {}

# Capacity: works full-time, studies part-time. Evenings + weekends only.
# Weekdays: ~2hrs evening. Weekends: ~5hrs spread across the day.
ONBOARDING_PAYLOAD = {
    "user_id": USER_ID,
    "max_workable_hours": 14.0,  # 5 weekday evenings x2 + 2 weekend days x ~2
    "weekday_blocks": [
        {
            "label": "evening after work",
            "start_time": "19:00",
            "end_time": "21:00",
            "energy_level": "MEDIUM",
        }
    ],
    "weekend_blocks": [
        {
            "label": "morning focus block",
            "start_time": "08:00",
            "end_time": "11:00",
            "energy_level": "HIGH",
        },
        {
            "label": "afternoon catch-up",
            "start_time": "14:00",
            "end_time": "16:00",
            "energy_level": "MEDIUM",
        },
    ],
}

# Week-start dates are intentionally left as relative week numbers in
# "week" and resolved by the runner / a date helper before the API call,
# OR — simpler for now — supply explicit ISO dates below once a real
# start date is picked. Using explicit dates here, anchored to an
# arbitrary Monday, so this is runnable as-is without extra resolution
# logic in the runner.

def _current_week_monday() -> str:
    """Monday of the actual current week, computed at script-run time —
    not hardcoded. The onboarding SlotGrid is generated against whatever
    'today' really is when /onboarding/profile runs, so Week 1 of the
    script MUST be anchored to that same real week, not an arbitrary
    past or future date, or confirm_goal's SlotGrid lookup will miss."""
    from datetime import date, timedelta
    today = date.today()
    return (today - timedelta(days=today.weekday())).isoformat()


WEEK_1_MONDAY = _current_week_monday()


def _week_date(n: int) -> str:
    """Return ISO date string for the Monday of week n (1-indexed)."""
    from datetime import date, timedelta
    anchor = date.fromisoformat(WEEK_1_MONDAY)
    return (anchor + timedelta(weeks=n - 1)).isoformat()


SCRIPT = [
    # ───────────────────────── MONTH 1 — Thesis goal, high urgency ──────────
    {
        "week": 1,
        "event_type": "draft_goal",
        "path": "/goals/draft",
        "payload": {
            "user_id": USER_ID,
            "raw_goal": "Finish my MSc thesis proposal — defense is in 10 weeks.",
            "user_context": (
                "Final-year part-time MSc Data Science student, also working "
                "full-time as a junior backend developer. Hard deadline, "
                "first time using this kind of tool, somewhat skeptical."
            ),
        },
        "save_as": "thesis_draft",
    },
    {
        "week": 1,
        "event_type": "structure_goal",
        "path": "/goals/structure",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{thesis_draft}}",  # resolved at runtime, see note below
            "existing_goal_summaries": [],
        },
        "save_as": "thesis_structured",
    },
    {
        "week": 1,
        "event_type": "confirm_goal",
        "path": "/goals/confirm",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{thesis_draft}}",
            "smart_assessment": "{{thesis_structured}}",
            "week_start": WEEK_1_MONDAY,
        },
        "save_as": "thesis_confirmed",
    },
    # Weeks 1-2: pull and complete a few tasks, evenings + weekend pattern
    {
        "week": 1,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "MEDIUM",
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
    {
        "week": 4,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(5)},
    },

    # ───────────────────────── MONTH 2 — Adds interview-prep goal ───────────
    {
        "week": 5,
        "event_type": "draft_goal",
        "path": "/goals/draft",
        "payload": {
            "user_id": USER_ID,
            "raw_goal": (
                "I want to prepare for a technical interview at a company "
                "I'm targeting. No fixed deadline yet, but I want it tracked "
                "alongside my thesis work."
            ),
            "user_context": (
                "Already has an active thesis-proposal goal in progress. "
                "Wants this as a second, lower-urgency concurrent goal."
            ),
        },
        "save_as": "interview_draft",
    },
    {
        "week": 5,
        "event_type": "structure_goal",
        "path": "/goals/structure",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{interview_draft}}",
            "existing_goal_summaries": "{{ACTIVE_GOAL_SUMMARIES}}",
        },
        "save_as": "interview_structured",
    },
    {
        "week": 5,
        "event_type": "confirm_goal",
        "path": "/goals/confirm",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{interview_draft}}",
            "smart_assessment": "{{interview_structured}}",
            "week_start": _week_date(5),
        },
        "save_as": "interview_confirmed",
    },
    {
        "week": 6,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "MEDIUM",
            "consecutive_pull_count": 0,
        },
        "save_as": "pull_w6_a",
    },
    {
        "week": 6,
        "event_type": "complete_task",
        "path": "/tasks/complete",
        "payload": {
            "user_id": USER_ID,
            "task_id": "{{pull_w6_a.pulled_task.task_id}}",
            "goal_id": "{{pull_w6_a.pulled_task.goal_id}}",
            "milestone_id": "{{pull_w6_a.pulled_task.milestone_id}}",
        },
    },
    {
        "week": 8,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(9)},
    },

    # ───────────────────────── MONTH 3 — both goals continue ────────────────
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
        "week": 12,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(13)},
    },

    # ───────────────────────── MONTH 4 — thesis concludes, gym goal added ──
    {
        "week": 13,
        "event_type": "draft_goal",
        "path": "/goals/draft",
        "payload": {
            "user_id": USER_ID,
            "raw_goal": "Rebuild a regular gym routine — I've been sedentary for months.",
            "user_context": (
                "Low impact, no deadline, identity-driven rather than "
                "outcome-driven. Already has interview-prep goal active; "
                "thesis goal is at or near its natural conclusion."
            ),
        },
        "save_as": "gym_draft",
    },
    {
        "week": 13,
        "event_type": "structure_goal",
        "path": "/goals/structure",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{gym_draft}}",
            "existing_goal_summaries": "{{ACTIVE_GOAL_SUMMARIES}}",
        },
        "save_as": "gym_structured",
    },
    {
        "week": 13,
        "event_type": "confirm_goal",
        "path": "/goals/confirm",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{gym_draft}}",
            "smart_assessment": "{{gym_structured}}",
            "week_start": _week_date(13),
        },
        "save_as": "gym_confirmed",
    },
    {
        "week": 16,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(17)},
    },

    # ───────────────────────── MONTH 5 — interview callback, urgency spike ─
    # Week 17 — interview callback, urgency spike. Restored now that
    # PATCH /goals/{goal_id} exists (Brief 032). Tightens the interview-prep
    # goal's terminal_deadline to 2 weeks out, which should trigger the
    # cross-goal Tri-Vector recompute (Brief 030/032 addendum) and push
    # the interview goal into a higher urgency bracket.
    {
        "week": 17,
        "event_type": "edit_goal_deadline",
        "method": "PATCH",
        "path": "/goals/{{interview_confirmed.goal_id}}",
        "payload": {
            "user_id": USER_ID,
            "terminal_deadline": _week_date(19),  # ~2 weeks from week 17
        },
        "save_as": "interview_urgency_update",
        "notes": (
            "Simulates: 'I got a callback! Interview is in 2 weeks now, "
            "this needs to be the priority.' Real endpoint, real deadline "
            "tightening — not a draft revision. Layer B check applies here: "
            "confirm tri_vector_weight recomputed correctly and still sums "
            "to 1.0 across all of Amaka's active milestones (interview + "
            "gym), and confirm gym goal's allocation visibly shrinks as a "
            "result — this is the 'does the system communicate "
            "deprioritization honestly' moment the protocol doc calls out."
        ),
    },
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
        "week": 18,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(19)},
    },

    # ───────────────────────── MONTH 6 — post-interview ─────────────────────
    {
        "week": 19,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "MEDIUM",
            "consecutive_pull_count": 0,
        },
        "save_as": "pull_w19_a",
        "notes": (
            "Post-interview check-in. Outcome (job offer vs continued "
            "search) is not pre-scripted — protocol doc allows this to "
            "'emerge naturally.' Since there's no persona-LLM, decide "
            "outcome here at script-build time rather than at runtime: "
            "TODO Toni — pick an outcome before running, so this isn't "
            "ambiguous."
        ),
    },
    {
        "week": 22,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(23)},
    },
]