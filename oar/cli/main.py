"""OAR CLI — Typer application with Rich output."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from oar import __version__
from oar.cli.add_note import add_note_cmd
from oar.cli.compile import compile_cmd
from oar.cli.index_cmd import index_cmd
from oar.cli.ingest import ingest as ingest_command
from oar.cli.query import query_cmd
from oar.cli.export import export_cmd
from oar.cli.lint import lint_cmd
from oar.cli.search import search_cmd
from oar.cli.validate import validate_cmd
from oar.core.config import OarConfig
from oar.core.vault import Vault

app = typer.Typer(
    name="oar",
    help="OAR — Obsidian Agentic RAG CLI",
    no_args_is_help=True,
)
console = Console()


@app.callback()
def global_options(
    offline: bool = typer.Option(
        False, "--offline", help="Force offline mode (local models only)."
    ),
) -> None:
    """OAR — Obsidian Agentic RAG CLI"""
    if offline:
        os.environ["OAR_OFFLINE"] = "true"


# Register sub-commands.
app.command(name="ingest")(ingest_command)
app.command(name="compile")(compile_cmd)
app.command(name="index")(index_cmd)
app.command(name="search")(search_cmd)
app.command(name="query")(query_cmd)
app.command(name="lint")(lint_cmd)
app.command(name="export")(export_cmd)
app.command(name="add-note")(add_note_cmd)
app.command(name="validate")(validate_cmd)


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


@app.command()
def init(
    path: Optional[str] = typer.Option(
        None, "--path", "-p", help="Directory where the vault will be created."
    ),
) -> None:
    """Initialize a new OAR vault."""
    vault_path = Path(path) if path else Path.cwd() / "oar-vault"
    vault = Vault(vault_path)
    vault.init()
    console.print(
        Panel(
            f"[bold green]Vault initialized[/bold green]\nLocation: {vault.path}",
            title="oar init",
            border_style="green",
        )
    )


@app.command()
def status(
    providers: bool = typer.Option(
        False, "--providers", help="Show detected LLM CLI providers."
    ),
) -> None:
    """Show vault statistics."""
    vault_path = _find_vault_path()
    if vault_path is None:
        console.print(
            "[bold red]Error:[/bold red] No OAR vault found. Run `oar init` first."
        )
        raise typer.Exit(code=1)

    state_file = vault_path / ".oar" / "state.json"
    try:
        state = json.loads(state_file.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        console.print(f"[bold red]Error reading state:[/bold red] {exc}")
        raise typer.Exit(code=1)

    stats = state.get("stats", {})
    table = Table(title=f"OAR Vault — {vault_path}", show_header=False)
    table.add_column("Key", style="bold cyan")
    table.add_column("Value", style="white")
    table.add_row("Vault path", str(vault_path))
    table.add_row("Raw articles", str(stats.get("raw_articles", 0)))
    table.add_row("Compiled articles", str(stats.get("compiled_articles", 0)))
    table.add_row("Total words", str(stats.get("total_words", 0)))
    table.add_row("Last compile", str(state.get("last_compile", "never")))
    table.add_row("Last lint", str(state.get("last_lint", "never")))
    console.print(table)

    if providers:
        from oar.llm.providers.registry import PROVIDER_CLASSES, ProviderRegistry

        registry = ProviderRegistry()
        config = OarConfig.load(vault_path / ".oar" / "config.yaml")

        provider_table = Table(title="LLM Providers", show_header=True)
        provider_table.add_column("Provider", style="bold cyan")
        provider_table.add_column("Available", style="white")
        provider_table.add_column("Healthy", style="white")
        provider_table.add_column("Notes", style="dim")

        for name in PROVIDER_CLASSES:
            try:
                prov = registry.get(name)
                available = prov.available
                healthy = prov.health_check() if available else False
                avail_str = "[green]✓[/green]" if available else "[dim]—[/dim]"
                health_str = (
                    "[green]✓[/green]"
                    if healthy
                    else ("[red]✗[/red]" if available else "[dim]—[/dim]")
                )

                notes = ""
                if name == "litellm" and not available:
                    notes = "No API key set"
                elif name == config.llm.provider:
                    notes = "[bold]Preferred[/bold]"

                provider_table.add_row(name, avail_str, health_str, notes)
            except Exception as exc:
                provider_table.add_row(
                    name, "[red]error[/red]", "[red]error[/red]", str(exc)[:40]
                )

        console.print(provider_table)


@app.command(name="config")
def config_cmd(
    key: Optional[str] = typer.Argument(
        None, help="Config key to read (e.g. llm.provider)"
    ),
    value: Optional[str] = typer.Argument(None, help="Value to set"),
    list_all: bool = typer.Option(False, "--list", "-l", help="Show all config values"),
) -> None:
    """Read or set OAR configuration values."""
    vault_path = _find_vault_path()
    if vault_path is None:
        console.print(
            "[bold red]Error:[/bold red] No OAR vault found. Run `oar init` first."
        )
        raise typer.Exit(code=1)

    config_path = vault_path / ".oar" / "config.yaml"
    config = OarConfig.load(config_path)

    if list_all or key is None:
        # Show all config as a nice table.
        table = Table(title="OAR Configuration", show_header=True)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        data = config.model_dump()
        for section_key, section_val in data.items():
            if isinstance(section_val, dict):
                for k, v in section_val.items():
                    if isinstance(v, dict):
                        for kk, vv in v.items():
                            table.add_row(f"{section_key}.{k}.{kk}", str(vv))
                    else:
                        table.add_row(f"{section_key}.{k}", str(v))
            else:
                table.add_row(section_key, str(section_val))
        console.print(table)
        return

    # Read a specific key.
    def _get_nested(obj: dict, path: str):
        keys = path.split(".")
        current = obj
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None
        return current

    data = config.model_dump()

    if value is None:
        # Read mode.
        result = _get_nested(data, key)
        if result is None:
            console.print(f"[yellow]Key not found:[/yellow] {key}")
            raise typer.Exit(code=1)
        if isinstance(result, dict):
            console.print_json(json.dumps(result, indent=2, default=str))
        else:
            console.print(str(result))
    else:
        # Write mode.
        keys = key.split(".")
        current = data
        for k in keys[:-1]:
            if k not in current or not isinstance(current[k], dict):
                current[k] = {}
            current = current[k]
        # Parse value type.
        parsed_value: Any = value
        if value.lower() in ("true", "false"):
            parsed_value = value.lower() == "true"
        elif value.isdigit():
            parsed_value = int(value)
        else:
            try:
                parsed_value = float(value)
            except ValueError:
                pass
        current[keys[-1]] = parsed_value
        config = OarConfig.model_validate(data)
        config.save(config_path)
        console.print(f"[green]Set {key} = {parsed_value}[/green]")


@app.command()
def mcp() -> None:
    """Start OAR MCP server (stdio transport for IDE integration)."""
    from oar.mcp_server import main as mcp_main

    mcp_main()


@app.command()
def version() -> None:
    """Print the OAR version."""
    console.print(f"oar {__version__}")
