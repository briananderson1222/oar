# OAR — Obsidian Agentic RAG

> Turn documents into a cross-linked knowledge wiki, powered by AI.

OAR is a CLI tool that ingests documents, uses LLMs to compile them into a cross-linked markdown wiki, and provides agentic Q&A, full-text search, linting, and export — all viewable in [Obsidian](https://obsidian.md).

**No database required.** Everything is files + YAML frontmatter + `[[wikilinks]]`.

## Quick Start

### Install

```bash
# Option 1: pipx (recommended)
pipx install git+https://github.com/briananderson1222/oar.git

# Option 2: pip
pip install git+https://github.com/briananderson1222/oar.git

# Option 3: Download binary from Releases
# Go to https://github.com/briananderson1222/oar/releases
```

### Initialize a vault

```bash
oar init --path ~/my-wiki
cd ~/my-wiki
```

This creates an Obsidian-compatible vault with directories for raw sources, compiled wiki articles, indices, and outputs.

### Add knowledge

**Interactive (recommended):** Use the skill file with your AI assistant. It writes the content, OAR handles the structure.

```bash
# The AI agent writes content and runs:
oar add-note --title "Attention Mechanisms" --type concept --tags "ai,deep-learning" --body "..."
oar index --rebuild
oar validate attention-mechanisms
```

**Batch import:** Feed it raw documents and build everything in one command.

```bash
oar ingest --file article.md
oar ingest --url https://example.com/article
oar build             # Compile + index + lint in one step
```

Or just drop files into `01-raw/` and run `oar build` — it detects new content automatically.

### Explore

```bash
oar status                    # Vault statistics
oar search "neural networks"  # Full-text search
oar lint --quick --coverage   # Find gaps in coverage
oar lint --quality            # Score article quality
```

### Open in Obsidian

```bash
open -a Obsidian ~/my-wiki
```

Click `[[wikilinks]]`, browse tag pages, explore Maps of Content (MOCs).

## Architecture

```
wiki/
├── 00-inbox/          # Unprocessed imports
├── 01-raw/            # Source material (articles, papers, repos)
├── 02-compiled/       # Wiki articles organized by type
│   ├── concepts/
│   ├── methods/
│   ├── comparisons/
│   └── timelines/
├── 03-indices/        # Auto-generated cross-references
│   ├── moc/           # Maps of Content
│   ├── tags/          # Tag index pages
│   └── clusters/      # Topic clusters
├── 04-outputs/        # Generated answers, reports, slides
└── 05-logs/           # Lint reports and operational logs
```

Each wiki article has YAML frontmatter with metadata and `[[wikilinks]]` for cross-referencing.

## CLI Commands

| Command | Description |
|---------|-------------|
| `oar init` | Create a new vault |
| `oar build` | **One-command pipeline: compile → index → lint** |
| `oar add-note` | Add a structured wiki note (no LLM) |
| `oar ingest` | Import files, URLs, directories |
| `oar compile` | Compile raw articles into wiki notes (LLM) |
| `oar index` | Rebuild cross-references, MOCs, tag pages |
| `oar search` | Full-text search with SQLite FTS5 |
| `oar query` | Ask questions against the wiki (LLM) |
| `oar validate` | Check a single article's health |
| `oar lint` | Run health checks on the whole wiki |
| `oar status` | Show vault statistics |
| `oar config` | Read/set configuration |
| `oar export` | Export to HTML, slides, or fine-tune data |
| `oar vault` | Manage named vaults (add/list/remove/default) |
| `oar mcp` | Start MCP server for IDE integration |

## Multi-vault

Work with more than one vault safely. Every command that touches a vault
resolves it through a single, predictable precedence and — for any command that
**writes** — echoes exactly which vault it chose before doing anything:

```
vault: /Users/me/work-vault (via cwd)
```

### Named-vault registry

Register vaults by name so you can switch with `--vault NAME` from anywhere. The
registry lives at `~/.config/oar/vaults.yaml` (honoring `XDG_CONFIG_HOME`).

```bash
oar vault add work   ~/work-vault     # first vault added becomes the default
oar vault add notes  ~/personal-notes
oar vault list                        # shows ★ default and → the one resolving now
oar vault default notes               # change the fallback default
oar vault remove work

# Use a named vault (or a raw path) for a single command:
oar search "transformers" --vault notes
oar build --vault ~/some/other/vault
```

### Resolution precedence

The first valid vault (one containing `.oar/state.json`) wins:

| # | Source | `via` label | How it's set |
|---|--------|-------------|--------------|
| 1 | Explicit `--vault` | `registry:<name>` or `explicit path` | A registry name (preferred) or a filesystem path |
| 2 | Current directory | `cwd` | Walking up from your working directory |
| 3 | `OAR_VAULT` env var | `OAR_VAULT env` | Exported environment variable |
| 4 | Registry default | `registry default` | `oar vault default NAME` |

> **Why cwd beats `OAR_VAULT`:** a globally-exported `OAR_VAULT` must never
> silently override the vault you are standing in. Standing inside a vault always
> targets that vault unless you pass `--vault` explicitly.

The MCP tools follow the same precedence, and every tool accepts an optional
`vault` argument (a registry name or a path) to target a specific vault.

## LLM Providers

OAR can use multiple LLM backends with automatic fallback:

| Provider | How | Cost |
|----------|-----|------|
| **Claude CLI** | Uses your existing `claude` subscription | Included |
| **OpenCode** | Uses your existing `opencode` subscription | Included |
| **Codex CLI** | Uses your existing `codex` subscription | Included |
| **Ollama** | Local models via Ollama server | Free |
| **LiteLLM** | API keys (Anthropic, OpenAI, etc.) | Pay-per-token |

Auto-detected on first run. Configure with `oar config llm.provider claude-cli`.

### Offline Mode

```bash
oar --offline compile --all    # Force local models only
oar config llm.offline true    # Persist offline preference
```

## MCP Server

Expose your wiki as tools for any MCP-compatible agent. The server provides read AND write tools — agents can compile articles, build indices, and manage the full lifecycle.

```bash
oar mcp
```

### Available Tools

| Tool | Purpose |
|------|---------|
| `get_pending_articles` | Find raw articles needing compilation |
| `read_raw_article` | Read a raw article's content |
| `save_compiled_article` | Save a compiled wiki note (handles frontmatter, state, paths) |
| `mark_raw_compiled` | Link raw → compiled in state |
| `build_indices` | Rebuild MOCs, tags, orphans, stubs |
| `search_wiki` | Full-text search |
| `read_article` | Read a compiled article |
| `list_articles` | List/filter compiled articles |
| `get_wiki_context` | Retrieve relevant wiki context for agent-driven Q&A without an internal LLM call |
| `get_status` | Vault statistics |
| `list_mocs` | List Maps of Content |

**Every tool** also accepts an optional `vault` argument — a registry name or a
filesystem path — to target a specific vault. When omitted, the tool resolves
the active vault using the same precedence as the CLI (`cwd` > `OAR_VAULT` >
registry default).

### Setup: Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `~/.config/Claude/claude_desktop_config.json` (Linux):

```json
{
  "mcpServers": {
    "oar": {
      "command": "oar",
      "args": ["mcp"],
      "env": {
        "OAR_VAULT": "/path/to/your/vault"
      }
    }
  }
}
```

### Setup: Codex CLI

Add to `~/.codex/config.json` or your project's `.codex/config.json`:

```json
{
  "mcpServers": {
    "oar": {
      "command": "oar",
      "args": ["mcp"],
      "env": {
        "OAR_VAULT": "/path/to/your/vault"
      }
    }
  }
}
```

### Setup: Cursor

Add to `.cursor/mcp.json` in your project:

```json
{
  "mcpServers": {
    "oar": {
      "command": "oar",
      "args": ["mcp"],
      "env": {
        "OAR_VAULT": "/path/to/your/vault"
      }
    }
  }
}
```

### Setup: OpenCode

The skill file is already installed at `~/.opencode/skills/oar/SKILL.md`. OpenCode agents will automatically discover OAR commands. Optionally add the MCP server to `~/.config/opencode/config.json`:

```json
{
  "mcpServers": {
    "oar": {
      "command": "oar",
      "args": ["mcp"],
      "env": {
        "OAR_VAULT": "/path/to/your/vault"
      }
    }
  }
}
```

## Development

```bash
git clone https://github.com/briananderson1222/oar.git
cd oar
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -q
```

## License

MIT
