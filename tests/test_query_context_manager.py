"""Tests for oar.query.context_manager — ContextManager and ContextWindow."""

import pytest

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.core.link_resolver import LinkResolver
from oar.query.context_manager import ContextWindow, ContextManager


# ---------------------------------------------------------------------------
# Vault population helper
# ---------------------------------------------------------------------------


def _populate_vault_for_context(tmp_vault):
    """Create a vault with compiled articles, MOCs, and master index."""
    ops = VaultOps(Vault(tmp_vault))

    # Create compiled articles
    ops.write_compiled_article(
        "concepts",
        "attention-mechanism.md",
        {
            "id": "attention-mechanism",
            "title": "Attention Mechanism",
            "tags": ["attention", "transformer"],
        },
        "# Attention Mechanism\n\n"
        "> **TL;DR**: Attention allows models to focus on relevant input.\n\n"
        "## Overview\n\n"
        "Attention is a mechanism in neural networks.\n\n"
        "## Key Ideas\n\n"
        "- Self-attention\n"
        "- Multi-head attention\n",
    )
    ops.write_compiled_article(
        "concepts",
        "transformer-architecture.md",
        {
            "id": "transformer-architecture",
            "title": "Transformer Architecture",
            "tags": ["transformer", "architecture"],
        },
        "# Transformer\n\n"
        "> **TL;DR**: The Transformer is an architecture based on attention.\n\n"
        "## Overview\n\n"
        "Transformers revolutionized NLP.\n\n"
        "See [[attention-mechanism]] for the core component.\n",
    )

    # Create MOC
    moc_dir = tmp_vault / "03-indices" / "moc"
    moc_dir.mkdir(parents=True, exist_ok=True)
    (moc_dir / "moc-llm-foundations.md").write_text(
        "---\n"
        'id: "moc-llm-foundations"\n'
        "title: LLM Foundations\n"
        "type: moc\n"
        "---\n\n"
        "# LLM Foundations\n\n"
        "- [[attention-mechanism]]\n"
        "- [[transformer-architecture]]\n"
    )

    # Create master index
    (tmp_vault / "03-indices" / "_master-index.md").write_text(
        "---\n"
        'id: "_master-index"\n'
        "type: master-index\n"
        "---\n\n"
        "# Master Index\n\n"
        "| MOC | Articles | Summary |\n"
        "|-----|----------|----------|\n"
        "| [[moc-llm-foundations]] | 2 | Core LLM concepts |\n"
    )

    return ops


# ===================================================================
# ContextWindow unit tests
# ===================================================================


class TestContextWindowAddSection:
    """ContextWindow.add_section basics."""

    def test_context_window_add_section(self):
        ctx = ContextWindow(max_tokens=1000)
        added = ctx.add_section("test-source", "Hello world")
        assert added is True
        assert len(ctx.sections) == 1
        assert ctx.sections[0]["source"] == "test-source"
        assert ctx.sections[0]["content"] == "Hello world"

    def test_context_window_tokens_tracked(self):
        ctx = ContextWindow(max_tokens=1000)
        ctx.add_section("src", "A" * 40)  # 40 chars = 10 tokens
        assert ctx.total_tokens == 10


class TestContextWindowMaxTokens:
    """ContextWindow enforces token budget."""

    def test_context_window_respects_max_tokens(self):
        ctx = ContextWindow(max_tokens=10)
        # First section takes all budget
        assert ctx.add_section("big", "A" * 40) is True  # 10 tokens
        # Second section won't fit
        assert ctx.add_section("overflow", "B" * 40) is False
        assert len(ctx.sections) == 1


class TestContextWindowTruncated:
    """ContextWindow.add_section_truncated."""

    def test_context_window_add_section_truncated(self):
        ctx = ContextWindow(max_tokens=10)
        # Fill most of the budget
        ctx.add_section("filler", "A" * 20)  # 5 tokens
        # This should be truncated to fit remaining 5 tokens
        added = ctx.add_section_truncated("long", "B" * 1000)
        assert added is True
        assert ctx.total_tokens <= 10
        assert "[TRUNCATED]" in ctx.sections[-1]["content"]

    def test_context_window_add_section_truncated_no_space(self):
        ctx = ContextWindow(max_tokens=5)
        ctx.add_section("filler", "A" * 20)  # 5 tokens
        # No remaining budget at all
        assert ctx.add_section_truncated("extra", "x") is False


class TestContextWindowRender:
    """ContextWindow.render output."""

    def test_context_window_render(self):
        ctx = ContextWindow()
        ctx.add_section("source-a", "Content A")
        ctx.add_section("source-b", "Content B")
        rendered = ctx.render()
        assert "--- source-a ---" in rendered
        assert "--- source-b ---" in rendered
        assert "Content A" in rendered
        assert "Content B" in rendered


