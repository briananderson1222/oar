"""Claude CLI provider — wraps `claude` (Claude Code) as an LLM backend."""

from __future__ import annotations

import json
from typing import Any

from oar.llm.providers.base import LLMProviderError, LLMResponse
from oar.llm.providers.cli_base import CliProvider

# Map full model names to CLI short names.
MODEL_MAP: dict[str, str] = {
    "claude-sonnet-4-20250514": "sonnet",
    "claude-3-5-sonnet-20241022": "sonnet",
    "claude-haiku-4-20250414": "haiku",
    "claude-3-5-haiku-20241022": "haiku",
    "claude-opus-4-20250514": "opus",
    "claude-3-opus-20240229": "opus",
}


class ClaudeCliProvider(CliProvider):
    """Use `claude` (Claude Code CLI) as an LLM backend.

    Best CLI provider: supports --output-format json for structured output,
    real token counts via usage reporting, and model selection.
    """

    @property
    def name(self) -> str:
        return "claude-cli"

    @property
    def binary_name(self) -> str:
        return "claude"

    def build_args(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> list[str]:
        args: list[str] = [
            "-p",
            prompt,
            "--output-format",
            "json",
            "--bare",
        ]

        if system_prompt:
            args.extend(["--system-prompt", system_prompt])

        if model:
            short = MODEL_MAP.get(model, model)
            args.extend(["--model", short])

        return args

    def parse_response(
        self,
        stdout: str,
        stderr: str,
        returncode: int,
    ) -> LLMResponse:
        if returncode != 0:
            raise LLMProviderError(
                self.name,
                stderr.strip() or f"Exit code {returncode}",
                recoverable=True,
            )

        # Try JSON parse first (structured output).
        try:
            data = json.loads(stdout)
            content = data.get("content", "")
            usage = data.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            return LLMResponse(
                content=content,
                model=self.name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=0.0,
            )
        except (json.JSONDecodeError, AttributeError):
            pass

        # Fallback: plain text.
        return LLMResponse(
            content=stdout.strip(),
            model=self.name,
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
        )
