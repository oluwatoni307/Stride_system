import pytest
from datetime import datetime, timezone

from core.feedback.feedback_loop import FeedbackLoop
from core.schemas.contracts.feedback_loop import Boundary3Input


class TestFeedbackLoop:

    def setup_method(self):
        self.loop = FeedbackLoop()
        self.base_args = {
            "user_id": "user_001",
            "task_id": "task_001",
            "goal_id": "goal_001",
            "milestone_id": "milestone_001",
        }

    def test_returns_boundary3_input(self):
        result = self.loop.package_completion_event(**self.base_args)
        assert isinstance(result, Boundary3Input)

    def test_fields_mapped_correctly(self):
        result = self.loop.package_completion_event(**self.base_args)
        assert result.user_id == "user_001"
        assert result.task_id == "task_001"
        assert result.goal_id == "goal_001"
        assert result.milestone_id == "milestone_001"

    def test_trigger_significance_check_always_false(self):
        result = self.loop.package_completion_event(**self.base_args)
        assert result.trigger_significance_check is False

    def test_user_note_optional(self):
        result = self.loop.package_completion_event(**self.base_args)
        assert result.user_note is None

    def test_user_note_passed_through(self):
        result = self.loop.package_completion_event(
            **self.base_args,
            user_note="Finished earlier than expected"
        )
        assert result.user_note == "Finished earlier than expected"

    def test_completion_timestamp_defaults_to_now(self):
        before = datetime.now(timezone.utc).isoformat()
        result = self.loop.package_completion_event(**self.base_args)
        after = datetime.now(timezone.utc).isoformat()
        assert before <= result.completion_timestamp <= after

    def test_completion_timestamp_accepted_when_provided(self):
        ts = "2025-06-01T10:00:00+00:00"
        result = self.loop.package_completion_event(
            **self.base_args,
            completion_timestamp=ts
        )
        assert result.completion_timestamp == ts

    def test_schema_version_is_1(self):
        result = self.loop.package_completion_event(**self.base_args)
        assert result.schema_version == 1