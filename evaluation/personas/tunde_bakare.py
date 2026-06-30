"""
evaluation/personas/tunde_bakare.py

Persona 2 — Tunde Bakare. 41, Abuja. Mid-level civil servant wanting to
transition to consulting. Time-starved (long commute + 3 kids). Skeptical,
terse, pushes back when suggestions feel generic or disconnected from his
real constraints.

Layer B targets:
  - Capacity conflict trigger    (Month 3: school exam + consulting compete)
  - Weight recompute on exit     (Month 4: school goal closes)
  - Urgency multiplier           (Month 3: school exam 5 weeks out → 30–90d bracket)
  - Floor-deficit prioritization (low hours throughout; one goal will starve)
  - Tri-Vector normalization     (any point with 2+ active milestones)
"""

USER_ID = "tunde_bakare"

CONTEXT: dict = {}

# Capacity: long commute eats mornings. Early evenings taken by family.
# Late evenings (after kids sleep) are his only real window on weekdays.
# Weekends: Saturday morning before family obligations. Sunday almost nothing.
# Deliberately low max_workable_hours — this is what makes the capacity
# conflict meaningful when the school goal lands in Month 3.
ONBOARDING_PAYLOAD = {
    "user_id": USER_ID,
    "max_workable_hours": 8.0,  # ~1.5hrs x 4 weekday late evenings + 2hrs Saturday
    "weekday_blocks": [
        {
            "label": "late evening after family",
            "start_time": "21:30",
            "end_time": "23:00",
            "energy_level": "LOW",
        }
    ],
    "weekend_blocks": [
        {
            "label": "Saturday morning",
            "start_time": "07:00",
            "end_time": "09:00",
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
    # ─────────────── MONTH 1 — Vague goal, natural pushback ─────────────────
    # Tunde submits deliberately vague. The DraftingAgent should probe
    # for specificity. His user_context signals the constraint-awareness
    # the system needs to engage with — if it doesn't, Layer A Criterion 1
    # (Personalisation) scores low.
    {
        "week": 1,
        "event_type": "draft_goal",
        "path": "/goals/draft",
        "payload": {
            "user_id": USER_ID,
            "raw_goal": "Build a side income so I'm not depending only on my salary.",
            "user_context": (
                "Civil servant, 14 years same ministry. Long daily commute, "
                "married with three children. Only real window is late evenings "
                "after kids are asleep. Has tried productivity apps before and "
                "dropped them all. Does not want generic advice."
            ),
        },
        "save_as": "consulting_draft",
    },
    {
        "week": 1,
        "event_type": "structure_goal",
        "path": "/goals/structure",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{consulting_draft}}",
            "existing_goal_summaries": [],
        },
        "save_as": "consulting_structured",
    },
    {
        "week": 1,
        "event_type": "confirm_goal",
        "path": "/goals/confirm",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{consulting_draft}}",
            "smart_assessment": "{{consulting_structured}}",
            "week_start": WEEK_1_MONDAY,
        },
        "save_as": "consulting_confirmed",
    },
    {
        "week": 1,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "LOW",
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

    # ─────────────── MONTH 2 — Goal structured, low but steady progress ─────
    # Consulting goal is now a ~6-week portfolio piece. His actual hours
    # remain low. Pull once per week — reflects his real late-evening pattern.
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
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "MEDIUM",
            "consecutive_pull_count": 0,
        },
        "save_as": "pull_w3_a",
    },
    {
        "week": 3,
        "event_type": "complete_task",
        "path": "/tasks/complete",
        "payload": {
            "user_id": USER_ID,
            "task_id": "{{pull_w3_a.pulled_task.task_id}}",
            "goal_id": "{{pull_w3_a.pulled_task.goal_id}}",
            "milestone_id": "{{pull_w3_a.pulled_task.milestone_id}}",
        },
    },
    {
        "week": 3,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(3)},
    },
    {
        "week": 4,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(5)},
    },

    # ─────────────── MONTH 3 — School exam goal, capacity conflict ───────────
    # Entrance exam is 5 weeks out (~35 days → urgency bracket 30–90d, U=1.2).
    # With max_workable_hours=8.0, adding a second goal with its own
    # min_weekly_units should push new_total_min_weekly_units > 8.0 × 3 = 24.
    # Layer B: capacity conflict trigger + urgency multiplier bracket check.
    # Layer A: does guidance communicate the conflict to Tunde honestly, or
    # silently overcommit him? This is Criterion 3 (Cross-Goal Coherence).
    {
        "week": 5,
        "event_type": "draft_goal",
        "path": "/goals/draft",
        "payload": {
            "user_id": USER_ID,
            "raw_goal": (
                "Help my eldest son prepare for his secondary school entrance "
                "exam. The exam is in 5 weeks. He needs structured daily study "
                "sessions and I need to be the one supervising them."
            ),
            "user_context": (
                "High-stakes, emotionally weighted. This takes priority over "
                "the consulting goal this month. Already have an active "
                "consulting goal with very limited weekly hours."
            ),
        },
        "save_as": "school_draft",
    },
    {
        "week": 5,
        "event_type": "structure_goal",
        "path": "/goals/structure",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{school_draft}}",
            "existing_goal_summaries": "{{ACTIVE_GOAL_SUMMARIES}}",
        },
        "save_as": "school_structured",
        "notes": (
            "Layer A Criterion 2: does the system surface a viability concern "
            "about adding a 5-week urgent goal on top of an already-capacity-"
            "constrained consulting goal? Tunde has 8hrs/week total."
        ),
    },
    {
        "week": 5,
        "event_type": "confirm_goal",
        "path": "/goals/confirm",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{school_draft}}",
            "smart_assessment": "{{school_structured}}",
            "week_start": _week_date(5),
        },
        "save_as": "school_confirmed",
        "notes": (
            "Layer B: capacity conflict check. new_total_min_weekly_units "
            "should exceed max_workable_hours × 3 = 24 here. If the system "
            "does NOT raise a conflict, that's a Layer B Fail."
        ),
    },
    # Both goals now active. Pull reflects he's prioritizing school prep.
    {
        "week": 5,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "MEDIUM",
            "consecutive_pull_count": 0,
        },
        "save_as": "pull_w5_a",
    },
    {
        "week": 5,
        "event_type": "complete_task",
        "path": "/tasks/complete",
        "payload": {
            "user_id": USER_ID,
            "task_id": "{{pull_w5_a.pulled_task.task_id}}",
            "goal_id": "{{pull_w5_a.pulled_task.goal_id}}",
            "milestone_id": "{{pull_w5_a.pulled_task.milestone_id}}",
        },
    },
    {
        "week": 5,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(5)},
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
        "week": 7,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(8)},
    },

    # ─────────────── MONTH 4 — School goal closes, rebalance ────────────────
    # Exam has passed. Mark the school goal's final milestone complete,
    # then run the weekly cycle. Layer B: weight recompute on goal exit —
    # consulting goal's milestones should renormalize to sum=1.0 alone.
    # Layer A: does guidance acknowledge the closed goal and reorient
    # Tunde back toward consulting without being patronizing?
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
        "notes": (
            "School goal final task completion. The cycle that follows should "
            "trigger weight recompute — school milestones exit, consulting "
            "milestones renormalize. Layer B: weight recompute on goal exit."
        ),
    },
    {
        "week": 9,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(9)},
    },
    {
        "week": 10,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "LOW",
            "consecutive_pull_count": 0,
        },
        "save_as": "pull_w10_a",
    },
    {
        "week": 10,
        "event_type": "complete_task",
        "path": "/tasks/complete",
        "payload": {
            "user_id": USER_ID,
            "task_id": "{{pull_w10_a.pulled_task.task_id}}",
            "goal_id": "{{pull_w10_a.pulled_task.goal_id}}",
            "milestone_id": "{{pull_w10_a.pulled_task.milestone_id}}",
        },
    },
    {
        "week": 10,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(10)},
    },
    {
        "week": 12,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(13)},
    },

    # ─────────────── MONTH 5–6 — Small gig lands, delivery goal added ────────
    # New goal: deliver the first paid consulting gig. Short, hard deadline
    # (~3 weeks), high impact. Layered on top of ongoing skills-building goal.
    # Layer B: urgency multiplier (3 weeks → 7–30d bracket, U=1.5) +
    # Tri-Vector renormalization across both goals.
    # Layer A: Cross-Goal Coherence — does the system reason about the
    # tension between "keep building skills" and "deliver the live gig"?
    {
        "week": 13,
        "event_type": "draft_goal",
        "path": "/goals/draft",
        "payload": {
            "user_id": USER_ID,
            "raw_goal": (
                "I just landed a small paid consulting project. I need to "
                "deliver it well — the deadline is in 3 weeks."
            ),
            "user_context": (
                "First paid gig from the consulting transition goal. Hard "
                "deadline, high stakes for credibility. Still has the "
                "ongoing consulting skills-building goal active."
            ),
        },
        "save_as": "gig_draft",
    },
    {
        "week": 13,
        "event_type": "structure_goal",
        "path": "/goals/structure",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{gig_draft}}",
            "existing_goal_summaries": "{{ACTIVE_GOAL_SUMMARIES}}",
        },
        "save_as": "gig_structured",
    },
    {
        "week": 13,
        "event_type": "confirm_goal",
        "path": "/goals/confirm",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{gig_draft}}",
            "smart_assessment": "{{gig_structured}}",
            "week_start": _week_date(13),
        },
        "save_as": "gig_confirmed",
        "notes": (
            "Layer B: urgency multiplier check — gig deadline is ~3 weeks "
            "out, should land in the 7–30d bracket (U=1.5). Tri-Vector "
            "weights should shift visibly toward the gig goal. "
            "Layer A: does guidance tell Tunde concretely what this means "
            "for his consulting skills work this month, or just acknowledge "
            "the new goal abstractly?"
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
        "week": 14,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "MEDIUM",
            "consecutive_pull_count": 0,
        },
        "save_as": "pull_w14_a",
    },
    {
        "week": 14,
        "event_type": "complete_task",
        "path": "/tasks/complete",
        "payload": {
            "user_id": USER_ID,
            "task_id": "{{pull_w14_a.pulled_task.task_id}}",
            "goal_id": "{{pull_w14_a.pulled_task.goal_id}}",
            "milestone_id": "{{pull_w14_a.pulled_task.milestone_id}}",
        },
    },
    {
        "week": 14,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(14)},
    },
    {
        "week": 15,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "LOW",
            "consecutive_pull_count": 0,
        },
        "save_as": "pull_w15_a",
    },
    {
        "week": 15,
        "event_type": "complete_task",
        "path": "/tasks/complete",
        "payload": {
            "user_id": USER_ID,
            "task_id": "{{pull_w15_a.pulled_task.task_id}}",
            "goal_id": "{{pull_w15_a.pulled_task.goal_id}}",
            "milestone_id": "{{pull_w15_a.pulled_task.milestone_id}}",
        },
    },
    {
        "week": 15,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(15)},
    },
    {
        "week": 17,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(23)},
    },
]