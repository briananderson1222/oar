"""Tests for oar.llm.providers.base — dataclasses and exceptions."""

from oar.llm.providers.base import (
    LLMProviderError,
    LLMResponse,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


class TestLLMResponse:
    """LLMResponse dataclass."""

    def test_llm_response_fields(self):
        resp = LLMResponse(
            content="hello",
            model="test-model",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001,
        )
        assert resp.content == "hello"
        assert resp.model == "test-model"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5
        assert resp.cost_usd == 0.001
        assert resp.cached is False

    def test_llm_response_cached_flag(self):
        resp = LLMResponse(
            content="x",
            model="m",
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            cached=True,
        )
        assert resp.cached is True


class TestLLMProviderError:
    """LLMProviderError hierarchy."""

    def test_error_message_format(self):
        err = LLMProviderError("test-provider", "something broke")
        assert "[test-provider]" in str(err)
        assert "something broke" in str(err)
        assert err.provider == "test-provider"
        assert err.recoverable is True

    def test_error_non_recoverable(self):
        err = LLMProviderError("p", "fatal", recoverable=False)
        assert err.recoverable is False


class TestProviderUnavailableError:
    """ProviderUnavailableError."""

    def test_unavailable_is_recoverable(self):
        err = ProviderUnavailableError("cli-tool", "not found")
        assert err.recoverable is True
        assert "not found" in str(err)


class TestProviderTimeoutError:
    """ProviderTimeoutError."""

    def test_timeout_message(self):
        err = ProviderTimeoutError("slow-provider", 60)
        assert err.recoverable is True
        assert "60" in str(err)
