# PATH: stride_backend/tests/test_scheduling_component.py

import pytest
from datetime import date

from core.scheduling.scheduling_component import SchedulingComponent
from core.schemas.contracts.execution_engine import (
    MilestoneAllocationData,
    SlotAllocationInput,
    SlotAllocationOutput,
)
from core.schemas.enums import EnergyLevel


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_slot(day: str, start_time: str, energy: str) -> dict:
    return {"day": day, "start_time": start_time, "energy_level": energy}


def _make_slot_grid(*slots: dict) -> dict:
    return {
        "user_id": "user_001",
        "week_start": "2025-06-02",
        "slots": list(slots),
    }


def _make_milestone(
    milestone_id: str,
    weight: float,
    min_units: int,
    max_units: int,
) -> MilestoneAllocationData:
    return MilestoneAllocationData(
        milestone_id=milestone_id,
        tri_vector_weight=weight,
        min_weekly_units=min_units,
        max_weekly_units=max_units,
    )


def _make_input(milestones, slot_grid) -> SlotAllocationInput:
    return SlotAllocationInput(
        user_id="user_001",
        week_start=date(2025, 6, 2),
        milestones=milestones,
        slot_grid=slot_grid,
    )


FULL_WEEK_HIGH = _make_slot_grid(
    _make_slot("Monday",    "09:00", "HIGH"),
    _make_slot("Tuesday",   "09:00", "HIGH"),
    _make_slot("Wednesday", "09:00", "HIGH"),
    _make_slot("Thursday",  "09:00", "HIGH"),
    _make_slot("Friday",    "09:00", "HIGH"),
)


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestSchedulingComponentBasic:

    def setup_method(self):
        self.component = SchedulingComponent()

    def test_returns_slot_allocation_output(self):
        milestones = [_make_milestone("m1", 1.0, 4, 12)]
        result = self.component.allocate_slots(_make_input(milestones, FULL_WEEK_HIGH))
        assert isinstance(result, SlotAllocationOutput)

    def test_no_error_on_valid_input(self):
        milestones = [_make_milestone("m1", 1.0, 4, 12)]
        result = self.component.allocate_slots(_make_input(milestones, FULL_WEEK_HIGH))
        assert result.error is None

    def test_returns_plan_per_milestone(self):
        milestones = [
            _make_milestone("m1", 0.7, 4, 12),
            _make_milestone("m2", 0.3, 2, 6),
        ]
        result = self.component.allocate_slots(_make_input(milestones, FULL_WEEK_HIGH))
        assert len(result.deep_session_plans) == 2

    def test_plan_ids_match_milestone_ids(self):
        milestones = [
            _make_milestone("m1", 0.7, 4, 12),
            _make_milestone("m2", 0.3, 2, 6),
        ]
        result = self.component.allocate_slots(_make_input(milestones, FULL_WEEK_HIGH))
        plan_ids = {p.milestone_id for p in result.deep_session_plans}
        assert plan_ids == {"m1", "m2"}

    def test_user_id_passed_through(self):
        milestones = [_make_milestone("m1", 1.0, 4, 12)]
        result = self.component.allocate_slots(_make_input(milestones, FULL_WEEK_HIGH))
        assert result.user_id == "user_001"

    def test_week_start_passed_through(self):
        milestones = [_make_milestone("m1", 1.0, 4, 12)]
        result = self.component.allocate_slots(_make_input(milestones, FULL_WEEK_HIGH))
        assert result.week_start == date(2025, 6, 2)


class TestSchedulingComponentGapConstraint:

    def setup_method(self):
        self.component = SchedulingComponent()

    def test_deep_sessions_respect_minimum_gap(self):
        """No two DEEP sessions for same milestone on consecutive days."""
        milestones = [_make_milestone("m1", 1.0, 4, 16)]
        result = self.component.allocate_slots(_make_input(milestones, FULL_WEEK_HIGH))
        plan = result.deep_session_plans[0]
        days = plan.assigned_days
        from core.scheduling.scheduling_component import DAY_INDEX
        for i in range(len(days) - 1):
            gap = DAY_INDEX[days[i + 1]] - DAY_INDEX[days[i]]
            assert gap >= 2, f"Gap too small between {days[i]} and {days[i+1]}"

    def test_single_milestone_gets_sessions_across_week(self):
        milestones = [_make_milestone("m1", 1.0, 4, 16)]
        result = self.component.allocate_slots(_make_input(milestones, FULL_WEEK_HIGH))
        plan = result.deep_session_plans[0]
        assert plan.sessions_planned >= 1

    def test_assigned_days_are_valid_day_names(self):
        milestones = [_make_milestone("m1", 1.0, 4, 12)]
        result = self.component.allocate_slots(_make_input(milestones, FULL_WEEK_HIGH))
        valid_days = {"Monday", "Tuesday", "Wednesday", "Thursday",
                      "Friday", "Saturday", "Sunday"}
        for plan in result.deep_session_plans:
            for day in plan.assigned_days:
                assert day in valid_days


