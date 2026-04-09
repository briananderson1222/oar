"""Tests for oar.llm.router with provider system — integration tests."""

from unittest.mock import MagicMock, patch

from oar.llm.cost_tracker import CostTracker
from oar.llm.providers.base import LLMResponse, LLMProviderError
from oar.llm.router import BudgetExceededError, LLMRouter


def _mock_provider(name: str, content: str = "result"):
    p = MagicMock()
    p.name = name
    p.available = True
    p.complete.return_value = LLMResponse(
        content=content,
        model=name,
        input_tokens=50,
        output_tokens=20,
        cost_usd=0.0,
    )
    return p


class TestRouterWithProviders:
    """End-to-end provider usage through LLMRouter."""

    def test_router_uses_provider(self, tmp_path):
        """Router delegates to provider when configured."""
        tracker = CostTracker(tmp_path)
        provider = _mock_provider("claude-cli", "Hello from CLI")

        router = LLMRouter("claude-sonnet-4-20250514", tracker, provider=provider)

        response = router.complete(
            messages=[{"role": "user", "content": "Hi"}],
        )
        assert response.content == "Hello from CLI"
        assert response.model == "claude-cli"
        provider.complete.assert_called_once()

    def test_router_fallback_on_provider_error(self, tmp_path):
        """Router falls back to next provider on recoverable error."""
        tracker = CostTracker(tmp_path)
        provider_a = _mock_provider("a")
        provider_a.complete.side_effect = LLMProviderError(
            "a", "timeout", recoverable=True
        )
        provider_b = _mock_provider("b", "fallback result")

        selector = MagicMock()
        selector.select_with_fallback.return_value = [provider_a, provider_b]

        router = LLMRouter(
            "claude-sonnet-4-20250514",
            tracker,
            provider_selector=selector,
        )
        response = router.complete(
            messages=[{"role": "user", "content": "Hi"}],
        )
        assert response.content == "fallback result"
        provider_b.complete.assert_called_once()

    def test_router_all_providers_fail_raises(self, tmp_path):
        """Router raises when all providers fail."""
        tracker = CostTracker(tmp_path)
        provider_a = _mock_provider("a")
        provider_a.complete.side_effect = LLMProviderError(
            "a", "dead", recoverable=True
        )

        selector = MagicMock()
        selector.select_with_fallback.return_value = [provider_a]

        router = LLMRouter(
            "claude-sonnet-4-20250514",
            tracker,
            provider_selector=selector,
        )
        try:
            router.complete(messages=[{"role": "user", "content": "Hi"}])
            assert False, "Should have raised"
        except LLMProviderError:
            pass

    def test_router_provider_tracks_cost(self, tmp_path):
        """Cost tracking still works with provider responses."""
        tracker = CostTracker(tmp_path)
        provider = _mock_provider("claude-cli")
        provider.complete.return_value = LLMResponse(
            content="ok",
            model="claude-cli",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.0,
        )

        router = LLMRouter("claude-sonnet-4-20250514", tracker, provider=provider)
        router.complete(messages=[{"role": "user", "content": "Hi"}])

        assert tracker.get_session_cost() == 0.0
        history = tracker.get_call_history()
        assert len(history) == 1

    def test_router_backward_compat_litellm(self, tmp_path):
        """Router without provider still works with litellm (backward compat)."""
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)

        mock_usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_response = MagicMock(
            usage=mock_usage,
            choices=[MagicMock(message=MagicMock(content="legacy ok"))],
        )
        with patch("litellm.completion", return_value=mock_response):
            response = router.complete([{"role": "user", "content": "Hi"}])

        assert response.content == "legacy ok"

    def test_router_budget_blocks_provider_call(self, tmp_path):
        """Budget check still works with provider."""
        from oar.llm.budget import BudgetConfig, BudgetManager

        tracker = CostTracker(tmp_path)
        tracker.record("m", 100, 50, 4.95)
        budget_mgr = BudgetManager(
            BudgetConfig(max_per_call=0.50, max_per_session=5.00),
            tracker,
        )
        provider = _mock_provider("cli")

        router = LLMRouter(
            "claude-sonnet-4-20250514",
            tracker,
            budget_manager=budget_mgr,
            provider=provider,
        )
        try:
            router.complete([{"role": "user", "content": "Hi"}])
            assert False, "Should have raised BudgetExceededError"
        except BudgetExceededError:
            pass
        provider.complete.assert_not_called()
