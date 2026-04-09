"""CLI index command — manage auto-generated index files (MOCs, tags, master index)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from oar.cli._shared import build_router, find_vault_path
from oar.core.link_resolver import LinkResolver
from oar.core.state import StateManager
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.index.cluster_detector import ClusterDetector
from oar.index.moc_builder import MocBuilder
from oar.index.orphan_tracker import OrphanTracker
from oar.index.stats import StatsCalculator
from oar.index.tag_builder import TagBuilder

console = Console()


def index_cmd(
    rebuild: bool = typer.Option(
        False, "--rebuild", help="Full rebuild of all indexes"
    ),
    update: bool = typer.Option(True, "--update", help="Update affected indexes only"),
    mocs_only: bool = typer.Option(False, "--mocs-only"),
    tags_only: bool = typer.Option(False, "--tags-only"),
    detect_clusters: bool = typer.Option(
        False,
        "--detect-clusters",
        help="Detect concept clusters and build cluster pages.",
    ),
) -> None:
    """Manage auto-generated index files (MOCs, tags, master index)."""
    vault_path = find_vault_path()
    if vault_path is None:
        console.print(
            "[bold red]Error:[/bold red] No OAR vault found. Run `oar init` first."
        )
        raise typer.Exit(code=1)

    vault = Vault(vault_path)
    ops = VaultOps(vault)
    state = StateManager(vault.oar_dir)

    moc_builder = MocBuilder(vault, ops)
    tag_builder = TagBuilder(vault, ops)
    resolver = LinkResolver(vault, ops)
    orphan_tracker = OrphanTracker(vault, ops, resolver)
    stats_calc = StatsCalculator(vault, ops, state)

    actions: list[str] = []

    if detect_clusters:
        # Detect clusters and build cluster pages only.
        router, _, _ = build_router(vault_path)
        cluster_detector = ClusterDetector(vault, ops, resolver, router=router)
        cluster_paths = cluster_detector.detect_and_build()
        actions.append(f"Detected and built {len(cluster_paths)} cluster page(s)")

    elif mocs_only:
        # Generate MOCs only.
        mocs = moc_builder.auto_generate_mocs()
        moc_data = moc_builder.list_mocs()
        moc_builder.build_master_index(moc_data)
        actions.append(f"Generated {len(mocs)} MOCs")
    elif tags_only:
        # Generate tag pages only.
        tags = tag_builder.auto_generate_tags()
        actions.append(f"Generated {len(tags)} tag pages")
    else:
        # Full rebuild or update.
        mocs = moc_builder.auto_generate_mocs()
        moc_data = moc_builder.list_mocs()
        moc_builder.build_master_index(moc_data)
        tags = tag_builder.auto_generate_tags()
        orphans = orphan_tracker.write_orphans_page()
        stubs = orphan_tracker.write_stubs_page()
        orphan_tracker.write_recent_page()
        actions.append(f"Generated {len(mocs)} MOCs")
        actions.append(f"Generated {len(tags)} tag pages")
        actions.append(f"Found {len(orphans)} orphans")
        actions.append(f"Found {len(stubs)} stubs")

    # Show stats.
    stats = stats_calc.calculate()
    table = Table(title="OAR Index Results", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Raw articles", str(stats.raw_articles))
    table.add_row("Compiled articles", str(stats.compiled_articles))
    table.add_row("MOCs", str(stats.mocs))
    table.add_row("Tag pages", str(stats.tag_pages))
    table.add_row("Total words", str(stats.total_words))
    console.print(table)

    console.print(
        Panel(
            "\n".join(f"• {a}" for a in actions),
            title="oar index",
            border_style="green",
        )
    )
