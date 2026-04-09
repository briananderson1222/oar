"""Codex CLI provider — wraps OpenAI `codex` as an LLM backend."""

from __future__ import annotations

import json
from typing import Any

from oar.llm.providers.base import LLMProviderError, LLMResponse
from oar.llm.providers.cli_base import CliProvider


class CodexCliProvider(CliProvider):
    """Use OpenAI `codex` CLI as an LLM backend.

    Uses `codex exec` in non-interactive mode with --json for JSONL output.
    Requires --skip-git-repo-check when not in a git repository.
    """

    @property
    def name(self) -> str:
        return "codex-cli"

    @property
    def binary_name(self) -> str:
        return "codex"

    def build_args(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> list[str]:
        args: list[str] = ["exec", prompt, "--skip-git-repo-check", "--json"]

        # System instructions via -c persistent_instructions="...".
        if system_prompt:
            args.extend(
                [
                    "-c",
                    f'persistent_instructions="{system_prompt}"',
                ]
            )

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

        # Parse JSONL: look for item.completed events with agent_message text.
        try:
            for line in stdout.strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                if data.get("type") == "item.completed":
                    item = data.get("item", {})
                    if item.get("type") == "agent_message":
                        text = item.get("text", "")
                        if text:
                            return LLMResponse(
                                content=text,
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
