# OAR — Obsidian Agentic RAG System Architecture

> **Status**: Design Complete — Ready for Implementation  
> **Last Updated**: 2025-04-08

---

## 1. Executive Summary

OAR is a **file-native, LLM-maintained personal knowledge engine** built on top of an Obsidian vault. It replaces traditional vector-database RAG with a compiled wiki approach: raw source documents are ingested, then an LLM incrementally compiles them into a richly cross-linked markdown wiki. At ~100+ articles and ~400K words, the wiki's own index files and structure become sufficient context for the LLM to answer complex questions — no embedding search or vector store required.

The system is Python CLI-first, Obsidian-rendered, file-based (zero databases), and designed to operate with local LLMs for full offline capability.

---

## 2. Context & Constraints

| Constraint | Implication |
|---|---|
| **File-based, no database** | All state lives in markdown files, YAML frontmatter, and JSON manifest files inside the vault |
| **Markdown-first** | Every artifact is a `.md` file readable by any editor, not just Obsidian |
| **Offline-capable** | Must support local LLM inference (Ollama, llama.cpp) as primary or fallback |
| **Incrementally buildable** | Phase 1 is a single Python script; Phase N is a full agent with search engine |
| **Python CLI** | Typer-based CLI tools for all operations; LLM calls via `litellm` for model portability |
| **LLM as primary maintainer** | Human reviews and curates; the LLM writes, indexes, links, and maintains all wiki content |
| **Obsidian as IDE** | Leverage `[[wikilinks]]`, tags, Dataview queries, graph view; don't fight the platform |

### Key Assumptions

- Vault size target: **500–5,000 articles**, ~500K–5M words
- Primary LLM: **Claude Sonnet** for compilation/Q&A, **Haiku** for linting/classification, **local Mistral/Llama** for offline
- Single-user system — no multi-tenancy or concurrency requirements
- macOS/Linux primary; Windows secondary

---

## 3. Directory / Vault Structure

```
oar-vault/
├── README.md                          # Vault manifest — auto-generated overview
├── .oar/                              # System directory (hidden from Obsidian graph)
│   ├── config.yaml                    # User configuration
│   ├── state.json                     # Processing state manifest
│   ├── search-index/                  # SQLite FTS5 search index
│   │   └── search.db
│   ├── templates/                     # Jinja2 templates for article generation
│   │   ├── compiled-article.md.j2
│   │   ├── index-moc.md.j2
│   │   ├── concept-card.md.j2
│   │   ├── qanda-output.md.j2
│   │   └── lint-report.md.j2
│   ├── prompts/                       # Prompt templates organized by task
│   │   ├── compile-article.md
│   │   ├── compile-update.md
│   │   ├── generate-index.md
│   │   ├── answer-question.md
│   │   ├── lint-consistency.md
│   │   ├── lint-missing-data.md
│   │   ├── classify-concept.md
│   │   └── search-query.md
│   └── cache/                         # Prompt cache, response cache
│       ├── prompt-cache/
│       └── response-cache/
│
├── 00-inbox/                          # Staging area for new raw documents
│   └── _index.md
│
├── 01-raw/                            # Source documents (originals, never modified)
│   ├── articles/
│   ├── papers/
│   ├── repos/
│   ├── images/
│   └── _index.md
│
├── 02-compiled/                       # LLM-compiled wiki articles
│   ├── concepts/
│   ├── entities/
│   ├── methods/
│   ├── comparisons/
│   ├── tutorials/
│   ├── timelines/
│   └── _index.md
│
├── 03-indices/                        # Auto-maintained navigation hubs
│   ├── moc/                           # Maps of Content (topic gateways)
│   ├── tags/                          # Tag-based aggregation pages
│   ├── clusters/                      # Concept cluster pages
│   ├── orphans.md
│   ├── stubs.md
│   ├── recent.md
│   └── stats.md
│
├── 04-outputs/                        # Q&A outputs, reports, presentations
│   ├── answers/
│   ├── reports/
│   ├── slides/
│   ├── images/
│   └── _index.md
│
├── 05-logs/                           # System operation logs
│   ├── compile-log.md
│   ├── lint-reports/
│   └── query-log.md
│
└── .obsidian/                         # Obsidian configuration
```

