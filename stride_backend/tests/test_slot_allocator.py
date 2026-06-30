# PATH: stride_backend/tests/test_slot_allocator.py

import pytest
from typing import Dict, List

from core.execution.slot_allocator import SlotAllocator
from core.schemas.contracts.execution_engine import (
    MilestoneAllocationData,
    QueuePullRequest,
    QueuePullResponse,
)
from core.schemas.entities import Task
from core.schemas.enums import EnergyLevel, TaskStatus, TaskTag


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_task(
    task_id: str,
    milestone_id: str,
    tag: TaskTag,
    status: TaskStatus = TaskStatus.AVAILABLE,
) -> Task:
    return Task(
        task_id=task_id,
        milestone_id=milestone_id,
        goal_id="goal_001",
        user_id="user_001",
        description=f"Task {task_id}",
        tag=tag,
        dependencies=[],
        status=status,
    )


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


def _make_request(
    energy: EnergyLevel = EnergyLevel.HIGH,
    last_tag: TaskTag = None,
    last_milestone: str = None,
    consecutive: int = 0,
    force_pull: bool = False,
) -> QueuePullRequest:
    return QueuePullRequest(
        user_id="user_001",
        current_energy_level=energy,
        last_task_tag=last_tag,
        last_milestone_id=last_milestone,
        consecutive_pull_count=consecutive,
        force_pull=force_pull,
    )


# ── Basic pull tests ───────────────────────────────────────────────────────────

class TestSlotAllocatorBasic:

    def setup_method(self):
        self.allocator = SlotAllocator()

    def test_returns_queue_pull_response(self):
        tasks = [_make_task("t1", "m1", TaskTag.MODERATE)]
        milestones = [_make_milestone("m1", 1.0, 2, 8)]
        result = self.allocator.pull(
            _make_request(), tasks, milestones, {"m1": 0}
        )
        assert isinstance(result, QueuePullResponse)

    def test_returns_task_when_available(self):
        tasks = [_make_task("t1", "m1", TaskTag.MODERATE)]
        milestones = [_make_milestone("m1", 1.0, 2, 8)]
        result = self.allocator.pull(
            _make_request(), tasks, milestones, {"m1": 0}
        )
        assert result.pulled_task is not None
        assert result.pulled_task.task_id == "t1"

    def test_no_error_on_valid_pull(self):
        tasks = [_make_task("t1", "m1", TaskTag.MODERATE)]
        milestones = [_make_milestone("m1", 1.0, 2, 8)]
        result = self.allocator.pull(
            _make_request(), tasks, milestones, {"m1": 0}
        )
        assert result.error is None

    def test_empty_task_pool_returns_no_eligible(self):
        result = self.allocator.pull(
            _make_request(), [], [], {}
        )
        assert result.pulled_task is None
        assert result.state_message == "NO_ELIGIBLE_TASKS"


# ── Refractory rule tests ──────────────────────────────────────────────────────

