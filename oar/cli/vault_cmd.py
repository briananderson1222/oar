"""oar vault — manage the named-vault registry (~/.config/oar/vaults.yaml)."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from oar.cli._shared import resolve_vault
from oar.core import vault_registry

console = Console()

vault_app = typer.Typer(
    name="vault",
    help="Manage named vaults (registry at ~/.config/oar/vaults.yaml).",
    no_args_is_help=True,
)


@vault_app.command("add")
def vault_add(
    name: str = typer.Argument(..., help="Short name for the vault."),
    path: str = typer.Argument(..., help="Path to the vault directory."),
) -> None:
    """Register NAME → PATH. The first vault added becomes the default."""
    abs_path = Path(path).expanduser().resolve()
    if not (abs_path / ".oar" / "state.json").exists():
        console.print(
            f"[yellow]Warning:[/yellow] {abs_path} does not look like an OAR vault "
            "(no .oar/state.json). Registering anyway."
        )
    data = vault_registry.add(name, abs_path)
    is_default = data.get("default") == name
    console.print(
        f"[green]Registered[/green] [cyan]{name}[/cyan] → {abs_path}"
        + ("  [dim](default)[/dim]" if is_default else "")
    )


@vault_app.command("list")
def vault_list() -> None:
    """List registered vaults; mark the default and the one resolving NOW."""
    data = vault_registry.load()
    vaults = data.get("vaults", {})
    default = data.get("default")

    # What would resolve right now (from cwd/env/registry, no --vault)?
    resolved = resolve_vault(None)
    resolved_path = str(resolved[0]) if resolved else None
    resolved_source = resolved[1] if resolved else None

    if not vaults:
        console.print("[dim]No named vaults registered.[/dim]")
    else:
        table = Table(title="Registered Vaults", show_header=True)
        table.add_column("Name", style="cyan")
        table.add_column("Path", style="white")
        table.add_column("Default", justify="center")
        table.add_column("Active now", justify="center")
        for vname, vpath in sorted(vaults.items()):
            is_default = "★" if vname == default else ""
            is_active = "→" if resolved_path and str(Path(vpath).resolve()) == resolved_path else ""
            table.add_row(vname, vpath, is_default, is_active)
        console.print(table)

    if resolved:
        console.print(
            f"\n[dim]Resolves now:[/dim] {resolved_path} "
            f"[dim](via {resolved_source})[/dim]"
        )
    else:
        console.print("\n[dim]No vault resolves from the current directory/env.[/dim]")


@vault_app.command("remove")
def vault_remove(
    name: str = typer.Argument(..., help="Name of the vault to remove."),
) -> None:
    """Remove NAME from the registry."""
    data = vault_registry.load()
    if name not in data.get("vaults", {}):
        console.print(f"[bold red]Error:[/bold red] No such vault: {name}")
        raise typer.Exit(code=1)
    vault_registry.remove(name)
    console.print(f"[green]Removed[/green] [cyan]{name}[/cyan]")


@vault_app.command("default")
def vault_default(
    name: str = typer.Argument(..., help="Name of the vault to set as default."),
) -> None:
    """Set NAME as the default vault (lowest-precedence fallback)."""
    try:
        vault_registry.set_default(name)
    except KeyError:
        console.print(f"[bold red]Error:[/bold red] No such vault: {name}")
        raise typer.Exit(code=1)
    console.print(f"[green]Default set to[/green] [cyan]{name}[/cyan]")
