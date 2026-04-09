"""Tests for oar.index.orphan_tracker — OrphanTracker."""

from oar.core.link_resolver import LinkResolver
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.index.orphan_tracker import OrphanTracker


class TestWriteOrphansPage:
    """Orphan detection and page generation."""

    def test_write_orphans_page_empty(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        resolver = LinkResolver(vault, ops)
        tracker = OrphanTracker(vault, ops, resolver)
        orphans = tracker.write_orphans_page()
        assert orphans == []

    def test_write_orphans_page_finds_isolated(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        # Create well-connected articles that mutually link.
        ops.write_compiled_article(
            "concepts",
            "hub-a.md",
            {"id": "hub-a", "title": "Hub A", "type": "concept", "status": "draft"},
            "# Hub A\n\nSee [[hub-b]] and [[hub-c]].",
        )
        ops.write_compiled_article(
            "concepts",
            "hub-b.md",
            {
                "id": "hub-b",
                "title": "Hub B",
                "type": "concept",
                "status": "draft",
            },
            "# Hub B\n\nSee [[hub-a]] and [[hub-c]].",
        )
        ops.write_compiled_article(
            "concepts",
            "hub-c.md",
            {
                "id": "hub-c",
                "title": "Hub C",
                "type": "concept",
                "status": "draft",
            },
            "# Hub C\n\nSee [[hub-a]] and [[hub-b]].",
        )
        # Isolated: nothing links to it, and it links nowhere.
        ops.write_compiled_article(
            "concepts",
            "isolated.md",
            {
                "id": "isolated",
                "title": "Isolated",
                "type": "concept",
                "status": "draft",
            },
            "# Isolated\n\nNo outgoing links.",
        )

        resolver = LinkResolver(vault, ops)
        tracker = OrphanTracker(vault, ops, resolver)
        orphans = tracker.write_orphans_page(min_backlinks=2)
        assert "isolated" in orphans
        # Well-connected articles should NOT be in orphans.
        assert "hub-a" not in orphans
        assert "hub-b" not in orphans
        assert "hub-c" not in orphans
        # Verify the page file was created.
        assert (vault.indices_dir / "orphans.md").exists()


class TestWriteStubsPage:
    """Stub detection and page generation."""

    def test_write_stubs_page_finds_short(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        # Short article (fewer than 200 words).
        ops.write_compiled_article(
            "concepts",
            "short.md",
            {
                "id": "short-article",
                "title": "Short",
                "type": "concept",
                "status": "draft",
            },
            "# Short\n\nBrief content.",
        )
        # Long article (>= 200 words).
        long_body = " ".join(["word"] * 250)
        ops.write_compiled_article(
            "concepts",
            "long.md",
            {
                "id": "long-article",
                "title": "Long",
                "type": "concept",
                "status": "draft",
            },
            f"# Long\n\n{long_body}",
        )

        resolver = LinkResolver(vault, ops)
        tracker = OrphanTracker(vault, ops, resolver)
        stubs = tracker.write_stubs_page(min_words=200)
        assert "short-article" in stubs
        assert "long-article" not in stubs
        assert (vault.indices_dir / "stubs.md").exists()


class TestWriteRecentPage:
    """Recently updated page generation."""

    def test_write_recent_page_lists_latest(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        ops.write_compiled_article(
            "concepts",
            "new.md",
            {
                "id": "new-article",
                "title": "New",
                "type": "concept",
                "status": "draft",
                "updated": "2024-06-01T12:00:00Z",
            },
            "# New Article",
        )
        ops.write_compiled_article(
            "concepts",
            "old.md",
            {
                "id": "old-article",
                "title": "Old",
                "type": "concept",
                "status": "draft",
                "updated": "2024-01-01T12:00:00Z",
            },
            "# Old Article",
        )

        resolver = LinkResolver(vault, ops)
        tracker = OrphanTracker(vault, ops, resolver)
        path = tracker.write_recent_page()
        assert path.exists()
        content = path.read_text()
        # Newer article should appear in the page.
        assert "new-article" in content
        assert "old-article" in content
