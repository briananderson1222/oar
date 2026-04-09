"""CLI provider base class — shared subprocess logic for CLI-based LLM tools."""

from __future__ import annotations

import json
import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import Any

from oar.llm.providers.base import LLMProviderError, LLMResponse, ProviderTimeoutError


class CliProvider(ABC):
    """Abstract base class for CLI-based LLM providers.

    Subclasses must implement:
        - binary_name: str property
        - build_args(): list[str]
        - parse_response(): LLMResponse
    """

    def __init__(self, timeout: int = 120) -> None:
        self.timeout = timeout

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'claude-cli')."""

    @property
    @abstractmethod
    def binary_name(self) -> str:
        """Binary name for shutil.which() lookup (e.g. 'claude')."""

    @abstractmethod
    def build_args(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """Build the command-line arguments for the CLI tool."""

    @abstractmethod
    def parse_response(
        self,
        stdout: str,
        stderr: str,
        returncode: int,
    ) -> LLMResponse:
        """Parse raw subprocess output into an LLMResponse."""

    @property
    def available(self) -> bool:
        """True if the CLI binary is found on PATH."""
        return shutil.which(self.binary_name) is not None

    def health_check(self) -> bool:
        """Run the binary with --version to verify it works."""
        if not self.available:
            return False
        try:
            result = subprocess.run(
                [self.binary_name, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    def complete(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send completion request via CLI subprocess."""
        prompt = self._format_messages_as_prompt(messages)
        system_prompt = self._extract_system_prompt(messages)

        args = self.build_args(
            prompt,
            system_prompt=system_prompt,
            model=model,
            **kwargs,
        )

        try:
            result = subprocess.run(
                [self.binary_name, *args],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderTimeoutError(self.name, self.timeout) from exc
        except OSError as exc:
            raise LLMProviderError(self.name, str(exc), recoverable=True) from exc

        return self.parse_response(
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
        )

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate: ~4 chars per token."""
        return len(text) // 4

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_messages_as_prompt(messages: list[dict]) -> str:
        """Convert a messages array to a single prompt string."""
        parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                # System messages are handled separately when possible.
                parts.append(f"[System]: {content}")
            elif role == "assistant":
                parts.append(f"[Assistant]: {content}")
            else:
                parts.append(content)
        return "\n\n".join(parts)

    @staticmethod
    def _extract_system_prompt(messages: list[dict]) -> str | None:
        """Extract the first system message from the messages array."""
        for msg in messages:
            if msg.get("role") == "system":
                return msg.get("content")
        return None
