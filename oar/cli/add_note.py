"""oar add-note — Add a structured wiki note (no LLM, structure only)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from oar.cli._shared import find_vault_path
from oar.core.frontmatter import FrontmatterManager
from oar.core.slug import slugify
from oar.core.state import StateManager
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps

console = Console()

VALID_TYPES = ("concept", "entity", "method", "comparison", "tutorial", "timeline")


def add_note_cmd(
    title: str = typer.Option(..., "--title", "-t", help="Note title (required)."),
    type: str = typer.Option(
        "concept",
        "--type",
        "-T",
        help=f"Article type: {', '.join(VALID_TYPES)}.",
    ),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated tags."),
    related: Optional[str] = typer.Option(
        None,
        "--related",
        help="Comma-separated related article IDs (as [[wikilinks]]).",
    ),
    status: str = typer.Option(
        "draft", "--status", "-s", help="Article status: stub, draft, mature, review."
    ),
    body: Optional[str] = typer.Option(None, "--body", "-b", help="Note body content."),
    file: Optional[str] = typer.Option(
        None, "--file", "-f", help="Read body from file path."
    ),
    edit: bool = typer.Option(
        False, "--edit", "-e", help="Open in $EDITOR after creating."
    ),
    confidence: float = typer.Option(
        0.9, "--confidence", "-c", help="Confidence score 0.0-1.0."
    ),
) -> None:
    """Add a structured wiki note to the vault. No LLM — you write the content, this handles the structure."""
    vault_path = find_vault_path()
    if vault_path is None:
        console.print(
            "[bold red]Error:[/bold red] No OAR vault found. Run `oar init` first."
        )
        raise typer.Exit(code=1)

    # Validate type.
    if type not in VALID_TYPES:
        console.print(
            f"[bold red]Error:[/bold red] Invalid type '{type}'. Must be one of: {', '.join(VALID_TYPES)}"
        )
        raise typer.Exit(code=1)

    # Get body content.
    note_body = ""
    if file:
        file_path = Path(file)
        if not file_path.exists():
            console.print(f"[bold red]Error:[/bold red] File not found: {file}")
            raise typer.Exit(code=1)
        note_body = file_path.read_text()
    elif body:
        note_body = body
    else:
        # Open editor if no body provided.
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", delete=False, prefix="oar-note-"
        ) as tf:
            tf.write(f"# {title}\n\n")
            tmp_path = tf.name
        editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vi"))
        subprocess.run([editor, tmp_path])
        note_body = Path(tmp_path).read_text()
        Path(tmp_path).unlink()

    # Generate ID and slug.
    slug = slugify(title)
    article_id = slug
    filename = f"{slug}.md"

    # Parse tags.
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    # Parse related articles.
    related_list = []
    if related:
        for r in related.split(","):
            r = r.strip()
            if r and not r.startswith("[["):
                r = f"[[{r}]]"
            related_list.append(r)

    # Compute word count and read time.
    word_count = len(note_body.split())
    read_time = max(1, word_count // 200)

    # Build frontmatter.
    now = datetime.now(timezone.utc).isoformat()
    metadata = {
        "id": article_id,
        "title": title,
        "aliases": [],
        "created": now,
        "updated": now,
        "version": 1,
        "type": type,
        "tags": tag_list,
        "status": status,
        "confidence": confidence,
        "sources": [],
        "source_count": 0,
        "related": related_list,
        "word_count": word_count,
        "read_time_min": read_time,
        "backlink_count": 0,
    }

    # Write the article.
    vault = Vault(vault_path)
    ops = VaultOps(vault)
    path = ops.write_compiled_article(type + "s", filename, metadata, note_body)

    # Update state.
    state_mgr = StateManager(vault.oar_dir)
    from oar.core.hashing import content_hash_string

    state_mgr.register_article(
        article_id, str(path.relative_to(vault.path)), content_hash_string(note_body)
    )

    # Update compiled count in stats.
    state = state_mgr.load()
    compiled_articles = len(ops.list_compiled_articles())
    state.setdefault("stats", {})["compiled_articles"] = compiled_articles
    total_words = state["stats"].get("total_words", 0) + word_count
    state["stats"]["total_words"] = total_words
    state_mgr.save(state)

    # Optionally open in editor.
    if edit:
        editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vi"))
        import subprocess

        subprocess.run([editor, str(path)])

    console.print(
        Panel(
            f"[bold green]Note added[/bold green]\n"
            f"Title: {title}\n"
            f"ID: {article_id}\n"
            f"Type: {type}\n"
            f"Tags: {', '.join(tag_list) or '(none)'}\n"
            f"Path: {path.relative_to(vault.path)}\n"
            f"Words: {word_count}",
            title="oar add-note",
            border_style="green",
        )
    )
