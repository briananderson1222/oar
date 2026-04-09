"""Tests for oar.llm.providers.claude_cli — ClaudeCliProvider (mocked subprocess)."""

import json
from unittest.mock import MagicMock, patch

from oar.llm.providers.claude_cli import ClaudeCliProvider


def _make_provider() -> ClaudeCliProvider:
    return ClaudeCliProvider(timeout=30)


class TestClaudeBuildArgs:
    """build_args correctness."""

    def test_claude_build_args_basic(self):
        p = _make_provider()
        args = p.build_args("What is 2+2?")
        assert args[0] == "-p"
        assert "What is 2+2?" in args
        assert "--output-format" in args
        assert "json" in args
        assert "--bare" in args

    def test_claude_build_args_with_system_prompt(self):
        p = _make_provider()
        args = p.build_args("Hello", system_prompt="You are helpful.")
        assert "--system-prompt" in args
        idx = args.index("--system-prompt")
        assert args[idx + 1] == "You are helpful."

    def test_claude_build_args_with_model(self):
        p = _make_provider()
        args = p.build_args("Hi", model="claude-sonnet-4-20250514")
        assert "--model" in args
        idx = args.index("--model")
        assert args[idx + 1] == "sonnet"

    def test_claude_build_args_model_haiku(self):
        p = _make_provider()
        args = p.build_args("Hi", model="claude-haiku-4-20250414")
        idx = args.index("--model")
        assert args[idx + 1] == "haiku"


class TestClaudeParseResponse:
    """parse_response correctness."""

    def test_claude_parse_json_response(self):
        p = _make_provider()
        json_output = json.dumps(
            {
                "content": "4",
                "usage": {"input_tokens": 50, "output_tokens": 10},
            }
        )
        resp = p.parse_response(stdout=json_output, stderr="", returncode=0)
        assert resp.content == "4"
        assert resp.input_tokens == 50
        assert resp.output_tokens == 10
        assert resp.cost_usd == 0.0

    def test_claude_parse_plain_text_fallback(self):
        p = _make_provider()
        resp = p.parse_response(stdout="Just plain text", stderr="", returncode=0)
        assert resp.content == "Just plain text"
        assert resp.input_tokens == 0
        assert resp.output_tokens == 0

    def test_claude_parse_error_returncode(self):
        p = _make_provider()
        try:
            p.parse_response(stdout="", stderr="Error: something", returncode=1)
            assert False, "Should have raised"
        except Exception as exc:
            assert "claude-cli" in str(exc)


class TestClaudeAvailable:
    """available property."""

    def test_claude_available_when_binary_exists(self):
        p = _make_provider()
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            assert p.available is True

    def test_claude_not_available_when_missing(self):
        p = _make_provider()
        with patch("shutil.which", return_value=None):
            assert p.available is False