### Naming Conventions

| Artifact Type | Pattern | Example |
|---|---|---|
| Raw article | `{YYYY-MM-DD}-{slug}.md` | `2024-01-15-transformer-architecture.md` |
| Compiled concept | `{kebab-case-topic}.md` | `attention-mechanism.md` |
| Map of Content | `moc-{kebab-case-area}.md` | `moc-llm-foundations.md` |
| Tag page | `tag-{tag-name}.md` | `tag-transformer.md` |
| Q&A answer | `{YYYY-MM-DD}-{slug}.md` | `2024-03-15-how-does-rlhf-work.md` |
| System index | `_index.md` (underscore-prefixed) | `_index.md` |

---

## 4. File Format Conventions

### 4.1 Compiled Article Format

```markdown
---
# === IDENTITY ===
id: "attention-mechanism"
title: "Attention Mechanism"
aliases: ["attention", "self-attention", "scaled dot-product attention"]
created: "2024-01-15T10:30:00Z"
updated: "2024-03-10T14:22:00Z"
version: 3

# === CLASSIFICATION ===
type: concept                     # concept | entity | method | comparison | tutorial | timeline
domain: [machine-learning, nlp]
tags: [transformer, attention, neural-network, deep-learning]
status: mature                    # stub | draft | mature | review
confidence: 0.95

# === PROVENANCE ===
sources:
  - "[[2024-01-15-transformer-architecture]]"
  - "[[2023-attention-is-all-you-need]]"
source_count: 3

# === RELATIONSHIPS ===
related:
  - "[[transformer-architecture]]"
  - "[[multi-head-attention]]"
  - "[[positional-encoding]]"
prerequisite_for:
  - "[[transformer-architecture]]"
see_also:
  - "[[memory-networks]]"

# === METRICS ===
word_count: 1247
read_time_min: 6
backlink_count: 12
complexity: intermediate          # beginner | intermediate | advanced
---

# Attention Mechanism

> **TL;DR**: One-paragraph summary of the concept.

## Overview
[2-3 paragraph high-level explanation]

## Key Ideas
- **Concept 1**: ...
- **Concept 2**: ...

## How It Works
[Step-by-step explanation with optional mermaid diagram]

## Variants
- **Self-attention**: [[self-attention]]
- **Multi-head**: [[multi-head-attention]]

## Applications
- Core of [[transformer-architecture]]

## History
| Year | Milestone | Reference |
|------|-----------|-----------|
| 2017 | Scaled dot-product | [[2017-attention-is-all-you-need]] |

## Open Questions
- Can attention be replaced by SSMs?

## References
- [[2017-attention-is-all-you-need]] — Original paper

---
*Last compiled: 2024-03-10 by OAR v0.3.0 | Sources: 3 | Confidence: 0.95*
```

### 4.2 Raw Article Format

```markdown
---
id: "2024-01-15-transformer-architecture"
title: "Transformer Architecture"
source_url: "https://arxiv.org/abs/1706.03762"
source_type: article
author: "Vaswani et al."
published: "2017-06-12"
clipped: "2024-01-15T10:00:00Z"
compiled: false
compiled_into: []
word_count: 8432
language: en
---

[Original content — never modified after ingestion]
```

### 4.3 State Manifest (`.oar/state.json`)

```json
{
  "version": "0.1.0",
  "vault_path": "/Users/brian/oar-vault",
  "last_compile": "2024-03-10T14:22:00Z",
  "stats": {
    "raw_articles": 142,
    "compiled_articles": 89,
    "total_words": 487000
  },
  "articles": {
    "2024-01-15-transformer-architecture": {
      "path": "01-raw/articles/2024-01-15-transformer-architecture.md",
      "content_hash": "sha256:a1b2c3d4...",
      "compiled": true,
      "compiled_into": ["transformer-architecture", "attention-mechanism"],
      "last_compiled": "2024-03-10T14:22:00Z"
    }
  }
}
```

---

## 5. System Components

