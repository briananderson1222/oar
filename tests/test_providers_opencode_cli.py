"""Tests for oar.llm.providers.opencode_cli — OpenCodeCliProvider (mocked subprocess)."""

import json
from unittest.mock import MagicMock, patch

from oar.llm.providers.opencode_cli import OpenCodeCliProvider


def _make_provider() -> OpenCodeCliProvider:
    return OpenCodeCliProvider(timeout=30)


class TestOpenCodeBuildArgs:
    """build_args correctness."""

    def test_opencode_build_args_basic(self):
        p = _make_provider()
        args = p.build_args("What is OAR?")
        assert args[0] == "run"
        assert "What is OAR?" in args
        assert "--format" in args
        assert "json" in args

    def test_opencode_build_args_prepends_system_prompt(self):
        p = _make_provider()
        args = p.build_args("Hello", system_prompt="Be concise.")
        # System prompt should be prepended to the prompt text.
        prompt_idx = args.index("run") + 1
        combined = args[prompt_idx]
        assert "Be concise." in combined
        assert "Hello" in combined

    def test_opencode_build_args_with_model(self):
        p = _make_provider()
        args = p.build_args("Hi", model="anthropic/claude-sonnet-4-20250514")
        assert "-m" in args
        idx = args.index("-m")
        assert args[idx + 1] == "anthropic/claude-sonnet-4-20250514"


class TestOpenCodeParseResponse:
    """parse_response correctness."""

    def test_opencode_parse_jsonl_response(self):
        p = _make_provider()
        lines = [
            json.dumps({"type": "text", "part": {"text": "Hello "}}),
            json.dumps({"type": "text", "part": {"text": "World"}}),
        ]
        stdout = "\n".join(lines)
        resp = p.parse_response(stdout=stdout, stderr="", returncode=0)
        assert "Hello" in resp.content
        assert "World" in resp.content

    def test_opencode_stderr_error_detection(self):
        """opencode exits 0 even on errors — must check stderr."""
        p = _make_provider()
        try:
            p.parse_response(stdout="", stderr="Error: model not found", returncode=0)
            assert False, "Should have raised"
        except Exception as exc:
            assert "opencode-cli" in str(exc)

    def test_opencode_parse_plain_text_fallback(self):
        p = _make_provider()
        resp = p.parse_response(stdout="plain response", stderr="", returncode=0)
        assert resp.content == "plain response"
