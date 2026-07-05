"""File importing — import local files and directories into the vault."""

from __future__ import annotations

from pathlib import Path

from oar.core.frontmatter import FrontmatterManager
from oar.core.hashing import content_hash_string
from oar.core.slug import slugify
from oar.core.state import StateManager
from oar.core.vault import Vault
from oar.ingest.metadata import generate_raw_metadata


class FileImporter:
    """Import local files into the vault's raw directory."""

    def __init__(self) -> None:
        self.fm = FrontmatterManager()

    def import_file(self, source: Path, vault: Vault) -> Path:
        """Import a local file into the vault. Returns path to created raw article."""
        return self.import_file_with_metadata(source, vault)

    def import_file_with_metadata(
        self,
        source: Path,
        vault: Vault,
        *,
        source_type: str | None = None,
        title: str | None = None,
        source_url: str = "",
        author: str = "",
        published: str = "",
    ) -> Path:
        """Import a local file with optional metadata overrides."""
        content = source.read_text()
        resolved_source_type = source_type or self.detect_type(source)

        # Use filename (without extension) as a fallback title.
        resolved_title = title or source.stem.replace("-", " ").replace("_", " ").strip()
        if not resolved_title:
            resolved_title = source.name

        metadata = generate_raw_metadata(
            title=resolved_title,
            source_url=source_url,
            source_type=resolved_source_type,
            author=author,
            published=published,
            content=content,
        )

        # Build filename: {id}.md
        filename = f"{metadata['id']}.md"

        # Write via VaultOps-like pattern.
        articles_dir = vault.raw_dir / "articles"
        dest = articles_dir / filename
        self.fm.write(dest, metadata, content)

        # Register in state.
        state_mgr = StateManager(vault.oar_dir)
        content_hash = content_hash_string(content)
        rel_path = f"01-raw/articles/{filename}"
        state_mgr.register_article(metadata["id"], rel_path, content_hash)

        return dest

    def import_directory(self, source_dir: Path, vault: Vault) -> list[Path]:
        """Import all .md and .txt files from a directory."""
        results: list[Path] = []
        for entry in sorted(source_dir.iterdir()):
            # Skip hidden files and _index.md.
            if entry.name.startswith("."):
                continue
            if entry.name == "_index.md":
                continue
            # Only process files (skip subdirectories).
            if not entry.is_file():
                continue
            if entry.suffix not in (".md", ".txt"):
                continue
            results.append(self.import_file(entry, vault))
        return results

    def detect_type(self, path: Path) -> str:
        """Detect source type from file extension."""
        ext = path.suffix.lower()
        if ext == ".pdf":
            return "paper"
        if ext in (".md", ".txt"):
            return "article"
        return "file"
