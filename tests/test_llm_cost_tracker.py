"""Tests for oar.llm.cost_tracker — CostTracker and estimate_cost."""

import json
from pathlib import Path

from oar.llm.cost_tracker import CostTracker, estimate_cost


class TestEstimateCost:
    """Cost estimation by model."""

    def test_estimate_cost_sonnet(self):
        cost = estimate_cost("claude-sonnet-4-20250514", 1000, 500)
        # 1000 * 3/1M + 500 * 15/1M = 0.003 + 0.0075 = 0.0105
        assert cost == 0.0105

    def test_estimate_cost_haiku(self):
        cost = estimate_cost("claude-3-5-haiku-20241022", 1000, 500)
        # 1000 * 0.25/1M + 500 * 1.25/1M = 0.00025 + 0.000625 = 0.000875
        assert cost == 0.00087500

    def test_estimate_cost_unknown_model_uses_default(self):
        cost = estimate_cost("unknown-model", 1000, 500)
        # Default: Sonnet pricing
        assert cost == 0.0105

    def test_estimate_cost_litellm_prefix(self):
        cost = estimate_cost("anthropic/claude-sonnet-4-20250514", 1000, 500)
        assert cost == 0.0105


class TestCostTrackerRecord:
    """Recording calls."""

    def test_cost_tracker_records_call(self, tmp_path):
        tracker = CostTracker(tmp_path)
        tracker.record("test-model", 100, 50, 0.01, task="compile")
        assert tracker.get_session_cost() == 0.01

    def test_cost_tracker_session_cost_sums(self, tmp_path):
        tracker = CostTracker(tmp_path)
        tracker.record("model-a", 100, 50, 0.01, task="compile")
        tracker.record("model-a", 200, 100, 0.02, task="classify")
        assert tracker.get_session_cost() == 0.03


class TestCostTrackerBudget:
    """Budget checking."""

    def test_cost_tracker_check_budget_under(self, tmp_path):
        tracker = CostTracker(tmp_path)
        tracker.record("model", 100, 50, 0.01)
        assert tracker.check_budget(1.00) is True

    def test_cost_tracker_check_budget_over(self, tmp_path):
        tracker = CostTracker(tmp_path)
        tracker.record("model", 100, 50, 5.00)
        assert tracker.check_budget(3.00) is False


class TestCostTrackerPersistence:
    """JSONL file persistence."""

    def test_cost_tracker_persists_to_disk(self, tmp_path):
        tracker = CostTracker(tmp_path)
        tracker.record("test-model", 100, 50, 0.01, task="compile")

        history_path = tmp_path / "cost-history.jsonl"
        assert history_path.exists()

        lines = history_path.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["model"] == "test-model"
        assert entry["input_tokens"] == 100
        assert entry["output_tokens"] == 50
        assert entry["cost_usd"] == 0.01
        assert entry["task"] == "compile"

    def test_cost_tracker_get_total_cost(self, tmp_path):
        tracker = CostTracker(tmp_path)
        tracker.record("m1", 100, 50, 0.01)
        tracker.record("m2", 200, 100, 0.02)

        # New tracker reads from the same file.
        tracker2 = CostTracker(tmp_path)
        assert tracker2.get_total_cost() == 0.03

    def test_cost_tracker_get_call_history(self, tmp_path):
        tracker = CostTracker(tmp_path)
        tracker.record("m1", 100, 50, 0.01)
        tracker.record("m2", 200, 100, 0.02)

        history = tracker.get_call_history()
        assert len(history) == 2
        assert history[0]["model"] == "m1"
        assert history[1]["model"] == "m2"

    def test_cost_tracker_get_total_cost_no_file(self, tmp_path):
        tracker = CostTracker(tmp_path)
        assert tracker.get_total_cost() == 0.0

    def test_cost_tracker_get_call_history_no_file(self, tmp_path):
        tracker = CostTracker(tmp_path)
        assert tracker.get_call_history() == []
