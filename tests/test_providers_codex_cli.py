"""Tests for oar.llm.providers.codex_cli — CodexCliProvider (mocked subprocess)."""

import json
from unittest.mock import MagicMock, patch

from oar.llm.providers.codex_cli import CodexCliProvider


def _make_provider() -> CodexCliProvider:
    return CodexCliProvider(timeout=30)


class TestCodexBuildArgs:
    """build_args correctness."""

    def test_codex_build_args_basic(self):
        p = _make_provider()
        args = p.build_args("Explain transformers.")
        assert args[0] == "exec"
        assert "Explain transformers." in args
        assert "--skip-git-repo-check" in args
        assert "--json" in args

    def test_codex_build_args_with_system_instruction(self):
        p = _make_provider()
        args = p.build_args("Hello", system_prompt="Be brief.")
        assert "-c" in args
        idx = args.index("-c")
        config_val = args[idx + 1]
        assert "persistent_instructions" in config_val
        assert "Be brief." in config_val


class TestCodexParseResponse:
    """parse_response correctness."""

    def test_codex_parse_jsonl_response(self):
        p = _make_provider()
        event = {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": "Transformers are neural networks.",
            },
        }
        stdout = json.dumps(event)
        resp = p.parse_response(stdout=stdout, stderr="", returncode=0)
        assert "Transformers are neural networks." in resp.content

    def test_codex_parse_error_returncode(self):
        p = _make_provider()
        try:
            p.parse_response(stdout="", stderr="error: auth failed", returncode=1)
            assert False, "Should have raised"
        except Exception as exc:
            assert "codex-cli" in str(exc)

    def test_codex_parse_plain_text_fallback(self):
        p = _make_provider()
        resp = p.parse_response(stdout="plain text fallback", stderr="", returncode=0)
        assert resp.content == "plain text fallback"
