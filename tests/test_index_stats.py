"""Tests for oar.index.stats — StatsCalculator and VaultStats."""

from oar.core.state import StateManager
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.index.stats import StatsCalculator, VaultStats


class TestStatsEmptyVault:
    """Statistics on an empty vault."""

    def test_stats_empty_vault(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        state = StateManager(vault.oar_dir)
        calc = StatsCalculator(vault, ops, state)
        stats = calc.calculate()
        assert isinstance(stats, VaultStats)
        assert stats.raw_articles == 0
        assert stats.compiled_articles == 0
        assert stats.mocs == 0
        assert stats.tag_pages == 0
        assert stats.total_words == 0


class TestStatsWithArticles:
    """Statistics after adding articles."""

    def test_stats_with_articles(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        state = StateManager(vault.oar_dir)

        # Write raw and compiled articles.
        ops.write_raw_article(
            "raw-1.md",
            {"id": "raw-1", "title": "Raw One", "source_type": "article"},
            "Raw body one.",
        )
        ops.write_compiled_article(
            "concepts",
            "concept-1.md",
            {
                "id": "concept-1",
                "title": "Concept One",
                "type": "concept",
                "status": "draft",
            },
            "Concept body with some words to count.",
        )
        ops.write_compiled_article(
            "concepts",
            "concept-2.md",
            {
                "id": "concept-2",
                "title": "Concept Two",
                "type": "concept",
                "status": "draft",
            },
            "Another concept body.",
        )

        calc = StatsCalculator(vault, ops, state)
        stats = calc.calculate()
        assert stats.raw_articles == 1
        assert stats.compiled_articles == 2

    def test_stats_counts_words(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        state = StateManager(vault.oar_dir)

        body_a = "one two three four five"
        body_b = "six seven eight"
        ops.write_compiled_article(
            "concepts",
            "a.md",
            {"id": "a", "title": "A", "type": "concept", "status": "draft"},
            body_a,
        )
        ops.write_compiled_article(
            "concepts",
            "b.md",
            {"id": "b", "title": "B", "type": "concept", "status": "draft"},
            body_b,
        )

        calc = StatsCalculator(vault, ops, state)
        stats = calc.calculate()
        assert stats.total_words == len(body_a.split()) + len(body_b.split())