| Component | Responsibility | Technology |
|---|---|---|
| **`oar` CLI** | Unified command-line interface | Python, Typer, Rich |
| **Frontmatter Parser** | Read/write YAML frontmatter on .md files | `python-frontmatter` |
| **LLM Router** | Model selection, rate limiting, cost tracking | `litellm`, `anthropic` |
| **Context Manager** | Build optimal context windows from vault | Custom — token counting, relevance |
| **Diff Engine** | Detect changed articles, incremental updates | `difflib`, content hashing |
| **Link Resolver** | Backlink graph, orphans, validate `[[links]]` | Custom graph over filesystem |
| **Template Renderer** | Generate articles from templates | Jinja2 |
| **Index Builder** | Build MOCs, tag pages, clusters | Custom + LLM for clustering |
| **Search Engine** | Full-text search (CLI + web UI) | SQLite FTS5 + FastAPI |
| **State Manager** | Track processing state, hashes, versions | JSON manifest on disk |

---

## 6. Data Flows

### Ingestion
URL/File/PDF → fetch/extract → write to `01-raw/` → update state → set `compiled=false`

### Compilation
Read uncompiled articles → build context → LLM generates compiled articles → write to `02-compiled/` → update backlinks → rebuild affected indices

### Q&A
User question → read master index → identify relevant MOCs → read top articles → LLM answers with tool use → save output to `04-outputs/` → file back into wiki

### Linting
Scan all articles → structural checks → LLM consistency checks → detect orphans/stubs → write report → suggest fixes

---

## 7. Index / Summary System (Core Innovation)

The index system **replaces vector search** with structured navigation files:

```
03-indices/
├── _master-index.md       ← Entry point for LLM (~3K tokens, always fits in context)
├── moc/                   ← Maps of Content (topic gateways)
├── tags/                  ← Auto-generated tag aggregation
├── clusters/              ← Auto-detected concept clusters
├── orphans.md             ← Articles with <2 backlinks
├── stubs.md               ← Incomplete articles
├── recent.md              ← Last 20 additions
└── stats.md               ← Vault metrics
```

**How the LLM navigates** (Progressive Context Loading):
1. Read `_master-index.md` (~3K tokens) → identify relevant MOCs
2. Read 2-3 MOC files (~6K tokens) → identify 5-10 relevant articles
3. Read full text of top articles (~30-50K tokens)
4. Check related/sources frontmatter for supplementary context (~10K tokens)
5. Total: ~50-70K tokens — well within 200K context window

---

## 8. Search Engine Design

- **Storage**: SQLite FTS5 (zero-dependency, file-based)
- **Schema**: `vault_fts` (title, body, aliases, tags), `vault_docs` (metadata), `backlinks` (graph)
- **Interfaces**: CLI (`oar search`), Web UI (FastAPI at localhost:3232), LLM tool
- **Ranking**: TF-IDF + recency + backlink_count
- **API endpoints**: `/search`, `/article/{id}`, `/backlinks/{id}`, `/graph/cluster/{id}`, `/stats`

---

## 9. LLM Integration Strategy

### Model Tiering

| Task | Model | Fallback | Cost/Call |
|---|---|---|---|
| Compile new article | Claude Sonnet | Llama 3.1 70B (Ollama) | ~$0.05 |
| Update existing | Claude Haiku | Mistral 7B | ~$0.005 |
| Q&A (complex) | Claude Sonnet | Llama 3.1 70B | ~$0.25 |
| Q&A (simple) | Claude Haiku | Mistral 7B | ~$0.01 |
| Lint/checks | Claude Haiku | Mistral 7B | ~$0.005 |
| Cluster detection | Claude Sonnet | Llama 3.1 70B | ~$0.13 |

### Agent Tools (for Q&A)

1. `search_wiki` — Full-text search over compiled wiki
2. `read_article` — Read full article content by ID
3. `read_raw_source` — Read original source document
4. `get_backlinks` — Get articles linking TO a given article
5. `get_related` — Traverse relationship graph
6. `read_moc` / `list_mocs` — Navigate MOC hierarchy
7. `web_search` — Search the web (sparingly)
8. `create_article` / `update_article` — Modify the wiki
9. `generate_diagram` / `create_slides` — Visual output
10. `file_output` — Save Q&A output back into wiki

