"""CLI ingest command — import documents into the vault's raw directory."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from oar.core.frontmatter import FrontmatterManager
from oar.core.hashing import content_hash_string
from oar.core.state import StateManager
from oar.core.vault import Vault
from oar.ingest.fetcher import URLFetcher
from oar.ingest.file_importer import FileImporter
from oar.ingest.metadata import generate_raw_metadata

console = Console()


def _find_vault_path() -> Optional[Path]:
    """Resolve vault path — prefer OAR_VAULT env var, else walk up from cwd."""
    env_path = os.environ.get("OAR_VAULT")
    if env_path:
        p = Path(env_path)
        if (p / ".oar" / "state.json").exists():
            return p

    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".oar" / "state.json").exists():
            return parent
    return None


def ingest(
    url: Optional[str] = typer.Option(None, "--url", help="URL to fetch"),
    file: Optional[Path] = typer.Option(None, "--file", help="Local file to import"),
    dir: Optional[Path] = typer.Option(None, "--dir", help="Directory to batch import"),
    type: str = typer.Option("article", "--type", help="article|paper|repo"),
) -> None:
    """Import documents into the vault's raw directory."""
    vault_path = _find_vault_path()
    if vault_path is None:
        console.print(
            "[bold red]Error:[/bold red] No OAR vault found. Run `oar init` first."
        )
        raise typer.Exit(code=1)

    vault = Vault(vault_path)

    if url:
        _handle_url(vault, url, type)
    elif file:
        _handle_file(vault, file)
    elif dir:
        _handle_directory(vault, dir)
    else:
        console.print(
            "[bold red]Error:[/bold red] Provide one of --url, --file, or --dir."
        )
        raise typer.Exit(code=1)


def _handle_url(vault: Vault, url: str, source_type: str) -> None:
    """Fetch a URL and write it as a raw article."""
    fetcher = URLFetcher()
    try:
        result = fetcher.fetch(url)
    except Exception as exc:
        console.print(f"[bold red]Fetch error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    metadata = generate_raw_metadata(
        title=result.title,
        source_url=url,
        source_type=source_type,
        author=result.author,
        published=result.published_date,
        content=result.content,
    )

    filename = f"{metadata['id']}.md"
    fm = FrontmatterManager()
    dest = vault.raw_dir / "articles" / filename
    fm.write(dest, metadata, result.content)

    # Register in state.
    state_mgr = StateManager(vault.oar_dir)
    content_hash = content_hash_string(result.content)
    rel_path = f"01-raw/articles/{filename}"
    state_mgr.register_article(metadata["id"], rel_path, content_hash)

    console.print(
        Panel(
            f"[bold green]Imported from URL[/bold green]\n"
            f"Title: {result.title}\n"
            f"File: {dest.name}",
            title="oar ingest",
            border_style="green",
        )
    )


def _handle_file(vault: Vault, file: Path) -> None:
    """Import a local file into the vault."""
    if not file.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {file}")
        raise typer.Exit(code=1)

    importer = FileImporter()
    dest = importer.import_file(file, vault)

    console.print(
        Panel(
            f"[bold green]Imported file[/bold green]\n"
            f"Source: {file}\n"
            f"File: {dest.name}",
            title="oar ingest",
            border_style="green",
        )
    )


def _handle_directory(vault: Vault, dir: Path) -> None:
    """Import all files from a directory into the vault."""
    if not dir.is_dir():
        console.print(f"[bold red]Error:[/bold red] Directory not found: {dir}")
        raise typer.Exit(code=1)

    importer = FileImporter()
    results = importer.import_directory(dir, vault)

    console.print(
        Panel(
            f"[bold green]Imported {len(results)} files[/bold green]\nFrom: {dir}",
            title="oar ingest",
            border_style="green",
        )
    )
