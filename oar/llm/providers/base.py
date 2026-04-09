"""Base types for the LLM provider system."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Structured response from an LLM completion call."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cached: bool = False


class LLMProviderError(Exception):
    """Base error for provider failures."""

    def __init__(self, provider: str, message: str, recoverable: bool = True):
        self.provider = provider
        self.recoverable = recoverable
        super().__init__(f"[{provider}] {message}")


class ProviderUnavailableError(LLMProviderError):
    """Raised when a provider binary or service is not available."""

    def __init__(self, provider: str, message: str):
        super().__init__(provider, message, recoverable=True)


class ProviderTimeoutError(LLMProviderError):
    """Raised when a provider call exceeds the timeout."""

    def __init__(self, provider: str, timeout: int):
        super().__init__(provider, f"Timed out after {timeout}s", recoverable=True)
