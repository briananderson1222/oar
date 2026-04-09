"""Tests for oar.llm.providers.selector — ProviderSelector."""

from unittest.mock import MagicMock

from oar.llm.providers.base import LLMResponse, ProviderUnavailableError
from oar.llm.providers.selector import ProviderSelector


def _mock_provider(name: str, healthy: bool = True, available: bool = True):
    p = MagicMock()
    p.name = name
    p.available = available
    p.health_check.return_value = healthy
    p.complete.return_value = LLMResponse(
        content="ok",
        model=name,
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.0,
    )
    return p


class TestSelect:
    """select() returns first healthy provider."""

    def test_select_returns_first_healthy(self):
        registry = MagicMock()
        p1 = _mock_provider("a", healthy=False)
        p2 = _mock_provider("b", healthy=True)
        registry.get_healthy.side_effect = lambda n: p2 if n == "b" else None

        selector = ProviderSelector(fallback_chain=["a", "b"], registry=registry)
        result = selector.select()
        assert result.name == "b"

    def test_select_raises_when_none_available(self):
        registry = MagicMock()
        registry.get_healthy.return_value = None

        selector = ProviderSelector(fallback_chain=["a"], registry=registry)
        try:
            selector.select()
            assert False, "Should have raised"
        except ProviderUnavailableError:
            pass


class TestSelectWithFallback:
    """select_with_fallback(preferred) returns ordered list."""

    def test_select_with_fallback_preferred_first(self):
        registry = MagicMock()
        p_pref = _mock_provider("preferred", healthy=True)
        p_fallback = _mock_provider("fallback", healthy=True)
        registry.get_healthy.side_effect = lambda n: {
            "preferred": p_pref,
            "fallback": p_fallback,
        }.get(n)

        selector = ProviderSelector(fallback_chain=["fallback"], registry=registry)
        providers = selector.select_with_fallback(preferred="preferred")
        assert len(providers) == 2
        assert providers[0].name == "preferred"
        assert providers[1].name == "fallback"

    def test_select_with_fallback_skips_unhealthy(self):
        registry = MagicMock()
        p_healthy = _mock_provider("ok", healthy=True)
        registry.get_healthy.side_effect = lambda n: p_healthy if n == "ok" else None

        selector = ProviderSelector(fallback_chain=["dead", "ok"], registry=registry)
        providers = selector.select_with_fallback()
        assert len(providers) == 1
        assert providers[0].name == "ok"
