"""Tests for oar.llm.router — LLMRouter (all litellm calls mocked)."""

from unittest.mock import MagicMock, patch

from oar.llm.budget import BudgetConfig, BudgetManager
from oar.llm.cost_tracker import CostTracker
from oar.llm.router import BudgetExceededError, LLMRouter


def _mock_litellm_response(
    content: str, input_tokens: int = 100, output_tokens: int = 50
):
    """Build a mock litellm response object."""
    return MagicMock(
        usage=MagicMock(prompt_tokens=input_tokens, completion_tokens=output_tokens),
        choices=[MagicMock(message=MagicMock(content=content))],
    )


class TestRouterComplete:
    """Basic completion calls."""

    def test_router_complete_returns_response(self, tmp_path):
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_litellm_response("Hello world")
            response = router.complete([{"role": "user", "content": "Hi"}])

        assert response.content == "Hello world"
        assert response.input_tokens == 100
        assert response.output_tokens == 50
        assert response.cached is False

    def test_router_uses_default_model(self, tmp_path):
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_litellm_response("ok")
            router.complete([{"role": "user", "content": "Hi"}])

        mock_completion.assert_called_once()
        assert mock_completion.call_args.kwargs["model"] == "claude-sonnet-4-20250514"

    def test_router_overrides_model(self, tmp_path):
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_litellm_response("ok")
            router.complete(
                [{"role": "user", "content": "Hi"}],
                model="claude-3-5-haiku-20241022",
            )

        mock_completion.assert_called_once()
        assert mock_completion.call_args.kwargs["model"] == "claude-3-5-haiku-20241022"

    def test_router_records_cost(self, tmp_path):
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_litellm_response("ok", 1000, 500)
            router.complete([{"role": "user", "content": "Hi"}])

        # Cost should be tracked.
        assert tracker.get_session_cost() > 0
        assert len(tracker.get_call_history()) == 1

    def test_router_handles_api_error(self, tmp_path):
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)

        with patch("litellm.completion") as mock_completion:
            mock_completion.side_effect = Exception("API rate limit exceeded")
            try:
                router.complete([{"role": "user", "content": "Hi"}])
                assert False, "Should have raised"
            except Exception as exc:
                assert "API rate limit exceeded" in str(exc)


class TestRouterBudgetIntegration:
    """Budget-aware router behaviour."""

    def test_router_budget_check_blocks(self, tmp_path):
        """Router raises BudgetExceededError when budget exceeded."""
        tracker = CostTracker(tmp_path)
        # Pre-spend to near the session limit.
        tracker.record("model", 100, 50, 4.95)
        budget_mgr = BudgetManager(
            BudgetConfig(max_per_call=0.50, max_per_session=5.00),
            tracker,
        )
        router = LLMRouter(
            "claude-sonnet-4-20250514", tracker, budget_manager=budget_mgr
        )

        with patch("litellm.completion") as mock_completion:
            try:
                router.complete([{"role": "user", "content": "Hi"}])
                assert False, "Should have raised BudgetExceededError"
            except BudgetExceededError:
                pass
            mock_completion.assert_not_called()

    def test_router_budget_check_allows(self, tmp_path):
        """Router proceeds when budget is fine."""
        tracker = CostTracker(tmp_path)
        budget_mgr = BudgetManager(
            BudgetConfig(max_per_call=0.50, max_per_session=5.00),
            tracker,
        )
        router = LLMRouter(
            "claude-sonnet-4-20250514", tracker, budget_manager=budget_mgr
        )

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_litellm_response("ok")
            response = router.complete([{"role": "user", "content": "Hi"}])

        assert response.content == "ok"

    def test_router_no_budget_manager_no_check(self, tmp_path):
        """Router without budget manager skips budget check (backward compat)."""
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_litellm_response("ok")
            response = router.complete([{"role": "user", "content": "Hi"}])

        assert response.content == "ok"


class TestRouterModelSelection:
    """select_model method."""

    def test_router_select_model_default(self, tmp_path):
        """select_model returns default model for unknown tasks."""
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)
        assert router.select_model("unknown_task") == "claude-sonnet-4-20250514"

    def test_router_select_model_with_task_model_map(self, tmp_path):
        """select_model uses task_model_map when task is present."""
        tracker = CostTracker(tmp_path)
        router = LLMRouter(
            "claude-sonnet-4-20250514",
            tracker,
            task_model_map={"lint": "claude-haiku-4-20250414"},
        )
        assert router.select_model("lint") == "claude-haiku-4-20250414"

    def test_router_select_model_falls_through(self, tmp_path):
        """select_model falls through to get_model_for_task for known tasks."""
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)
        # compile → COMPLEX → uses online_model (default)
        assert router.select_model("compile") == "claude-sonnet-4-20250514"


class TestRouterGetStatus:
    """get_status method."""

    def test_router_get_status(self, tmp_path):
        """Returns status dict with budget info."""
        tracker = CostTracker(tmp_path)
        budget_mgr = BudgetManager(
            BudgetConfig(max_per_session=5.00),
            tracker,
        )
        router = LLMRouter(
            "claude-sonnet-4-20250514", tracker, budget_manager=budget_mgr
        )
        status = router.get_status()
        assert status["default_model"] == "claude-sonnet-4-20250514"
        assert status["session_cost"] == 0.0
        assert "budget" in status
        assert status["budget"]["session_budget"] == 5.00

    def test_router_get_status_no_budget(self, tmp_path):
        """Returns status without budget key when no budget manager."""
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)
        status = router.get_status()
        assert status["default_model"] == "claude-sonnet-4-20250514"
        assert "budget" not in status
