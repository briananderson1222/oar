"""Vault file operations — high-level read/write helpers for articles."""

from __future__ import annotations

from pathlib import Path

from oar.core.frontmatter import FrontmatterManager
from oar.core.vault import Vault


class VaultOps:
    """Convenience operations that combine Vault path resolution with
    FrontmatterManager read/write."""

    def __init__(self, vault: Vault) -> None:
        self.vault = vault
        self.fm = FrontmatterManager()

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_raw_articles(self) -> list[Path]:
        """List all ``.md`` files in ``01-raw/articles/``, excluding ``_index.md``."""
        articles_dir = self.vault.raw_dir / "articles"
        return self._list_md(articles_dir)

    def list_compiled_articles(self, subdir: str | None = None) -> list[Path]:
        """List all ``.md`` files in ``02-compiled/`` recursively.

        When *subdir* is given, only scan ``02-compiled/{subdir}/``.
        ``_index.md`` files are excluded.
        """
        compiled = self.vault.compiled_dir
        if subdir:
            return self._list_md(compiled / subdir)
        # Scan all subdirectories recursively.
        results: list[Path] = []
        for child in sorted(compiled.iterdir()):
            if child.is_dir():
                results.extend(self._list_md(child))
        return results

    # ------------------------------------------------------------------
    # Read / Write
    # ------------------------------------------------------------------

    def read_article(self, path: Path) -> tuple[dict, str]:
        """Read article, returning ``(metadata, body)``."""
        return self.fm.read(path)

    def write_raw_article(self, filename: str, metadata: dict, body: str) -> Path:
        """Write to ``01-raw/articles/{filename}``."""
        path = self.vault.raw_dir / "articles" / filename
        self.fm.write(path, metadata, body)
        return path

    def write_compiled_article(
        self,
        subdir: str,
        filename: str,
        metadata: dict,
        body: str,
    ) -> Path:
        """Write to ``02-compiled/{subdir}/{filename}``."""
        path = self.vault.compiled_dir / subdir / filename
        self.fm.write(path, metadata, body)
        return path

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def get_article_by_id(self, article_id: str) -> Path | None:
        """Search for an article with matching ``id`` in frontmatter.

        Scans both raw and compiled directories.
        """
        candidates = self.list_raw_articles() + self.list_compiled_articles()
        for path in candidates:
            meta, _ = self.fm.read(path)
            if meta.get("id") == article_id:
                return path
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def compute_word_count(self, body: str) -> int:
        """Count words in text."""
        return len(body.split())

    def compute_read_time(self, word_count: int) -> int:
        """Estimate reading time in minutes (200 wpm, minimum 1)."""
        return max(1, word_count // 200)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _list_md(directory: Path) -> list[Path]:
        """List ``.md`` files in *directory*, excluding ``_index.md``."""
        if not directory.is_dir():
            return []
        return sorted(
            p
            for p in directory.iterdir()
            if p.is_file() and p.suffix == ".md" and p.name != "_index.md"
        )
