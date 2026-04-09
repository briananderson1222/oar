"""OpenCode CLI provider — wraps `opencode` as an LLM backend."""

from __future__ import annotations

import json
from typing import Any

from oar.llm.providers.base import LLMProviderError, LLMResponse
from oar.llm.providers.cli_base import CliProvider


class OpenCodeCliProvider(CliProvider):
    """Use `opencode` CLI as an LLM backend.

    Caveats:
        - No --system-prompt flag; system prompt is prepended to user prompt.
        - Always exits 0, even on errors — must check stderr.
    """

    @property
    def name(self) -> str:
        return "opencode-cli"

    @property
    def binary_name(self) -> str:
        return "opencode"

    def build_args(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> list[str]:
        # Prepend system prompt to the user prompt since opencode has no
        # dedicated flag for it.
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        args: list[str] = ["run", full_prompt, "--format", "json"]

        if model:
            args.extend(["-m", model])

        return args

    def parse_response(
        self,
        stdout: str,
        stderr: str,
        returncode: int,
    ) -> LLMResponse:
        # opencode exits 0 even on errors — check stderr for error strings.
        if stderr and _is_error_stderr(stderr):
            raise LLMProviderError(
                self.name,
                stderr.strip(),
                recoverable=True,
            )

        if returncode != 0:
            raise LLMProviderError(
                self.name,
                stderr.strip() or f"Exit code {returncode}",
                recoverable=True,
            )

        # Try JSONL parse: look for {"type":"text","part":{"text":"..."}}.
        try:
            text_parts: list[str] = []
            for line in stdout.strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                if data.get("type") == "text":
                    part = data.get("part", {})
                    if "text" in part:
                        text_parts.append(part["text"])
            if text_parts:
                return LLMResponse(
                    content="".join(text_parts),
                    model=self.name,
                    input_tokens=0,
                    output_tokens=0,
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


def _is_error_stderr(stderr: str) -> bool:
    """Heuristic: check if stderr looks like an error message."""
    lower = stderr.lower()
    return any(
        marker in lower
        for marker in ("error:", "fatal:", "panic:", "not found", "failed")
    )
