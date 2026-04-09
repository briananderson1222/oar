"""Vault management — directory tree creation, validation, and path resolution."""

from __future__ import annotations

import json
from pathlib import Path

from oar.core.config import OarConfig

# All directories that comprise a complete vault tree.
REQUIRED_DIRS: list[str] = [
    ".oar",
    ".oar/search-index",
    ".oar/templates",
    ".oar/prompts",
    ".oar/cache",
    ".oar/cache/prompt-cache",
    ".oar/cache/response-cache",
    "00-inbox",
    "01-raw",
    "01-raw/articles",
    "01-raw/papers",
    "01-raw/repos",
    "01-raw/images",
    "02-compiled",
    "02-compiled/concepts",
    "02-compiled/entities",
    "02-compiled/methods",
    "02-compiled/comparisons",
    "02-compiled/tutorials",
    "02-compiled/timelines",
    "03-indices",
    "03-indices/moc",
    "03-indices/tags",
    "03-indices/clusters",
    "04-outputs",
    "04-outputs/answers",
    "04-outputs/reports",
    "04-outputs/slides",
    "04-outputs/images",
    "05-logs",
    "05-logs/lint-reports",
]

# Directories that should contain an _index.md file.
INDEX_DIRS: list[str] = [
    "00-inbox",
    "01-raw",
    "01-raw/articles",
    "01-raw/papers",
    "01-raw/repos",
    "02-compiled",
    "02-compiled/concepts",
    "02-compiled/entities",
    "02-compiled/methods",
    "02-compiled/comparisons",
    "02-compiled/tutorials",
    "02-compiled/timelines",
    "03-indices",
    "03-indices/moc",
    "03-indices/tags",
    "03-indices/clusters",
    "04-outputs",
    "04-outputs/answers",
    "04-outputs/reports",
    "05-logs",
]

EMPTY_STATE: dict = {
    "version": "0.1.0",
    "vault_path": "",
    "last_compile": None,
    "last_lint": None,
    "stats": {
        "raw_articles": 0,
        "compiled_articles": 0,
        "total_words": 0,
    },
    "articles": {},
}

README_CONTENT = """\
# OAR Vault

Welcome to your **Obsidian Agentic RAG** vault.

## Directory layout

| Directory | Purpose |
|---|---|
| `00-inbox/` | Unprocessed clippings and imports |
| `01-raw/` | Raw source material (articles, papers, repos, images) |
| `02-compiled/` | AI-compiled knowledge notes (concepts, entities, methods, …) |
| `03-indices/` | Maps of content, tag indices, topic clusters |
| `04-outputs/` | Generated answers, reports, slides, images |
| `05-logs/` | Lint reports and operational logs |
| `.oar/` | Internal state, config, caches, and templates |
"""

CONFIG_CONTENT = """\
# OAR configuration — edit freely
llm:
  default_model: "claude-sonnet-4-20250514"
  fallback_model: "ollama/llama3.1"
  max_cost_per_call: 0.50

compile:
  default_type: "concept"
  auto_index: true
"""


class Vault:
    """Represents an OAR vault on disk."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path).resolve()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def init(self) -> None:
        """Create the complete vault directory tree.

        Idempotent — safe to call on an already-initialized vault.
        """
        # Ensure the vault root exists.
        self.path.mkdir(parents=True, exist_ok=True)

        # Create all required directories.
        for rel in REQUIRED_DIRS:
            (self.path / rel).mkdir(parents=True, exist_ok=True)

        # Write README.md (only if missing — don't overwrite user edits).
        readme = self.path / "README.md"
        if not readme.exists():
            readme.write_text(README_CONTENT)

        # Write .oar/config.yaml (only if missing).
        config_path = self.oar_dir / "config.yaml"
        if not config_path.exists():
            config_path.write_text(CONFIG_CONTENT)

        # Write .oar/state.json (only if missing).
        state_path = self.oar_dir / "state.json"
        if not state_path.exists():
            state_path.write_text(json.dumps(EMPTY_STATE, indent=2) + "\n")

        # Write _index.md files in key directories.
        for rel in INDEX_DIRS:
            index_file = self.path / rel / "_index.md"
            if not index_file.exists():
                dir_name = rel.split("/")[-1]
                index_file.write_text(
                    f"# {dir_name}\n\nThis is an auto-generated index file.\n"
                )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> bool:
        """Return True iff every required directory exists."""
        return all((self.path / rel).is_dir() for rel in REQUIRED_DIRS)

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def resolve(self, rel_path: str) -> Path:
        """Resolve a vault-relative path to an absolute path."""
        return (self.path / rel_path).resolve()

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def raw_dir(self) -> Path:
        return self.path / "01-raw"

    @property
    def compiled_dir(self) -> Path:
        return self.path / "02-compiled"

    @property
    def indices_dir(self) -> Path:
        return self.path / "03-indices"

    @property
    def oar_dir(self) -> Path:
        return self.path / ".oar"
