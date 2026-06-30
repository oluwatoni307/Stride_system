"""
evaluation/personas/ibrahim_suleiman.py

Persona 4 — Ibrahim Suleiman. 38, Kano. Wholesale textile trader.
No fixed hours — income and schedule highly variable (market days, travel).
Sharp, impatient, transactional. Low trust by default. First productivity app.

Layer B targets:
  - Urgency multiplier           (Month 3: trade show 3 weeks out → U=1.5)
  - Stagnation flagging          (zero-activity weeks in irregular pattern)
  - Weight recompute on goal exit (Month 4: trade show goal closes)
  - Tri-Vector normalization     (any point with 2+ active milestones)

NOTE on energy blocks: Ibrahim's schedule is genuinely irregular — market
days vary, travel is unpredictable. The EnergyBlock schema requires static
declarations. Approach: declare a sparse but real baseline (3 weekday
mornings, reflecting non-market-day mornings available for planning).
His irregular engagement pattern is expressed through script step density —
some weeks multiple pulls, some weeks zero. This is documented here as a
known model limitation, not a workaround.
"""

USER_ID = "ibrahim_suleiman"

CONTEXT: dict = {}

# Capacity: non-market-day mornings only. Market days and travel weeks
# are genuinely zero. Declared baseline is conservative.
# AMBIGUOUS CASE (flagged per handover instruction): protocol describes
# "some weeks heavy activity, others near-zero." Cannot represent per-week
# variance in EnergyBlocks. Declaring 3 weekday mornings as the available
# window; weeks with heavy market activity are represented by zero pulls
# in this script, not by a reduced block declaration.
ONBOARDING_PAYLOAD = {
    "user_id": USER_ID,
    "max_workable_hours": 9.0,  # 3hrs x 3 non-market weekday mornings
    "weekday_blocks": [
        {
            "label": "morning before market",
            "start_time": "07:00",
            "end_time": "10:00",
            "energy_level": "MEDIUM",
        }
    ],
    "weekend_blocks": [
        {
            "label": "Friday evening (post-Jumu'ah)",
            "start_time": "16:00",
            "end_time": "18:00",
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
    # ─────────────── MONTH 1 — Large ambiguous goal, distant deadline ────────
    # Ibrahim submits big, vague, long-horizon. DraftingAgent must probe
    # without feeling like it's wasting his time — Layer A Criterion 1.
    {
        "week": 1,
        "event_type": "draft_goal",
        "path": "/goals/draft",
        "payload": {
            "user_id": USER_ID,
            "raw_goal": "Expand my business into a second product line.",
            "user_context": (
                "Runs wholesale textile trading, Kano. No fixed schedule — "
                "market days and travel vary week to week. High impact goal, "
                "about 5 months out. First time using an app like this. "
                "Does not want long conversations, wants useful output fast."
            ),
        },
        "save_as": "expansion_draft",
    },
    {
        "week": 1,
        "event_type": "structure_goal",
        "path": "/goals/structure",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{expansion_draft}}",
            "existing_goal_summaries": [],
        },
        "save_as": "expansion_structured",
        "notes": (
            "Layer A Criterion 2 (Goal Viability): a 5-month business "
            "expansion is high-scope. Does the system produce milestones "
            "that are actually achievable given irregular weekly hours, "
            "or generic textbook steps disconnected from Ibrahim's context?"
        ),
    },
    {
        "week": 1,
        "event_type": "confirm_goal",
        "path": "/goals/confirm",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{expansion_draft}}",
            "smart_assessment": "{{expansion_structured}}",
            "week_start": WEEK_1_MONDAY,
        },
        "save_as": "expansion_confirmed",
    },
    # Week 1: active market week — one quick pull, no completion.
    # Simulates Ibrahim checking in but not having time to finish anything.
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
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(1)},
    },

    # ─────────────── MONTH 2 — Irregular engagement ─────────────────────────
    # Week 2: travel week — zero activity, advance only.
    {
        "week": 2,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(2)},
        "notes": (
            "Travel week. No pulls. The task pulled in week 1 is now "
            "AVAILABLE and unpulled for 7+ days — stagnation window opens. "
            "Layer B: stagnation flagging check begins here."
        ),
    },
    # Week 3: back from travel, several pulls in quick succession (heavy day).
    {
        "week": 3,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "HIGH",
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
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "HIGH",
            "consecutive_pull_count": 1,
        },
        "save_as": "pull_w3_b",
    },
    {
        "week": 3,
        "event_type": "complete_task",
        "path": "/tasks/complete",
        "payload": {
            "user_id": USER_ID,
            "task_id": "{{pull_w3_b.pulled_task.task_id}}",
            "goal_id": "{{pull_w3_b.pulled_task.goal_id}}",
            "milestone_id": "{{pull_w3_b.pulled_task.milestone_id}}",
        },
    },
    {
        "week": 3,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(3)},
    },
    # Week 4: another zero week (market travel).
    {
        "week": 4,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(5)},
    },

    # ─────────────── MONTH 3 — Trade show goal, sharp urgency spike ──────────
    # Trade show in 3 weeks. Urgency: 7–30d bracket → U=1.5.
    # Layer B: urgency multiplier + Tri-Vector renormalization with 2 goals.
    # Expansion goal is slow-burn; trade show is a sharp short-term spike.
    # Layer A Criterion 3: does the system reason about what the trade show
    # goal means for the expansion goal's progress this month?
    {
        "week": 5,
        "event_type": "draft_goal",
        "path": "/goals/draft",
        "payload": {
            "user_id": USER_ID,
            "raw_goal": "Prepare for a trade show in 3 weeks. Need samples, pricing sheets, contacts.",
            "user_context": (
                "Specific trade show, hard 3-week deadline. High business "
                "stakes — this is a direct revenue opportunity. "
                "Still has the product-line expansion goal active."
            ),
        },
        "save_as": "tradeshow_draft",
    },
    {
        "week": 5,
        "event_type": "structure_goal",
        "path": "/goals/structure",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{tradeshow_draft}}",
            "existing_goal_summaries": "{{ACTIVE_GOAL_SUMMARIES}}",
        },
        "save_as": "tradeshow_structured",
    },
    {
        "week": 5,
        "event_type": "confirm_goal",
        "path": "/goals/confirm",
        "payload": {
            "user_id": USER_ID,
            "confirmed_draft": "{{tradeshow_draft}}",
            "smart_assessment": "{{tradeshow_structured}}",
            "week_start": _week_date(5),
        },
        "save_as": "tradeshow_confirmed",
        "notes": (
            "Layer B: urgency multiplier — trade show ~21 days out → "
            "7–30d bracket, U=1.5. Tri-Vector weights should shift "
            "heavily toward trade show. Layer B: Tri-Vector normalization "
            "check — weights across both goals' milestones must sum to 1.0."
        ),
    },
    {
        "week": 5,
        "event_type": "pull_task",
        "path": "/tasks/pull",
        "payload": {
            "user_id": USER_ID,
            "current_energy_level": "HIGH",
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
        "payload": {"user_id": USER_ID, "week_start": _week_date(6)},
    },
    {
        "week": 7,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(8)},
    },

    # ─────────────── MONTH 4 — Trade show closes, expansion resumes ──────────
    # Trade show deadline has passed. Goal closes.
    # Layer B: weight recompute on goal exit — expansion milestones
    # should renormalize to sum=1.0 alone.
    # Expansion goal is now behind pace because Month 3 pulled attention away.
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
            "Back to expansion goal after trade show. Layer B: weight "
            "recompute check — trade show goal should now be closed and "
            "expansion milestones renormalized."
        ),
    },
    {
        "week": 9,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(9)},
    },
    # Another zero week (irregular pattern continues).
    {
        "week": 10,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(11)},
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

    # ─────────────── MONTH 5–6 — Deadline pushback ───────────────────────────
    # Expansion goal is approaching its original 5-month deadline.
    # Ibrahim pushes back hard — the timeline feels unrealistic given
    # all the interruptions. Simulated via goal edit tightening the
    # deadline (or extending it, in character for resistance).
    # TODO: pick whether Ibrahim's pushback results in deadline extension
    # (realistic acknowledgment) or he digs in and keeps original.
    # Extension is the more interesting system behavior — it tests whether
    # the Tri-Vector urgency bracket updates correctly on a LENGTHENED
    # deadline (U drops back down). Pick this unless you want to test
    # stagnation-under-pressure instead.
    {
        "week": 17,
        "event_type": "edit_goal_deadline",
        "method": "PATCH",
        "path": "/goals/{{expansion_confirmed.goal_id}}",
        "payload": {
            "user_id": USER_ID,
            "terminal_deadline": _week_date(30),  # extends by ~3 months
        },
        "save_as": "expansion_deadline_extension",
        "notes": (
            "Ibrahim pushes back on the original deadline. Extending by "
            "~3 months. Layer B: urgency multiplier — if original deadline "
            "was in the 7–30d bracket (U=1.5), the extension should drop "
            "it back to >90d (U=1.0). Weights should shift accordingly. "
            "Layer A Criterion 2: does the system acknowledge the extension "
            "honestly — including surfacing what work remains and what "
            "the new pace implies — rather than just confirming the edit?"
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
        "week": 20,
        "event_type": "advance_week",
        "payload": {"user_id": USER_ID, "week_start": _week_date(23)},
    },
]