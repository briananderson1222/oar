"""Kiro CLI provider — wraps `kiro-cli chat` as an LLM backend."""

from __future__ import annotations

import re
from typing import Any

from oar.llm.providers.base import LLMProviderError, LLMResponse
from oar.llm.providers.cli_base import CliProvider


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)


class KiroCliProvider(CliProvider):
    """Use `kiro-cli chat` as an LLM backend.

    Uses --no-interactive for non-interactive mode. Output is TUI-style
    with ANSI codes; we strip them and extract the text content.
    """

    @property
    def name(self) -> str:
        return "kiro-cli"

    @property
    def binary_name(self) -> str:
        return "kiro-cli"

    def build_args(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> list[str]:
        # Prepend system prompt since kiro-cli chat doesn't have a dedicated flag.
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        args: list[str] = [
            "chat",
            full_prompt,
            "--no-interactive",
            "--wrap",
            "never",
        ]

        if model:
            args.extend(["--model", model])

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
                _strip_ansi(stderr).strip() or f"Exit code {returncode}",
                recoverable=True,
            )

        # Strip ANSI codes.
        clean = _strip_ansi(stdout)

        # Extract text between '> ' prompt and 'Credits:' footer.
        # The output looks like: ...> content\n ... Credits: ...
        match = re.search(r">\s+(.*?)(?:Credits:|$)", clean, re.DOTALL)
        if match:
            content = match.group(1).strip()
        else:
            # Fallback: use everything, strip common noise.
            content = clean.strip()
            # Remove trailing credits/times line.
            content = re.sub(r"\n.*Credits:.*$", "", content, flags=re.DOTALL)
            content = content.strip()

        if not content:
            content = _strip_ansi(stdout).strip()

        return LLMResponse(
            content=content,
            model=self.name,
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
        )
