"""Tests for oar.llm.providers.kiro_cli — KiroCliProvider."""


import pytest

from oar.llm.providers.base import LLMProviderError
from oar.llm.providers.kiro_cli import KiroCliProvider, _strip_ansi
from oar.llm.providers.registry import PROVIDER_CLASSES
from oar.llm.providers.selector import DEFAULT_CHAIN


class TestRegistration:
    """Provider is registered in registry and default chain."""

    def test_kiro_cli_registered(self):
        assert "kiro-cli" in PROVIDER_CLASSES

    def test_kiro_cli_in_default_chain(self):
        assert "kiro-cli" in DEFAULT_CHAIN


class TestProviderProperties:
    """Provider name and binary_name are correct."""

    def test_kiro_cli_name_and_binary(self):
        provider = KiroCliProvider()
        assert provider.name == "kiro-cli"
        assert provider.binary_name == "kiro-cli"


class TestBuildArgs:
    """build_args() produces correct CLI arguments."""

    def test_kiro_cli_build_args_basic(self):
        provider = KiroCliProvider()
        args = provider.build_args("hello")
        assert args[0] == "chat"
        assert "hello" in args
        assert "--no-interactive" in args
        assert "--wrap" in args
        assert "never" in args

    def test_kiro_cli_build_args_with_model(self):
        provider = KiroCliProvider()
        args = provider.build_args("hello", model="claude-haiku-4.5")
        assert "--model" in args
        idx = args.index("--model")
        assert args[idx + 1] == "claude-haiku-4.5"

    def test_kiro_cli_build_args_with_system_prompt(self):
        provider = KiroCliProvider()
        args = provider.build_args(
            "user question",
            system_prompt="you are helpful",
        )
        # System prompt should be prepended to the user prompt.
        combined = "you are helpful\n\nuser question"
        assert combined in args


class TestParseResponse:
    """parse_response() extracts content from TUI-style output."""

    def test_kiro_cli_parse_clean_response(self):
        provider = KiroCliProvider()
        stdout = "\x1b[38;5;141m> \x1b[0mhello world\x1b[0m\n\x1b[38;5;8m\n Credits: 0.01\n\x1b[0m"
        result = provider.parse_response(stdout, "", 0)
        assert result.content == "hello world"

    def test_kiro_cli_parse_multiline_response(self):
        provider = KiroCliProvider()
        stdout = (
            "\x1b[38;5;141m> \x1b[0m"
            "First paragraph.\n\n"
            "Second paragraph with \x1b[1mbold\x1b[0m text.\n"
            "\x1b[38;5;8m\n Credits: 0.03\n\x1b[0m"
        )
        result = provider.parse_response(stdout, "", 0)
        assert "First paragraph." in result.content
        assert "Second paragraph" in result.content
        assert "bold" in result.content

    def test_kiro_cli_parse_error_exit(self):
        provider = KiroCliProvider()
        with pytest.raises(LLMProviderError):
            provider.parse_response("", "some error", 1)

    def test_kiro_cli_parse_empty_response(self):
        provider = KiroCliProvider()
        result = provider.parse_response("", "", 0)
        assert result.content == ""


class TestStripAnsi:
    """_strip_ansi() removes ANSI escape sequences."""

    def test_strip_ansi(self):
        text = "\x1b[38;5;141m> \x1b[0mhello\x1b[1m world\x1b[0m"
        assert _strip_ansi(text) == "> hello world"

    def test_strip_ansi_no_codes(self):
        text = "plain text"
        assert _strip_ansi(text) == "plain text"

    def test_strip_ansi_complex(self):
        text = "\x1b[32m✓\x1b[0m \x1b[1m\x1b[4mSuccess\x1b[0m"
        assert _strip_ansi(text) == "✓ Success"
