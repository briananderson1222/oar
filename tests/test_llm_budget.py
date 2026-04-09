"""Tests for oar.llm.budget — BudgetManager."""

from oar.llm.budget import BudgetConfig, BudgetManager
from oar.llm.cost_tracker import CostTracker


class TestCanProceed:
    """Budget gate checks."""

    def test_can_proceed_under_budget(self, tmp_path):
        """Returns (True, 'OK') when within budget."""
        tracker = CostTracker(tmp_path)
        config = BudgetConfig(max_per_call=0.50, max_per_session=5.00)
        mgr = BudgetManager(config, tracker)
        ok, reason = mgr.can_proceed(estimated_cost=0.10)
        assert ok is True
        assert reason == "OK"

    def test_can_proceed_over_session_budget(self, tmp_path):
        """Returns (False, reason) when session budget would be exceeded."""
        tracker = CostTracker(tmp_path)
        tracker.record("model", 100, 50, 4.95)
        config = BudgetConfig(max_per_call=0.50, max_per_session=5.00)
        mgr = BudgetManager(config, tracker)
        ok, reason = mgr.can_proceed(estimated_cost=0.10)
        assert ok is False
        assert "Session budget exceeded" in reason

    def test_can_proceed_over_call_budget(self, tmp_path):
        """Returns (False, reason) when a single call exceeds max_per_call."""
        tracker = CostTracker(tmp_path)
        config = BudgetConfig(max_per_call=0.50, max_per_session=5.00)
        mgr = BudgetManager(config, tracker)
        ok, reason = mgr.can_proceed(estimated_cost=0.60)
        assert ok is False
        assert "Single call exceeds max" in reason

    def test_can_proceed_zero_cost(self, tmp_path):
        """Returns (True, 'OK') for zero-cost call."""
        tracker = CostTracker(tmp_path)
        config = BudgetConfig()
        mgr = BudgetManager(config, tracker)
        ok, reason = mgr.can_proceed(estimated_cost=0.0)
        assert ok is True
        assert reason == "OK"


class TestGetStatus:
    """Budget status summary."""

    def test_get_status_returns_summary(self, tmp_path):
        """Returns correct dict structure."""
        tracker = CostTracker(tmp_path)
        config = BudgetConfig(max_per_call=0.50, max_per_session=5.00)
        mgr = BudgetManager(config, tracker)
        status = mgr.get_status()
        assert "session_cost" in status
        assert "session_budget" in status
        assert "session_remaining" in status
        assert "session_utilization" in status
        assert status["session_budget"] == 5.00

    def test_budget_status_utilization(self, tmp_path):
        """Calculates correct utilization percentage."""
        tracker = CostTracker(tmp_path)
        tracker.record("model", 100, 50, 1.00)
        config = BudgetConfig(max_per_call=0.50, max_per_session=5.00)
        mgr = BudgetManager(config, tracker)
        status = mgr.get_status()
        assert status["session_cost"] == 1.00
        assert status["session_remaining"] == 4.00
        assert abs(status["session_utilization"] - 0.2) < 1e-9

    def test_budget_status_no_spending(self, tmp_path):
        """Zero spending gives zero utilization."""
        tracker = CostTracker(tmp_path)
        config = BudgetConfig(max_per_session=5.00)
        mgr = BudgetManager(config, tracker)
        status = mgr.get_status()
        assert status["session_cost"] == 0.0
        assert status["session_remaining"] == 5.00
        assert status["session_utilization"] == 0.0
