"""
evaluation/personas/margaret_sully.py

Persona 7 — Margaret Sully. 67, Portland, Oregon. Retired schoolteacher,
widowed. Warm, reflective, unhurried. Low weekly hours by choice — this is
normal for her, not a limitation to fix. Communicates slowly, sometimes
second-guesses herself.

Layer B targets:
  - Dependency unlocking         (slow but steady task completion chain)
  - DEEP lockout                 (tests that lockout holds even at low pace)
  - Floor-deficit prioritization (low hours → milestones regularly below floor)
  - Urgency multiplier           (Month 5: fair deadline 6 weeks out → U=1.2)
  - Tri-Vector normalization     (Month 2+: 2 concurrent goals)

NOTE: Margaret's low engagement frequency (2–3 pulls/week) is normal
and healthy for her. The harness should not interpret sparse steps as
stagnation unless a DEEP task specifically goes 7+ unpulled days.
The pacing here is intentional — this persona validates that the system
does not over-index on activity frequency as a proxy for user health.
"""

USER_ID = "margaret_sully"

CONTEXT: dict = {}

# Capacity: retired, low hours by choice. Morning sessions only.
# No pressure, no urgency. Declaring low max_workable_hours intentionally.
ONBOARDING_PAYLOAD = {
    "user_id": USER_ID,
    "max_workable_hours": 6.0,  # ~1hr x 3 weekday mornings + 3hrs weekend
    "weekday_blocks": [
        {
            "label": "morning after breakfast",
            "start_time": "09:00",
            "end_time": "10:30",
            "energy_level": "MEDIUM",
        }
    ],
    "weekend_blocks": [
        {
            "label": "Saturday morning",
            "start_time": "09:00",
            "end_time": "11:30",
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
    # ─────────────── MONTH 1 — Single gentle goal, no deadline ──────────────
    # Watercolor: no deadline, or very soft self-set one.
    # Layer A Criterion 1: does the system respect her unhurried framing,
    # or impose structure that would feel pressuring?
    {
        "week": 1,
        "event_type": "draft_goal",
        "path": "/goals/draft",
        "payload": {
            "user_id": USER_ID,
            "raw_goal": "Learn to paint with watercolors. I've always wanted to try.",
            "user_context": (
                "Recently retired schoolteacher, Portland. Widowed two years "
                "ago. No deadlines, no career pressure. Wants structure and "
                "purpose, not achievement targets. Low weekly hours — "
                "this is how she likes it."
            ),
        },
        "save_as": "watercolor_draft",
    },
    {
        "week": 1,
        "event_type": "structure_goal",
        "path": "/goals/structure",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{watercolor_draft}}",
            "existing_goal_summaries": [],
        },
        "save_as": "watercolor_structured",
        "notes": (
            "Layer A Criterion 1 (Personalisation): Margaret explicitly "
            "wants purpose and structure, not achievement pressure. Does "
            "the system produce gentle, exploratory milestones — or does "
            "it turn 'learn to paint' into a deliverables roadmap?"
        ),
    },
    {
        "week": 1,
        "event_type": "confirm_goal",
        "path": "/goals/confirm",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{watercolor_draft}}",
            "smart_assessment": "{{watercolor_structured}}",
            "week_start": WEEK_1_MONDAY,
        },
        "save_as": "watercolor_confirmed",
    },
    # Slow pace from the start — one pull, one complete, then rest.
    {
        "week": 2,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "MEDIUM",
            "consecutive_pull_count": 0,
        },
        "save_as": "pull_w2_a",
        "notes": (
            "Layer B: DEEP lockout check candidate. If this pull returns "
            "a DEEP task, the next pull must exclude DEEP. Given her low "
            "pace, the gap between pulls will naturally be several days — "
            "lockout must still hold across that gap."
        ),
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
        "payload": {"user_id": USER_ID, "week_start": _week_date(5)},
    },

    # ─────────────── MONTH 2 — Volunteering goal added ──────────────────────
    # Simple, emotionally significant. Weekly library volunteering.
    # Layer B: Tri-Vector normalization with 2 concurrent goals.
    {
        "week": 5,
        "event_type": "draft_goal",
        "path": "/goals/draft",
        "payload": {
            "user_id": USER_ID,
            "raw_goal": (
                "Volunteer at my local library once a week. "
                "I miss being around people and books."
            ),
            "user_context": (
                "Emotionally significant — rebuilding social rhythm after "
                "widowhood. Structurally simple. No deadline. "
                "Still has watercolor goal active."
            ),
        },
        "save_as": "library_draft",
    },
    {
        "week": 5,
        "event_type": "structure_goal",
        "path": "/goals/structure",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{library_draft}}",
            "existing_goal_summaries": "{{ACTIVE_GOAL_SUMMARIES}}",
        },
        "save_as": "library_structured",
    },
    {
        "week": 5,
        "event_type": "confirm_goal",
        "path": "/goals/confirm",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{library_draft}}",
            "smart_assessment": "{{library_structured}}",
            "week_start": _week_date(5),
        },
        "save_as": "library_confirmed",
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
        "notes": (
            "Layer B: dependency unlocking check. If pull_w2_a completed "
            "a task with dependents, they should now be AVAILABLE. "
            "Layer B: DEEP lockout — if pull_w2_a was DEEP, this pull "
            "must still exclude DEEP despite the multi-week gap."
        ),
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
        "week": 6,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(6)},
    },
    {
        "week": 8,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(9)},
    },

    # ─────────────── MONTHS 3–4 — Slow steady pace ───────────────────────────
    # Genuine low engagement. ~1 pull per week is healthy for Margaret.
    # Floor-deficit will be common given low capacity.
    # Layer B: floor-deficit prioritization — system should serve the
    # most-starved milestone, not the highest-weighted one.
    {
        "week": 9,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "MEDIUM",
            "consecutive_pull_count": 0,
        },
        "save_as": "pull_w9_a",
        "notes": (
            "Layer B: floor-deficit prioritization. With 6hrs/week and "
            "2 active goals, at least one milestone will regularly be "
            "below its min_weekly_units floor. Verify from task pull "
            "response that the most-starved milestone was served."
        ),
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
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "MEDIUM",
            "consecutive_pull_count": 0,
        },
        "save_as": "pull_w11_a",
    },
    {
        "week": 11,
        "event_type": "complete_task",
        "path": "/tasks/complete",
        "payload": {
            "user_id": USER_ID,
            "task_id": "{{pull_w11_a.pulled_task.task_id}}",
            "goal_id": "{{pull_w11_a.pulled_task.goal_id}}",
            "milestone_id": "{{pull_w11_a.pulled_task.milestone_id}}",
        },
    },
    {
        "week": 11,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(12)},
    },
    {
        "week": 13,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(17)},
    },

    # ─────────────── MONTH 5 — Fair deadline added ───────────────────────────
    # Watercolor piece for a local community fair — 6 weeks out.
    # Her first genuinely urgent goal.
    # Layer B: urgency multiplier — 6 weeks = 42 days → 30–90d bracket (U=1.2).
    # Layer A Criterion 1: does the system shift tone appropriately — adding
    # gentle urgency without becoming pressuring or suddenly task-heavy?
    {
        "week": 17,
        "event_type": "edit_goal_deadline",
        "method": "PATCH",
        "path": "/goals/{{watercolor_confirmed.goal_id}}",
        "payload": {
            "user_id": USER_ID,
            "terminal_deadline": _week_date(23),  # 6 weeks from week 17
        },
        "save_as": "watercolor_fair_deadline",
        "notes": (
            "Watercolor goal now has a real deadline — community fair entry. "
            "Layer B: urgency multiplier — 6 weeks → 30–90d bracket (U=1.2). "
            "Tri-Vector weights should shift toward watercolor. "
            "Layer A Criterion 1: Margaret's first deadline. Does the system "
            "add appropriate gentle urgency, or overcorrect into pressure?"
        ),
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
        "week": 19,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "MEDIUM",
            "consecutive_pull_count": 0,
        },
        "save_as": "pull_w19_a",
    },
    {
        "week": 19,
        "event_type": "complete_task",
        "path": "/tasks/complete",
        "payload": {
            "user_id": USER_ID,
            "task_id": "{{pull_w19_a.pulled_task.task_id}}",
            "goal_id": "{{pull_w19_a.pulled_task.goal_id}}",
            "milestone_id": "{{pull_w19_a.pulled_task.milestone_id}}",
        },
    },
    {
        "week": 19,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(20)},
    },

    # ─────────────── MONTH 6 — Fair passes, settles back ────────────────────
    # Fair deadline passes — piece submitted or not, let emerge naturally.
    # TODO: Toni — decide outcome (submitted vs not ready in time).
    # Either is valid. Submitted: watercolor goal closes → weight recompute.
    # Not submitted: goal remains, urgency drops, gentle pace resumes.
    # Recommendation: submitted (more interesting for Layer B weight recompute).
    {
        "week": 21,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "MEDIUM",
            "consecutive_pull_count": 0,
        },
        "save_as": "pull_w21_a",
        "notes": (
            "Post-fair. If watercolor goal closed at deadline: Layer B "
            "weight recompute — library milestones renormalize to 1.0. "
            "System should return to the gentle pace appropriate for Margaret."
        ),
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