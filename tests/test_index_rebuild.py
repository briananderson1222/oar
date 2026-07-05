"""Tests for true index rebuild — stale tag/MOC pages are pruned (oar#3.1)."""

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.index.moc_builder import MocBuilder
from oar.index.tag_builder import TagBuilder


def _write(ops, filename, article_id, tags, domain):
    ops.write_compiled_article(
        "concepts",
        filename,
        {
            "id": article_id,
            "title": article_id.title(),
            "type": "concept",
            "status": "draft",
            "tags": tags,
            "domain": domain,
        },
        f"Body for {article_id}.",
    )


class TestTrueRebuild:
    def test_stale_tag_and_moc_removed_on_rebuild(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        tags_dir = tmp_vault / "03-indices" / "tags"
        moc_dir = tmp_vault / "03-indices" / "moc"

        # Two articles; one carries a unique tag + unique domain.
        _write(ops, "keep.md", "keep", ["common"], ["shared-domain"])
        _write(ops, "unique.md", "unique", ["zzz-unique-tag"], ["zzz-unique-domain"])

        TagBuilder(vault, ops).auto_generate_tags(prune=True)
        MocBuilder(vault, ops).auto_generate_mocs(prune=True)

        assert (tags_dir / "tag-zzz-unique-tag.md").exists()
        assert (moc_dir / "moc-zzz-unique-domain.md").exists()

        # Delete the unique article and rebuild with pruning.
        (tmp_vault / "02-compiled" / "concepts" / "unique.md").unlink()
        TagBuilder(vault, ops).auto_generate_tags(prune=True)
        MocBuilder(vault, ops).auto_generate_mocs(prune=True)

        # Its tag page and MOC are gone; the surviving article's pages remain.
        assert not (tags_dir / "tag-zzz-unique-tag.md").exists()
        assert not (moc_dir / "moc-zzz-unique-domain.md").exists()
        assert (tags_dir / "tag-common.md").exists()
        assert (moc_dir / "moc-shared-domain.md").exists()

    def test_prune_only_touches_generated_patterns(self, tmp_vault):
        """A user file that is not a tag-*/moc-* page is never deleted."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        tags_dir = tmp_vault / "03-indices" / "tags"
        tags_dir.mkdir(parents=True, exist_ok=True)
        user_file = tags_dir / "my-notes.md"
        user_file.write_text("# my notes\n")

        _write(ops, "keep.md", "keep", ["common"], ["shared-domain"])
        TagBuilder(vault, ops).auto_generate_tags(prune=True)

        assert user_file.exists()

    def test_build_indices_tool_prunes(self, tmp_vault, monkeypatch):
        """The MCP build_indices tool performs a true rebuild."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        from oar.mcp_tools import tool_build_indices

        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        _write(ops, "keep.md", "keep", ["common"], ["shared-domain"])
        _write(ops, "unique.md", "unique", ["zzz-unique-tag"], ["zzz-unique-domain"])
        tool_build_indices()
        assert (tmp_vault / "03-indices" / "tags" / "tag-zzz-unique-tag.md").exists()

        (tmp_vault / "02-compiled" / "concepts" / "unique.md").unlink()
        tool_build_indices()
        assert not (tmp_vault / "03-indices" / "tags" / "tag-zzz-unique-tag.md").exists()
        assert not (tmp_vault / "03-indices" / "moc" / "moc-zzz-unique-domain.md").exists()
