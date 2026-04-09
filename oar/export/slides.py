"""Marp slide generation — convert compiled articles into slide decks."""

from __future__ import annotations

import re
from pathlib import Path

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps

MARPE_HEADER = """\
---
marp: true
theme: default
paginate: true
---

"""


class SlideExporter:
    """Generate Marp-format slide decks from wiki content."""

    def __init__(self, vault: Vault, ops: VaultOps) -> None:
        self.vault = vault
        self.ops = ops

    def export_article_as_slides(
        self, article_id: str, output_path: Path | None = None
    ) -> Path:
        """Convert a compiled article into a Marp slide deck.

        Strategy:
        - Title → title slide
        - TL;DR → overview slide
        - Each ## section → one slide
        - References → final slide
        """
        path = self.ops.get_article_by_id(article_id)
        if not path:
            raise ValueError(f"Article '{article_id}' not found")

        fm, body = self.ops.read_article(path)
        title = fm.get("title", article_id)

        slides: list[str] = []
        tags = fm.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        slides.append(f"# {title}\n\n{tags}")

        # Split by ## headings.
        sections = re.split(r"^## ", body, flags=re.MULTILINE)
        for section in sections:
            if section.strip():
                slides.append(f"## {section.strip()}")

        content = MARPE_HEADER + "\n\n---\n\n".join(slides)

        if output_path is None:
            slides_dir = self.vault.path / "04-outputs" / "slides"
            slides_dir.mkdir(parents=True, exist_ok=True)
            output_path = slides_dir / f"{article_id}-slides.md"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
        return output_path

    def export_moc_as_slides(
        self, moc_id: str, output_path: Path | None = None
    ) -> Path:
        """Convert a MOC into a slide deck overview."""
        moc_dir = self.vault.indices_dir / "moc"
        moc_path: Path | None = None
        if moc_dir.is_dir():
            for candidate in moc_dir.iterdir():
                if candidate.is_file() and candidate.suffix == ".md":
                    fm, _ = self.ops.read_article(candidate)
                    if fm.get("id") == moc_id:
                        moc_path = candidate
                        break

        if moc_path is None:
            raise ValueError(f"MOC '{moc_id}' not found")

        fm, body = self.ops.read_article(moc_path)
        title = fm.get("title", moc_id)

        slides: list[str] = [f"# {title}\n\nMOC Overview"]

        # Each article link becomes its own slide stub.
        for line in body.splitlines():
            m = re.match(r"^- \[\[([^\]]+)\]\]", line)
            if m:
                slides.append(f"## {m.group(1)}\n\n(Article summary placeholder)")

        content = MARPE_HEADER + "\n\n---\n\n".join(slides)

        if output_path is None:
            slides_dir = self.vault.path / "04-outputs" / "slides"
            slides_dir.mkdir(parents=True, exist_ok=True)
            output_path = slides_dir / f"{moc_id}-slides.md"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
        return output_path