class TestSchedulingComponentPriority:

    def setup_method(self):
        self.component = SchedulingComponent()

    def test_higher_weight_milestone_gets_first_pick(self):
        """
        With limited HIGH energy windows, the heavier milestone
        should get more or earlier sessions.
        """
        limited_grid = _make_slot_grid(
            _make_slot("Monday",    "09:00", "HIGH"),
            _make_slot("Wednesday", "09:00", "HIGH"),
        )
        milestones = [
            _make_milestone("heavy", 0.8, 4, 12),
            _make_milestone("light", 0.2, 2, 6),
        ]
        result = self.component.allocate_slots(
            _make_input(milestones, limited_grid)
        )
        heavy_plan = next(p for p in result.deep_session_plans
                          if p.milestone_id == "heavy")
        light_plan = next(p for p in result.deep_session_plans
                          if p.milestone_id == "light")
        # Heavy milestone should have sessions planned
        assert heavy_plan.sessions_planned >= 1
        # Light milestone may have partial allocation
        total_planned = heavy_plan.sessions_planned + light_plan.sessions_planned
        assert total_planned <= 2   # only 2 windows available

    def test_milestones_do_not_share_windows(self):
        """Two milestones cannot be assigned the same timeslot."""
        two_window_grid = _make_slot_grid(
            _make_slot("Monday",   "09:00", "HIGH"),
            _make_slot("Thursday", "09:00", "HIGH"),
        )
        milestones = [
            _make_milestone("m1", 0.6, 4, 8),
            _make_milestone("m2", 0.4, 4, 8),
        ]
        result = self.component.allocate_slots(
            _make_input(milestones, two_window_grid)
        )
        all_days = []
        for plan in result.deep_session_plans:
            all_days.extend(plan.assigned_days)
        # No duplicate days across milestones
        assert len(all_days) == len(set(all_days))


class TestSchedulingComponentEdgeCases:

    def setup_method(self):
        self.component = SchedulingComponent()

    def test_no_high_energy_slots_returns_partial_allocation(self):
        low_grid = _make_slot_grid(
            _make_slot("Monday",  "09:00", "LOW"),
            _make_slot("Tuesday", "09:00", "MEDIUM"),
        )
        milestones = [_make_milestone("m1", 1.0, 4, 12)]
        result = self.component.allocate_slots(_make_input(milestones, low_grid))
        assert result.error is None
        plan = result.deep_session_plans[0]
        assert plan.partial_allocation is True
        assert plan.sessions_planned == 0

    def test_zero_max_units_milestone_skipped(self):
        milestones = [
            _make_milestone("active", 0.8, 4, 12),
            _make_milestone("zeroed", 0.2, 0, 0),
        ]
        result = self.component.allocate_slots(
            _make_input(milestones, FULL_WEEK_HIGH)
        )
        zeroed_plan = next(p for p in result.deep_session_plans
                           if p.milestone_id == "zeroed")
        assert zeroed_plan.sessions_planned == 0
        assert zeroed_plan.sessions_needed == 0
        assert zeroed_plan.partial_allocation is False

    def test_empty_milestone_list_returns_empty_plans(self):
        result = self.component.allocate_slots(
            _make_input([], FULL_WEEK_HIGH)
        )
        assert result.error is None
        assert result.deep_session_plans == []

    def test_single_available_window_fallback(self):
        """
        If only one window exists and two milestones compete,
        higher weight wins. Lower gets fallback or zero.
        """
        one_window_grid = _make_slot_grid(
            _make_slot("Wednesday", "09:00", "HIGH"),
        )
        milestones = [
            _make_milestone("m1", 0.7, 4, 8),
            _make_milestone("m2", 0.3, 4, 8),
        ]
        result = self.component.allocate_slots(
            _make_input(milestones, one_window_grid)
        )
        total_planned = sum(p.sessions_planned for p in result.deep_session_plans)
        assert total_planned == 1   # only one window — only one session possible

    def test_medium_energy_slots_ignored(self):
        medium_grid = _make_slot_grid(
            _make_slot("Monday",  "09:00", "MEDIUM"),
            _make_slot("Tuesday", "09:00", "MEDIUM"),
            _make_slot("Wednesday", "09:00", "HIGH"),
        )
        milestones = [_make_milestone("m1", 1.0, 4, 8)]
        result = self.component.allocate_slots(
            _make_input(milestones, medium_grid)
        )
        plan = result.deep_session_plans[0]
        assert plan.assigned_days == ["Wednesday"]

    def test_output_schema_version_correct(self):
        milestones = [_make_milestone("m1", 1.0, 4, 12)]
        result = self.component.allocate_slots(_make_input(milestones, FULL_WEEK_HIGH))
        assert result.schema_version == 1