class TestContextWindowUtilization:
    """ContextWindow.utilization property."""

    def test_context_window_utilization(self):
        ctx = ContextWindow(max_tokens=100)
        assert ctx.utilization == 0.0
        ctx.add_section("src", "A" * 40)  # 10 tokens
        assert ctx.utilization == pytest.approx(0.1)


class TestContextWindowRemainingTokens:
    """ContextWindow.remaining_tokens property."""

    def test_context_window_remaining_tokens(self):
        ctx = ContextWindow(max_tokens=100)
        assert ctx.remaining_tokens == 100
        ctx.add_section("src", "A" * 40)  # 10 tokens
        assert ctx.remaining_tokens == 90


# ===================================================================
# ContextManager integration tests
# ===================================================================


class TestBuildContextMasterIndex:
    """Master index loading."""

    def test_build_context_includes_master_index(self, tmp_vault):
        _populate_vault_for_context(tmp_vault)
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        resolver = LinkResolver(vault, ops)
        mgr = ContextManager(vault, ops, resolver)
        ctx = mgr.build_context("attention mechanism")
        rendered = ctx.render()
        assert "Master Index" in rendered


class TestBuildContextMOCs:
    """MOC identification and loading."""

    def test_build_context_includes_relevant_mocs(self, tmp_vault):
        _populate_vault_for_context(tmp_vault)
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        resolver = LinkResolver(vault, ops)
        mgr = ContextManager(vault, ops, resolver)
        ctx = mgr.build_context("LLM foundations attention")
        rendered = ctx.render()
        assert "LLM Foundations" in rendered

    def test_find_relevant_mocs_keyword_match(self, tmp_vault):
        _populate_vault_for_context(tmp_vault)
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        resolver = LinkResolver(vault, ops)
        mgr = ContextManager(vault, ops, resolver)
        mocs = mgr._find_relevant_mocs("LLM foundations")
        assert "moc-llm-foundations" in mocs


class TestBuildContextArticles:
    """Article loading from context builder."""

    def test_build_context_includes_articles(self, tmp_vault):
        _populate_vault_for_context(tmp_vault)
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        resolver = LinkResolver(vault, ops)
        mgr = ContextManager(vault, ops, resolver)
        ctx = mgr.build_context("attention mechanism")
        rendered = ctx.render()
        # At least one of the articles should be present
        assert "Attention" in rendered or "Transformer" in rendered


class TestBuildContextBudget:
    """Token budget enforcement."""

    def test_build_context_respects_token_budget(self, tmp_vault):
        _populate_vault_for_context(tmp_vault)
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        resolver = LinkResolver(vault, ops)
        mgr = ContextManager(vault, ops, resolver)
        ctx = mgr.build_context("attention mechanism", max_tokens=200)
        assert ctx.total_tokens <= 200


class TestBuildContextEmptyVault:
    """Context building with no content."""

    def test_build_context_empty_vault(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        resolver = LinkResolver(vault, ops)
        mgr = ContextManager(vault, ops, resolver)
        ctx = mgr.build_context("anything")
        # Should return a context window (possibly empty or just master index)
        assert isinstance(ctx, ContextWindow)
        assert ctx.total_tokens >= 0


class TestBuildContextForArticles:
    """Targeted article loading."""

    def test_build_context_for_articles(self, tmp_vault):
        _populate_vault_for_context(tmp_vault)
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        resolver = LinkResolver(vault, ops)
        mgr = ContextManager(vault, ops, resolver)
        ctx = mgr.build_context_for_articles(["attention-mechanism"])
        rendered = ctx.render()
        assert "Attention" in rendered


class TestGetArticleSummary:
    """Article summary extraction."""

    def test_get_article_summary_returns_tldr(self, tmp_vault):
        _populate_vault_for_context(tmp_vault)
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        resolver = LinkResolver(vault, ops)
        mgr = ContextManager(vault, ops, resolver)
        summary = mgr.get_article_summary("attention-mechanism")
        assert summary is not None
        # Should include TL;DR but stop before ##
        assert "TL;DR" in summary
        assert "## Overview" not in summary

    def test_get_article_summary_missing_article(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        resolver = LinkResolver(vault, ops)
        mgr = ContextManager(vault, ops, resolver)
        assert mgr.get_article_summary("nonexistent") is None


class TestScoreCandidates:
    """Candidate scoring by relevance."""

    def test_score_candidates_title_match_boosted(self, tmp_vault):
        _populate_vault_for_context(tmp_vault)
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        resolver = LinkResolver(vault, ops)
        mgr = ContextManager(vault, ops, resolver)
        # Query matches the "attention-mechanism" title directly
        candidates = [("attention-mechanism", 1), ("transformer-architecture", 1)]
        scored = mgr._score_candidates("attention mechanism", candidates)
        ids = [aid for aid, _ in scored]
        # attention-mechanism should score higher due to title match
        assert ids.index("attention-mechanism") < ids.index("transformer-architecture")
