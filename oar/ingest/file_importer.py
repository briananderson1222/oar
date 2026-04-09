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
        content = source.read_text()
        source_type = self.detect_type(source)

        # Use filename (without extension) as a fallback title.
        title = source.stem.replace("-", " ").replace("_", " ").strip()
        if not title:
            title = source.name

        metadata = generate_raw_metadata(
            title=title,
            source_type=source_type,
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