### Cost Optimization

- **Prompt caching**: ~50-60% input token reduction on repeated patterns
- **Model tiering**: Haiku for 70% of operations, Sonnet for 30%
- **Estimated monthly cost**: ~$8/month with prompt caching

---

## 10. CLI Command Reference

| Command | Purpose | Key Options |
|---------|---------|-------------|
| `oar ingest` | Import documents | `--url`, `--file`, `--repo`, `--dir`, `--type` |
| `oar compile` | Compile raw → wiki | `--all`, `--article`, `--cascade`, `--model`, `--max-cost` |
| `oar query` | Q&A against wiki | Interactive mode, `--format slides\|report\|chart`, `--save` |
| `oar search` | Search wiki | `--type`, `--domain`, `--serve` (web UI), `--format json` |
| `oar lint` | Health checks | `--quick`, `--fix`, `--web-search` |
| `oar index` | Manage indices | `--rebuild`, `--detect-clusters` |
| `oar export` | Export formats | `--format html\|pdf\|docx\|finetune` |
| `oar status` | Vault overview | `--queue`, `--costs` |
| `oar config` | Configuration | `set`, `show`, `init` |

---

## 11. Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Language | Python 3.11+ | LLM ecosystem, accessibility |
| CLI | Typer + Rich | Type-hinted, beautiful terminal output |
| LLM Router | litellm | Unified API for all providers |
| Search | SQLite FTS5 | Zero-dependency full-text search |
| Web UI | FastAPI + HTMX | Minimal, no build step |
| Templates | Jinja2 | Article and prompt templates |
| Frontmatter | python-frontmatter | YAML parse/write on .md |
| Slides | Marp CLI | Markdown → PDF/PPTX |
| Config | Pydantic + YAML | Type-safe configuration |

### Recommended Obsidian Plugins

- **Dataview** (required) — Dynamic queries over frontmatter
- **Mermaid** (required) — Diagram rendering
- **Marp** (optional) — Slide deck rendering
- **Calendar** (optional) — Timeline visualization
- **Graph Analysis** (optional) — Advanced graph metrics

---

## 12. Architecture Decision Records

### ADR-1: File-based state vs. SQLite
**Decision**: File-based for wiki content + minimal SQLite for search index only. State in JSON for transparency.
**Rationale**: Obsidian compatibility, portability, inspectability. Single-user system doesn't need ACID.

### ADR-2: Compiled Wiki RAG vs. Vector RAG
**Decision**: Compiled wiki up to ~5,000 articles. Evaluate hybrid beyond that.
**Rationale**: No embedding pipeline, better context quality, human-browsable, fixed cost (compile once, read many).

### ADR-3: Python CLI vs. Obsidian Plugin
**Decision**: Python CLI as primary. Obsidian plugin as future enhancement.
**Rationale**: Rich LLM ecosystem, full agent capabilities, portability, no Obsidian API limitations.

---

## 13. Project Structure (Python Package)

```
oar/
├── pyproject.toml
├── oar/
│   ├── __init__.py
│   ├── cli/                    # CLI commands (ingest, compile, query, etc.)
│   ├── core/                   # Vault, frontmatter, state, linker, hashing
│   ├── llm/                    # Router, context builder, tools, prompts, cost tracker
│   ├── compile/                # Compiler, article logic, classifier
│   ├── search/                 # Indexer, searcher, ranker, server
│   ├── index/                  # MOC builder, tag builder, cluster detector
│   ├── lint/                   # Structural, consistency, connections
│   ├── export/                 # HTML, PDF, fine-tune, slides
│   └── templates/              # Default Jinja2 templates
├── tests/
│   ├── test_compile.py
│   ├── test_search.py
│   ├── test_state.py
│   ├── test_ingest.py
│   ├── test_query.py
│   ├── test_lint.py
│   └── conftest.py
└── scripts/
    └── setup-vault.sh
```

---

*This architecture document serves as the source of truth for the OAR implementation. See `plans/` directory for phased implementation blueprints.*
