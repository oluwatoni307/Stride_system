"""
evaluation/personas/daniel_whitfield.py

Persona 6 — Daniel Whitfield. 34, Manchester. Senior PM, SaaS company.
Calm, structured, already disciplined. Evaluates the system like a vendor
tool. Professionally skeptical, not hostile.

Layer B targets:
  - DEEP lockout                 (Month 1–2: structured goals, clean task graph)
  - Anti-clumping                (Month 1–2: high output, consecutive pulls)
  - Dependency unlocking         (clean task completion chains)
  - Weight recompute on exit     (Month 3: marathon goal closes)
  - Urgency multiplier           (Month 5: certification exam deadline)
  - Tri-Vector normalization     (throughout — well-formed goals, stable system)
"""

USER_ID = "daniel_whitfield"

CONTEXT: dict = {}

# Capacity: moderate-to-high. Regular schedule. Early mornings before
# work + weekend blocks. Reliable, not maxed out.
ONBOARDING_PAYLOAD = {
    "user_id": USER_ID,
    "max_workable_hours": 16.0,  # ~1.5hrs x 5 weekday mornings + 6hrs weekend
    "weekday_blocks": [
        {
            "label": "early morning before work",
            "start_time": "06:30",
            "end_time": "08:00",
            "energy_level": "HIGH",
        }
    ],
    "weekend_blocks": [
        {
            "label": "Saturday long session",
            "start_time": "08:00",
            "end_time": "11:00",
            "energy_level": "HIGH",
        },
        {
            "label": "Sunday lighter session",
            "start_time": "14:00",
            "end_time": "17:00",
            "energy_level": "MEDIUM",
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
    # ─────────────── MONTH 1–2 — Two well-formed concurrent goals ────────────
    # Marathon: 10-week training block, fixed race date.
    {
        "week": 1,
        "event_type": "draft_goal",
        "path": "/goals/draft",
        "payload": {
            "user_id": USER_ID,
            "raw_goal": (
                "Train for a half-marathon. Race is in 10 weeks. "
                "I have a training plan — I need the system to help me "
                "track execution and not fall behind."
            ),
            "user_context": (
                "Senior PM, structured and disciplined. Regular early morning "
                "schedule. Wants the system to help reason across goals, not "
                "just list tasks."
            ),
        },
        "save_as": "marathon_draft",
    },
    {
        "week": 1,
        "event_type": "structure_goal",
        "path": "/goals/structure",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{marathon_draft}}",
            "existing_goal_summaries": [],
        },
        "save_as": "marathon_structured",
    },
    {
        "week": 1,
        "event_type": "confirm_goal",
        "path": "/goals/confirm",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{marathon_draft}}",
            "smart_assessment": "{{marathon_structured}}",
            "week_start": WEEK_1_MONDAY,
        },
        "save_as": "marathon_confirmed",
    },
    # Certification: self-paced, ~4-month horizon.
    {
        "week": 1,
        "event_type": "draft_goal",
        "path": "/goals/draft",
        "payload": {
            "user_id": USER_ID,
            "raw_goal": (
                "Complete my AWS Solutions Architect certification. "
                "Self-paced, I'm giving myself 4 months."
            ),
            "user_context": (
                "Already submitted a half-marathon goal this session. "
                "Wants both tracked concurrently."
            ),
        },
        "save_as": "cert_draft",
    },
    {
        "week": 1,
        "event_type": "structure_goal",
        "path": "/goals/structure",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{cert_draft}}",
            "existing_goal_summaries": "{{ACTIVE_GOAL_SUMMARIES}}",
        },
        "save_as": "cert_structured",
        "notes": (
            "Layer A Criterion 3: two well-formed concurrent goals from day 1. "
            "Does structure_goal reason about how they share capacity, or "
            "produce two independent milestone plans with no cross-reference?"
        ),
    },
    {
        "week": 1,
        "event_type": "confirm_goal",
        "path": "/goals/confirm",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{cert_draft}}",
            "smart_assessment": "{{cert_structured}}",
            "week_start": WEEK_1_MONDAY,
        },
        "save_as": "cert_confirmed",
    },
    # Daniel pulls consistently. Test DEEP lockout and anti-clumping here.
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
    # Immediate second pull — if pull_w1_a was DEEP, pull_w1_b must
    # exclude DEEP tasks. Layer B: DEEP lockout check.
    {
        "week": 1,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "HIGH",
            "consecutive_pull_count": 1,
        },
        "save_as": "pull_w1_b",
        "notes": (
            "Layer B: DEEP lockout. If pull_w1_a was DEEP, this pull must "
            "not return another DEEP task. Verify task_type on pull_w1_b "
            "from events.jsonl."
        ),
    },
    {
        "week": 1,
        "event_type": "complete_task",
        "path": "/tasks/complete",
        "payload": {
            "user_id": USER_ID,
            "task_id": "{{pull_w1_b.pulled_task.task_id}}",
            "goal_id": "{{pull_w1_b.pulled_task.goal_id}}",
            "milestone_id": "{{pull_w1_b.pulled_task.milestone_id}}",
        },
    },
    # Third pull — anti-clumping check. If pull_w1_a and pull_w1_b were
    # from the same MODERATE/MECHANICAL milestone, this must redirect.
    {
        "week": 1,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "MEDIUM",
            "consecutive_pull_count": 2,
        },
        "save_as": "pull_w1_c",
        "notes": (
            "Layer B: anti-clumping. If pull_w1_a and pull_w1_b were from "
            "the same MODERATE/MECHANICAL milestone, this pull must serve "
            "a different milestone. Verify milestone_id differs."
        ),
    },
    {
        "week": 1,
        "event_type": "complete_task",
        "path": "/tasks/complete",
        "payload": {
            "user_id": USER_ID,
            "task_id": "{{pull_w1_c.pulled_task.task_id}}",
            "goal_id": "{{pull_w1_c.pulled_task.goal_id}}",
            "milestone_id": "{{pull_w1_c.pulled_task.milestone_id}}",
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
        "notes": (
            "Layer B: dependency unlocking. If pull_w1_a/b/c completed "
            "tasks that were dependencies for others, those dependents "
            "should now be AVAILABLE. Verify from events.jsonl that "
            "newly unlocked tasks appear in eligible pool."
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
        "week": 4,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(5)},
    },
    {
        "week": 6,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "HIGH",
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
        "payload": {"user_id": USER_ID, "week_start": _week_date(7)},
    },
    {
        "week": 8,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(9)},
    },

    # ─────────────── MONTH 3 — Marathon completes, work initiative added ─────
    # Marathon race happens, goal closes naturally.
    # Layer B: weight recompute on goal exit — certification milestones
    # should renormalize to sum=1.0 alone.
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
        "notes": (
            "Marathon goal final task. Layer B: weight recompute on exit — "
            "marathon milestones close, cert milestones renormalize."
        ),
    },
    {
        "week": 9,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(9)},
    },
    # Work initiative goal: vague, political, narrative-shaped.
    # "I want to be seen as ready for the next level at work."
    # Layer A Criterion 2: can the system structure something this
    # intangible into actionable milestones without losing the intent?
    {
        "week": 9,
        "event_type": "draft_goal",
        "path": "/goals/draft",
        "payload": {
            "user_id": USER_ID,
            "raw_goal": (
                "I want to be seen as ready for the next level at work — "
                "leading a cross-team initiative that has real visibility."
            ),
            "user_context": (
                "Senior PM, wants to demonstrate readiness for principal "
                "or director level. No fixed deadline. Still has AWS "
                "certification active."
            ),
        },
        "save_as": "initiative_draft",
    },
    {
        "week": 9,
        "event_type": "structure_goal",
        "path": "/goals/structure",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{initiative_draft}}",
            "existing_goal_summaries": "{{ACTIVE_GOAL_SUMMARIES}}",
        },
        "save_as": "initiative_structured",
        "notes": (
            "Layer A Criterion 2 (Goal Viability): structuring a political/"
            "narrative goal into milestones is genuinely hard. Does the "
            "system produce something Daniel would find useful and "
            "non-generic, or retreat to platitudes?"
        ),
    },
    {
        "week": 9,
        "event_type": "confirm_goal",
        "path": "/goals/confirm",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{initiative_draft}}",
            "smart_assessment": "{{initiative_structured}}",
            "week_start": _week_date(9),
        },
        "save_as": "initiative_confirmed",
    },
    {
        "week": 12,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(13)},
    },

    # ─────────────── MONTH 4 — Goal tension, demanding sprint ────────────────
    # Work initiative conflicts with certification study during a demanding
    # work sprint. Both are genuinely active, neither should be dropped.
    # Layer A Criterion 3: does the system identify the specific tradeoff
    # and communicate it usefully, or just acknowledge both exist?
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
        "notes": (
            "Key tension moment. Work sprint reduces available energy "
            "from HIGH to MEDIUM. Does the system allocate correctly "
            "given the reduced energy level and two competing goals? "
            "Layer A Criterion 3 evidence point."
        ),
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

    # ─────────────── MONTH 5 — Certification exam deadline ───────────────────
    # Cert exam is approaching — urgency spike. Short deadline.
    # Layer B: urgency multiplier (7–30d bracket, U=1.5).
    {
        "week": 17,
        "event_type": "edit_goal_deadline",
        "method": "PATCH",
        "path": "/goals/{{cert_confirmed.goal_id}}",
        "payload": {
            "user_id": USER_ID,
            "terminal_deadline": _week_date(19),  # exam in ~2 weeks
        },
        "save_as": "cert_urgency_update",
        "notes": (
            "Cert exam booked — 2 weeks out. Layer B: urgency multiplier "
            "— 7–30d bracket (U=1.5). Weights should shift toward cert. "
            "Layer A: does guidance communicate the tradeoff with the "
            "initiative goal clearly? 'Cert is now priority' should be "
            "stated, not implied."
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
        "week": 17,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(17)},
    },
    {
        "week": 19,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(21)},
    },

    # ─────────────── MONTH 6 — Certification completes ───────────────────────
    # Cert done, initiative continues as sole active goal.
    # Layer B: weight recompute — cert exits, initiative milestones
    # renormalize to 1.0.
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
        "notes": (
            "Post-cert pull. Layer B: weight recompute — cert milestones "
            "should now be closed, initiative milestones renormalize. "
            "Verify from milestone_utilization in the preceding cycle response."
        ),
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