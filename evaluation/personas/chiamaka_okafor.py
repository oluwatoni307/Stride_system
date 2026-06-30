"""
evaluation/personas/chiamaka_okafor.py

Persona 3 — Chiamaka Okafor. 31, Port Harcourt. New mother (baby 4 months),
part-time freelance from home. Exhausted, fragmented attention. Wants to feel
like herself again. Wary of guilt-inducing systems.

Layer B targets:
  - Stagnation flagging          (2-week gap → DEEP task unpulled 7+ days)
  - Floor-deficit prioritization (post-gap, starved milestones)
  - Weight recompute on goal exit (if freelance goal closes naturally)
  - Tri-Vector normalization     (Month 5, 3 concurrent goals)

NOTE on energy blocks: Chiamaka's availability is genuinely unpredictable
week to week. The EnergyBlock schema is a static declaration — it cannot
represent variable availability. Declared capacity here reflects a
realistic LOW baseline. Her actual irregular engagement is expressed through
the density of pull/complete steps in this script (some weeks one pull,
some weeks zero). This is an honest representation of the system's current
capacity model limitation, which should be acknowledged in the thesis
methodology.
"""

USER_ID = "chiamaka_okafor"

CONTEXT: dict = {}

# Capacity: new mother, sleep-deprived. One short window during baby's
# morning nap (not guaranteed every day). Weekend slightly more if partner
# is home. Declaring the window as a baseline; actual engagement is sparse.
ONBOARDING_PAYLOAD = {
    "user_id": USER_ID,
    "max_workable_hours": 6.0,  # ~45min x 4 weekday nap windows + 3hrs weekend
    "weekday_blocks": [
        {
            "label": "baby morning nap window",
            "start_time": "10:00",
            "end_time": "11:30",
            "energy_level": "LOW",
        }
    ],
    "weekend_blocks": [
        {
            "label": "Saturday afternoon with partner home",
            "start_time": "14:00",
            "end_time": "17:00",
            "energy_level": "MEDIUM",
        }
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
    # ─────────────── MONTH 1 — Single loose goal, low pressure ──────────────
    {
        "week": 1,
        "event_type": "draft_goal",
        "path": "/goals/draft",
        "payload": {
            "user_id": USER_ID,
            "raw_goal": (
                "Stay connected to my professional field — maybe one small "
                "freelance article or project per month. Nothing too intense."
            ),
            "user_context": (
                "New mother, baby is 4 months old. On extended leave from "
                "marketing job, doing some part-time freelance from home. "
                "Very fragmented time. Does not want guilt if she misses days. "
                "Wants to feel like herself again, not hit KPIs."
            ),
        },
        "save_as": "freelance_draft",
    },
    {
        "week": 1,
        "event_type": "structure_goal",
        "path": "/goals/structure",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{freelance_draft}}",
            "existing_goal_summaries": [],
        },
        "save_as": "freelance_structured",
        "notes": (
            "Layer A Criterion 1: does the system respect her explicit "
            "low-pressure framing, or restructure this into something that "
            "feels like a KPI? Personalisation score depends on this."
        ),
    },
    {
        "week": 1,
        "event_type": "confirm_goal",
        "path": "/goals/confirm",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{freelance_draft}}",
            "smart_assessment": "{{freelance_structured}}",
            "week_start": WEEK_1_MONDAY,
        },
        "save_as": "freelance_confirmed",
    },
    {
        "week": 2,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "LOW",
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
        "week": 2,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(2)},
    },
    {
        "week": 3,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(4)},
    },
    {
        "week": 4,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(5)},
    },

    # ─────────────── MONTH 2 — Health goal added ────────────────────────────
    {
        "week": 5,
        "event_type": "draft_goal",
        "path": "/goals/draft",
        "payload": {
            "user_id": USER_ID,
            "raw_goal": "Feel physically stronger. Nothing specific, just better than I do now.",
            "user_context": (
                "Postpartum. No deadline, no metrics. This is purely "
                "identity-driven. Does not want a fitness plan with targets."
            ),
        },
        "save_as": "health_draft",
    },
    {
        "week": 5,
        "event_type": "structure_goal",
        "path": "/goals/structure",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{health_draft}}",
            "existing_goal_summaries": "{{ACTIVE_GOAL_SUMMARIES}}",
        },
        "save_as": "health_structured",
    },
    {
        "week": 5,
        "event_type": "confirm_goal",
        "path": "/goals/confirm",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{health_draft}}",
            "smart_assessment": "{{health_structured}}",
            "week_start": _week_date(5),
        },
        "save_as": "health_confirmed",
    },
    {
        "week": 6,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "LOW",
            "consecutive_pull_count": 0,
        },
        "save_as": "pull_w6_a",
        "notes": (
            "Pull a task here. If it is DEEP, it becomes the stagnation "
            "candidate — this task needs to go unpulled for 7+ days to "
            "trigger stagnation flagging in Month 3's gap. Do NOT complete "
            "it — leave it AVAILABLE (pulled but not completed here is fine, "
            "the key is that no subsequent pull happens for 2 weeks)."
        ),
    },
    # Deliberately NOT completing the pulled task this week.
    # The gap starts here — no pulls or completions for weeks 7 and 8.
    {
        "week": 6,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(6)},
    },

    # ─────────────── MONTH 3 — 2-week disengagement (baby illness) ──────────
    # No steps in weeks 7–8. The runner simply skips those week numbers.
    # The previously pulled DEEP task (pull_w6_a) has now been AVAILABLE
    # and unpulled for 14+ days, which exceeds the 7-day stagnation window.
    # Layer B: stagnation flagging — stalled_flag should be set and the
    # system should offer force-pull-or-breakdown choice on re-engagement.
    # Layer A: does the system acknowledge the gap warmly when she returns,
    # or does it immediately pile on missed tasks?
    {
        "week": 9,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(9)},
        "notes": (
            "Re-engagement after 2-week gap. This cycle should detect "
            "stagnation on the task pulled in week 6. Layer B stagnation "
            "check applies here. Layer A: tone of re-engagement guidance "
            "is the key qualitative moment for this persona."
        ),
    },
    {
        "week": 9,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "LOW",
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
        "week": 10,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(11)},
    },

    # ─────────────── MONTH 4 — Recurring client, real weekly deadlines ───────
    # Freelance goal sharpens: she's landed a recurring small client.
    # For the first time, her freelance work has actual weekly deadlines.
    # Simulate via goal edit (tightening terminal_deadline) rather than
    # submitting a new goal — the existing freelance goal evolves.
    {
        "week": 13,
        "event_type": "edit_goal_deadline",
        "method": "PATCH",
        "path": "/goals/{{freelance_confirmed.goal_id}}",
        "payload": {
            "user_id": USER_ID,
            "terminal_deadline": _week_date(21),  # ~8 weeks from month 4 start
        },
        "save_as": "freelance_deadline_update",
        "notes": (
            "Freelance goal now has a real deadline for the first time. "
            "Layer B: Tri-Vector recompute — urgency bracket shifts, "
            "weights across freelance + health goals should renormalize. "
            "Layer A: does guidance acknowledge the character change in "
            "this goal (from open-ended to deadline-bound)?"
        ),
    },
    {
        "week": 13,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "MEDIUM",
            "consecutive_pull_count": 0,
        },
        "save_as": "pull_w13_a",
    },
    {
        "week": 13,
        "event_type": "complete_task",
        "path": "/tasks/complete",
        "payload": {
            "user_id": USER_ID,
            "task_id": "{{pull_w13_a.pulled_task.task_id}}",
            "goal_id": "{{pull_w13_a.pulled_task.goal_id}}",
            "milestone_id": "{{pull_w13_a.pulled_task.milestone_id}}",
        },
    },
    {
        "week": 13,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(13)},
    },
    {
        "week": 16,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(17)},
    },

    # ─────────────── MONTH 5–6 — Return-to-work goal, 3 concurrent ──────────
    # Third goal: return to work part-time by Month 7. Job search/networking.
    # Now 3 goals active (freelance, health, career) against 6hrs/week.
    # Layer B: Tri-Vector normalization across 3 goals' milestones.
    # Layer A Criterion 3: does guidance reason about the 3-goal competition
    # for her handful of weekly hours, or treat each goal in isolation?
    {
        "week": 17,
        "event_type": "draft_goal",
        "path": "/goals/draft",
        "payload": {
            "user_id": USER_ID,
            "raw_goal": (
                "I want to start working part-time again by next month — "
                "need to do some networking and maybe update my portfolio."
            ),
            "user_context": (
                "Wants to return to marketing work part-time by Month 7. "
                "Already has freelance (now with real deadlines) and a "
                "health goal active. Same limited capacity throughout."
            ),
        },
        "save_as": "career_draft",
    },
    {
        "week": 17,
        "event_type": "structure_goal",
        "path": "/goals/structure",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{career_draft}}",
            "existing_goal_summaries": "{{ACTIVE_GOAL_SUMMARIES}}",
        },
        "save_as": "career_structured",
        "notes": (
            "Layer A Criterion 3 key moment: 3 goals now compete for 6hrs/week. "
            "Does structure_goal reason about this explicitly, or produce a "
            "plan that ignores the existing load?"
        ),
    },
    {
        "week": 17,
        "event_type": "confirm_goal",
        "path": "/goals/confirm",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{career_draft}}",
            "smart_assessment": "{{career_structured}}",
            "week_start": _week_date(17),
        },
        "save_as": "career_confirmed",
    },
    {
        "week": 17,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "MEDIUM",
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
        "week": 20,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(23)},
    },
]