class TestSlotAllocatorRefractoryRules:

    def setup_method(self):
        self.allocator = SlotAllocator()

    def test_deep_lockout_after_deep_task(self):
        """After a DEEP task, no DEEP tasks should be returned."""
        tasks = [
            _make_task("deep_t", "m1", TaskTag.DEEP),
            _make_task("mod_t",  "m1", TaskTag.MODERATE),
        ]
        milestones = [_make_milestone("m1", 1.0, 2, 12)]
        request = _make_request(last_tag=TaskTag.DEEP, consecutive=99)
        result = self.allocator.pull(request, tasks, milestones, {"m1": 0})
        assert result.pulled_task is not None
        assert result.pulled_task.tag != TaskTag.DEEP

    def test_deep_lockout_state_message_when_only_deep_available(self):
        """If only DEEP tasks remain after lockout, return DEEP_LOCKOUT."""
        tasks = [_make_task("deep_t", "m1", TaskTag.DEEP)]
        milestones = [_make_milestone("m1", 1.0, 2, 12)]
        request = _make_request(last_tag=TaskTag.DEEP, consecutive=99)
        result = self.allocator.pull(request, tasks, milestones, {"m1": 0})
        assert result.pulled_task is None
        assert result.state_message == "DEEP_LOCKOUT"

    def test_no_deep_on_low_energy(self):
        tasks = [
            _make_task("deep_t", "m1", TaskTag.DEEP),
            _make_task("mech_t", "m1", TaskTag.MECHANICAL),
        ]
        milestones = [_make_milestone("m1", 1.0, 2, 12)]
        result = self.allocator.pull(
            _make_request(energy=EnergyLevel.LOW),
            tasks, milestones, {"m1": 0}
        )
        assert result.pulled_task is not None
        assert result.pulled_task.tag == TaskTag.MECHANICAL

    def test_no_deep_on_medium_energy(self):
        tasks = [
            _make_task("deep_t", "m1", TaskTag.DEEP),
            _make_task("mod_t",  "m1", TaskTag.MODERATE),
        ]
        milestones = [_make_milestone("m1", 1.0, 2, 12)]
        result = self.allocator.pull(
            _make_request(energy=EnergyLevel.MEDIUM),
            tasks, milestones, {"m1": 0}
        )
        assert result.pulled_task.tag == TaskTag.MODERATE

    def test_force_pull_bypasses_energy_filter(self):
        tasks = [_make_task("deep_t", "m1", TaskTag.DEEP)]
        milestones = [_make_milestone("m1", 1.0, 2, 12)]
        result = self.allocator.pull(
            _make_request(energy=EnergyLevel.LOW, force_pull=True),
            tasks, milestones, {"m1": 0}
        )
        assert result.pulled_task is not None
        assert result.pulled_task.tag == TaskTag.DEEP

    def test_force_pull_does_not_bypass_deep_lockout(self):
        """force_pull bypasses energy filter only — not DEEP lockout."""
        tasks = [_make_task("deep_t", "m1", TaskTag.DEEP)]
        milestones = [_make_milestone("m1", 1.0, 2, 12)]
        request = _make_request(
            energy=EnergyLevel.LOW,
            last_tag=TaskTag.DEEP,
            consecutive=99,
            force_pull=True,
        )
        result = self.allocator.pull(request, tasks, milestones, {"m1": 0})
        assert result.pulled_task is None
        assert result.state_message == "DEEP_LOCKOUT"

    def test_anti_clumping_forces_rotation_after_2_pulls(self):
        """After 2 consecutive pulls from m1, must switch to m2."""
        tasks = [
            _make_task("t1", "m1", TaskTag.MODERATE),
            _make_task("t2", "m2", TaskTag.MODERATE),
        ]
        milestones = [
            _make_milestone("m1", 0.6, 2, 8),
            _make_milestone("m2", 0.4, 2, 8),
        ]
        request = _make_request(
            last_milestone="m1",
            consecutive=2,
        )
        result = self.allocator.pull(request, tasks, milestones, {"m1": 2, "m2": 0})
        assert result.pulled_task is not None
        assert result.pulled_task.milestone_id == "m2"

    def test_sentinel_forces_milestone_rotation(self):
        """DEEP_LOCKOUT_SENTINEL forces rotation away from last milestone."""
        tasks = [
            _make_task("t1", "m1", TaskTag.MODERATE),
            _make_task("t2", "m2", TaskTag.MODERATE),
        ]
        milestones = [
            _make_milestone("m1", 0.6, 2, 8),
            _make_milestone("m2", 0.4, 2, 8),
        ]
        request = _make_request(last_milestone="m1", consecutive=99)
        result = self.allocator.pull(request, tasks, milestones, {"m1": 4, "m2": 0})
        assert result.pulled_task.milestone_id == "m2"


# ── Two-tier priority tests ────────────────────────────────────────────────────

