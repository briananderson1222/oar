# OAR Examples

This directory contains a self-contained demo vault and walkthrough script for **Obsidian Agentic RAG (OAR)**.

## Demo Vault (`demo-vault/`)

The demo vault contains **8 AI/ML knowledge articles** that are fully cross-linked:

| Article | Type | Topic |
|---------|------|-------|
| `attention-mechanisms` | Concept | How neural networks focus on relevant input |
| `transformer-architecture` | Concept | The architecture behind modern AI models |
| `large-language-models` | Concept | GPT, Claude, Llama, and how LLMs work |
| `retrieval-augmented-generation` | Concept | Grounding LLMs in real data with RAG |
| `vector-databases` | Concept | Similarity search and vector storage |
| `embeddings` | Concept | Dense vector representations of meaning |
| `prompt-engineering` | Method | Designing effective LLM inputs |
| `fine-tuning-llms` | Method | Adapting pre-trained models to specific tasks |

All articles use `[[wiki-links]]` to reference each other, forming a connected knowledge graph.

### Vault Structure

```
demo-vault/
├── .oar/
│   ├── config.yaml          # OAR configuration (LLM model, compile settings)
│   └── templates/           # Custom prompt templates (empty in demo)
├── 00-inbox/
│   └── _index.md
├── 01-raw/
│   ├── _index.md
│   ├── articles/_index.md
│   ├── papers/_index.md
│   └── repos/_index.md
├── 02-compiled/
│   ├── _index.md
│   ├── concepts/
│   │   ├── _index.md
│   │   ├── attention-mechanisms.md
│   │   ├── transformer-architecture.md
│   │   ├── large-language-models.md
│   │   ├── retrieval-augmented-generation.md
│   │   ├── vector-databases.md
│   │   └── embeddings.md
│   └── methods/
│       ├── _index.md
│       ├── prompt-engineering.md
│       └── fine-tuning-llms.md
├── 03-indices/
│   ├── _index.md
│   ├── _master-index.md     # Entry point for LLM context building
│   ├── recent.md            # Recently updated articles
│   ├── stubs.md             # Articles below word-count threshold
│   ├── orphans.md           # Articles with few backlinks
│   ├── moc/
│   │   ├── _index.md
│   │   └── moc-uncategorized.md
│   ├── tags/
│   │   ├── _index.md
│   │   └── tag-*.md         # 22 tag index pages
│   └── clusters/
│       └── _index.md
├── 04-outputs/
│   ├── _index.md
│   ├── reports/_index.md
│   └── answers/_index.md
├── 05-logs/
│   └── _index.md
└── README.md
```

## Walkthrough Script (`walkthrough.sh`)

A comprehensive bash script that demonstrates every OAR CLI command in order:

```bash
# Make it executable (if not already)
chmod +x examples/walkthrough.sh

# Run the walkthrough
./examples/walkthrough.sh

# Save output to a log
./examples/walkthrough.sh 2>&1 | tee walkthrough.log
```

### Commands Demonstrated

| # | Command | What It Does |
|---|---------|-------------|
| 1 | `oar status` | Show vault overview and stats |
| 2 | `oar status --providers` | Check LLM provider availability |
| 3 | `oar search "attention"` | Full-text search for "attention" |
| 4 | `oar search "fine-tuning"` | Phrase matching search |
| 5 | `oar lint --quick` | Quick vault structure check |
| 6 | `oar lint --coverage` | Deep coverage analysis |
| 7 | `oar validate --article` | Validate a single article |
| 8 | `oar add-note` | Create a new note |
| 9 | `oar build --dry-run` | Preview the full pipeline |
| 10 | `oar build` | **Run compile → index → lint** |
| 11 | `oar index` | Rebuild all index files (standalone) |
| 12 | `oar export` | Export vault to HTML |
| 13 | `oar query` | Natural language Q&A (needs provider) |

## Opening in Obsidian

1. Open Obsidian
2. Click **Open folder as vault**
3. Navigate to `examples/demo-vault/` and select it
4. Obsidian will create a `.obsidian/` directory automatically

## LLM Provider Requirements

The following commands require an LLM provider to function:

- **`oar build`** (compile step) — Uses an LLM to compile raw sources into structured notes
- **`oar query`** — Uses an LLM to answer questions against the vault

Configure a provider using one of these methods:

| Provider | Setup |
|----------|-------|
| Anthropic Claude | Set `ANTHROPIC_API_KEY` environment variable |
| OpenAI | Set `OPENAI_API_KEY` environment variable |
| Ollama | Ensure Ollama is running locally (configured as fallback in `config.yaml`) |
| OpenCode/Codex | Available when running inside a supported agent |

The demo vault's `config.yaml` is pre-configured with `claude-sonnet-4-20250514` as the default model and `ollama/llama3.1` as the fallback.
