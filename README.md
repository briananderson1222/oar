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

**Batch import:** Feed it raw documents and let OAR compile them.

```bash
oar ingest --file article.md
oar ingest --url https://example.com/article
oar compile --all    # Uses claude/opencode/codex CLI tools
```

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
| `oar mcp` | Start MCP server for IDE integration |

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

Expose your wiki as tools for Claude Desktop, Cursor, or any MCP client:

```bash
oar mcp
```

Available tools: `search_wiki`, `read_article`, `list_articles`, `query_wiki`, `get_status`, `list_mocs`.

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