class TestSlotAllocatorPriority:

    def setup_method(self):
        self.allocator = SlotAllocator()

    def test_tier1_starved_milestone_gets_priority(self):
        """Starved milestone wins even if another has lower ceiling progress."""
        tasks = [
            _make_task("t1", "starved", TaskTag.MODERATE),
            _make_task("t2", "safe",    TaskTag.MODERATE),
        ]
        milestones = [
            _make_milestone("starved", 0.3, 4, 8),   # needs 4, has 0 — starved
            _make_milestone("safe",    0.7, 4, 12),  # needs 4, has 6 — safe
        ]
        result = self.allocator.pull(
            _make_request(),
            tasks,
            milestones,
            {"starved": 0, "safe": 6},
        )
        assert result.pulled_task.milestone_id == "starved"
        assert result.state_message == "PULLING"

    def test_tier2_ceiling_progress_determines_priority(self):
        """When all milestones above floor, furthest from ceiling wins."""
        tasks = [
            _make_task("t1", "m1", TaskTag.MODERATE),
            _make_task("t2", "m2", TaskTag.MODERATE),
        ]
        milestones = [
            _make_milestone("m1", 0.6, 2, 10),   # consumed 8/10 = 80% to ceiling
            _make_milestone("m2", 0.4, 2, 10),   # consumed 3/10 = 30% to ceiling
        ]
        result = self.allocator.pull(
            _make_request(),
            tasks,
            milestones,
            {"m1": 8, "m2": 3},
        )
        # m2 is furthest from ceiling — should be pulled
        assert result.pulled_task.milestone_id == "m2"
        assert result.state_message == "MINIMUMS_MET"

    def test_all_ceilings_reached_returns_correct_state(self):
        tasks = [
            _make_task("t1", "m1", TaskTag.MODERATE),
        ]
        milestones = [_make_milestone("m1", 1.0, 2, 8)]
        result = self.allocator.pull(
            _make_request(),
            tasks,
            milestones,
            {"m1": 8},   # consumed == max → ceiling hit
        )
        assert result.pulled_task is None
        assert result.state_message == "ALL_CEILINGS_REACHED"

    def test_lowest_floor_deficit_wins_in_tier1(self):
        """
        Two starved milestones — the one with lower floor deficit ratio
        (most behind) should be pulled first.
        """
        tasks = [
            _make_task("t1", "m1", TaskTag.MODERATE),
            _make_task("t2", "m2", TaskTag.MODERATE),
        ]
        milestones = [
            _make_milestone("m1", 0.5, 10, 20),  # consumed 1/10 = 0.10 deficit
            _make_milestone("m2", 0.5, 10, 20),  # consumed 3/10 = 0.30 deficit
        ]
        # m1 has lower deficit ratio → more behind → pulled first
        result = self.allocator.pull(
            _make_request(),
            tasks,
            milestones,
            {"m1": 1, "m2": 3},
        )
        assert result.pulled_task.milestone_id == "m1"


# ── Ceiling filter tests ───────────────────────────────────────────────────────

class TestSlotAllocatorCeilingFilter:

    def setup_method(self):
        self.allocator = SlotAllocator()

    def test_ceiling_hit_removes_milestone_from_pool(self):
        tasks = [
            _make_task("t1", "m1", TaskTag.MODERATE),  # m1 at ceiling
            _make_task("t2", "m2", TaskTag.MODERATE),  # m2 has room
        ]
        milestones = [
            _make_milestone("m1", 0.6, 2, 8),
            _make_milestone("m2", 0.4, 2, 8),
        ]
        result = self.allocator.pull(
            _make_request(),
            tasks,
            milestones,
            {"m1": 8, "m2": 2},   # m1 at ceiling
        )
        assert result.pulled_task.milestone_id == "m2"

    def test_all_milestones_at_ceiling_returns_all_ceilings_reached(self):
        tasks = [
            _make_task("t1", "m1", TaskTag.MODERATE),
            _make_task("t2", "m2", TaskTag.MODERATE),
        ]
        milestones = [
            _make_milestone("m1", 0.6, 2, 8),
            _make_milestone("m2", 0.4, 2, 6),
        ]
        result = self.allocator.pull(
            _make_request(),
            tasks,
            milestones,
            {"m1": 8, "m2": 6},
        )
        assert result.pulled_task is None
        assert result.state_message == "ALL_CEILINGS_REACHED"


