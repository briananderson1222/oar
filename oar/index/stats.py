"""Vault statistics calculator — compute counts and word totals."""

from __future__ import annotations

from dataclasses import dataclass, field

from oar.core.state import StateManager
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps


@dataclass
class VaultStats:
    """Aggregate statistics about the vault."""

    raw_articles: int = 0
    compiled_articles: int = 0
    mocs: int = 0
    tag_pages: int = 0
    total_words: int = 0
    backlinks: int = 0
    orphans: int = 0
    stubs: int = 0


class StatsCalculator:
    """Compute vault statistics by scanning files."""

    def __init__(self, vault: Vault, ops: VaultOps, state: StateManager) -> None:
        self.vault = vault
        self.ops = ops
        self.state = state

    def calculate(self) -> VaultStats:
        """Compute vault statistics by scanning files."""
        raw = len(self.ops.list_raw_articles())
        compiled = len(self.ops.list_compiled_articles())

        # Count words across compiled articles.
        total_words = 0
        for path in self.ops.list_compiled_articles():
            _, body = self.ops.read_article(path)
            total_words += self.ops.compute_word_count(body)

        # Count MOCs and tag pages from index directories.
        moc_dir = self.vault.indices_dir / "moc"
        tag_dir = self.vault.indices_dir / "tags"
        mocs = len(self._list_md(moc_dir))
        tag_pages = len(self._list_md(tag_dir))

        return VaultStats(
            raw_articles=raw,
            compiled_articles=compiled,
            mocs=mocs,
            tag_pages=tag_pages,
            total_words=total_words,
        )

    @staticmethod
    def _list_md(directory) -> list:
        """List .md files in directory, excluding _index.md."""
        if not directory.exists():
            return []
        return [
            p
            for p in directory.iterdir()
            if p.is_file() and p.suffix == ".md" and p.name != "_index.md"
        ]