# ── Edge case tests ────────────────────────────────────────────────────────────

class TestSlotAllocatorEdgeCases:

    def setup_method(self):
        self.allocator = SlotAllocator()

    def test_pending_tasks_excluded(self):
        tasks = [
            _make_task("t1", "m1", TaskTag.MODERATE, TaskStatus.PENDING),
            _make_task("t2", "m1", TaskTag.MODERATE, TaskStatus.AVAILABLE),
        ]
        milestones = [_make_milestone("m1", 1.0, 2, 8)]
        result = self.allocator.pull(
            _make_request(), tasks, milestones, {"m1": 0}
        )
        assert result.pulled_task.task_id == "t2"

    def test_completed_tasks_excluded(self):
        tasks = [
            _make_task("t1", "m1", TaskTag.MODERATE, TaskStatus.COMPLETED),
            _make_task("t2", "m1", TaskTag.MODERATE, TaskStatus.AVAILABLE),
        ]
        milestones = [_make_milestone("m1", 1.0, 2, 8)]
        result = self.allocator.pull(
            _make_request(), tasks, milestones, {"m1": 0}
        )
        assert result.pulled_task.task_id == "t2"

    def test_superseded_tasks_excluded(self):
        """SUPERSEDED tasks (replaced by breakdown tasks) must never be pulled."""
        tasks = [
            _make_task("t1", "m1", TaskTag.MODERATE, TaskStatus.SUPERSEDED),
            _make_task("t2", "m1", TaskTag.MODERATE, TaskStatus.AVAILABLE),
        ]
        milestones = [_make_milestone("m1", 1.0, 2, 8)]
        result = self.allocator.pull(
            _make_request(), tasks, milestones, {"m1": 0}
        )
        assert result.pulled_task.task_id == "t2"

    def test_single_task_single_milestone_clean_pull(self):
        tasks = [_make_task("t1", "m1", TaskTag.MECHANICAL)]
        milestones = [_make_milestone("m1", 1.0, 1, 4)]
        result = self.allocator.pull(
            _make_request(energy=EnergyLevel.LOW),
            tasks, milestones, {"m1": 0}
        )
        assert result.pulled_task.task_id == "t1"
        assert result.error is None

    def test_fresh_session_no_client_state(self):
        """First pull of the session — no last_tag, no last_milestone."""
        tasks = [_make_task("t1", "m1", TaskTag.DEEP)]
        milestones = [_make_milestone("m1", 1.0, 4, 12)]
        result = self.allocator.pull(
            _make_request(energy=EnergyLevel.HIGH),
            tasks, milestones, {"m1": 0}
        )
        assert result.pulled_task is not None
        assert result.pulled_task.tag == TaskTag.DEEP

    def test_schema_version_on_response(self):
        tasks = [_make_task("t1", "m1", TaskTag.MODERATE)]
        milestones = [_make_milestone("m1", 1.0, 2, 8)]
        result = self.allocator.pull(
            _make_request(), tasks, milestones, {"m1": 0}
        )
        assert result.schema_version == 1

    def test_dependency_filter_blocks_unmet_dependency(self):
        """A task depending on an incomplete task must not be eligible."""
        tasks = [
            _make_task("blocker", "m1", TaskTag.MECHANICAL, TaskStatus.AVAILABLE),
        ]
        blocked = _make_task("blocked", "m1", TaskTag.MODERATE)
        blocked.dependencies = ["blocker"]
        tasks.append(blocked)
        milestones = [_make_milestone("m1", 1.0, 2, 8)]
        result = self.allocator.pull(
            _make_request(), tasks, milestones, {"m1": 0}
        )
        # blocker is AVAILABLE but not COMPLETED, so "blocked" stays ineligible
        assert result.pulled_task.task_id == "blocker"