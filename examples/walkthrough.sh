#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# OAR Walkthrough Script
# =============================================================================
# This script demonstrates every OAR CLI command using the demo vault.
# It is safe to run — it does not modify the original vault files.
#
# Prerequisites:
#   - OAR must be installed and on your PATH
#   - compile/query commands require an LLM provider (claude, opencode, codex,
#     or an API key set via environment variables)
#
# Usage:
#   ./walkthrough.sh          # run all commands
#   ./walkthrough.sh 2>&1 | tee walkthrough.log   # run and save output
# =============================================================================

VAULT="$(dirname "$0")/demo-vault"

echo "======================================================================"
echo "  OAR CLI Walkthrough"
echo "  Vault: $VAULT"
echo "======================================================================"
echo ""

# ---------------------------------------------------------------------------
# 1. Vault Status — Show an overview of the vault
# ---------------------------------------------------------------------------
echo "======================================================================"
echo "  [1/12] oar status — Show vault overview"
echo "======================================================================"
echo ""
echo "  Displays article counts, directory structure health, and overall"
echo "  vault statistics."
echo ""
oar status "$VAULT"
echo ""

# ---------------------------------------------------------------------------
# 2. Provider Status — Check which LLM providers are available
# ---------------------------------------------------------------------------
echo "======================================================================"
echo "  [2/12] oar status --providers — Show LLM provider status"
echo "======================================================================"
echo ""
echo "  Checks which LLM backends (claude, opencode, codex, API) are"
echo "  configured and reachable. Commands like compile and query depend"
echo "  on having at least one provider available."
echo ""
oar status "$VAULT" --providers
echo ""

# ---------------------------------------------------------------------------
# 3. Full-Text Search — Find articles mentioning "attention"
# ---------------------------------------------------------------------------
echo "======================================================================"
echo "  [3/12] oar search \"attention\" — Full-text search"
echo "======================================================================"
echo ""
echo "  Searches across all compiled articles for the term 'attention'."
echo "  Returns ranked results with context snippets."
echo ""
oar search "$VAULT" "attention"
echo ""

# ---------------------------------------------------------------------------
# 4. Phrase Search — Find articles about "fine-tuning"
# ---------------------------------------------------------------------------
echo "======================================================================"
echo "  [4/12] oar search \"fine-tuning\" — Phrase matching search"
echo "======================================================================"
echo ""
echo "  Demonstrates phrase matching — searches for the exact phrase"
echo "  'fine-tuning' across the vault."
echo ""
oar search "$VAULT" "fine-tuning"
echo ""

# ---------------------------------------------------------------------------
# 5. Quick Lint — Fast sanity check on vault structure
# ---------------------------------------------------------------------------
echo "======================================================================"
echo "  [5/12] oar lint --quick — Quick lint check"
echo "======================================================================"
echo ""
echo "  Runs a fast lint pass: checks frontmatter fields, file naming,"
echo "  and basic vault structure. Quick mode skips expensive checks."
echo ""
oar lint "$VAULT" --quick
echo ""

# ---------------------------------------------------------------------------
# 6. Coverage Analysis — Deep lint with coverage report
# ---------------------------------------------------------------------------
echo "======================================================================"
echo "  [6/12] oar lint --coverage — Coverage analysis"
echo "======================================================================"
echo ""
echo "  Runs a full lint pass including coverage analysis. Reports which"
echo "  articles have complete frontmatter, backlinks, tags, and content."
echo ""
oar lint "$VAULT" --coverage
echo ""

# ---------------------------------------------------------------------------
# 7. Validate Single Article — Check one article in detail
# ---------------------------------------------------------------------------
echo "======================================================================"
echo "  [7/12] oar validate — Validate a single article"
echo "======================================================================"
echo ""
echo "  Validates the 'transformer-architecture' article in detail,"
echo "  checking frontmatter completeness, link integrity, and content"
echo "  quality metrics."
echo ""
oar validate "$VAULT" --article transformer-architecture
echo ""

# ---------------------------------------------------------------------------
# 8. Add a Note — Create a new note in the vault
# ---------------------------------------------------------------------------
echo "======================================================================"
echo "  [8/12] oar add-note — Add a new note to the vault"
echo "======================================================================"
echo ""
echo "  Creates a new note with a title, body content, and tags."
echo "  Notes are placed in 00-inbox/ for later processing."
echo ""
oar add-note "$VAULT" \
  --title "Test Note" \
  --content "This is a test note created during the walkthrough." \
  --tags "test,demo"
echo ""

# ---------------------------------------------------------------------------
# 9. Build Indices — Regenerate all index files
# ---------------------------------------------------------------------------
echo "======================================================================"
echo "  [9/12] oar index — Build indices"
echo "======================================================================"
echo ""
echo "  Rebuilds all index files: master index, maps of content (MOCs),"
echo "  tag pages, orphan lists, stub detection, and recent articles."
echo ""
oar index "$VAULT"
echo ""

# ---------------------------------------------------------------------------
# 10. Export to HTML — Generate a browsable HTML export
# ---------------------------------------------------------------------------
echo "======================================================================"
echo "  [10/12] oar export — Export vault to HTML"
echo "======================================================================"
echo ""
echo "  Exports the vault as static HTML files suitable for browsing or"
echo "  hosting. Output goes to /tmp/oar-walkthrough-export/."
echo ""
oar export "$VAULT" --format html --output /tmp/oar-walkthrough-export
echo ""

# ---------------------------------------------------------------------------
# 11. Compile — Use an LLM to compile/update articles
# ---------------------------------------------------------------------------
echo "======================================================================"
echo "  [11/12] oar compile — Compile articles with LLM"
echo "======================================================================"
echo ""
echo "  Uses an LLM provider to compile raw sources into structured"
echo "  knowledge notes. Requires an LLM provider to be configured."
echo "  Skipping if no provider is available..."
echo ""

if oar compile "$VAULT" 2>/dev/null; then
  echo "  Compile succeeded."
else
  echo "  [SKIPPED] No LLM provider available or compile not configured."
  echo "  To enable: set ANTHROPIC_API_KEY, OPENAI_API_KEY, or configure"
  echo "  a provider in .oar/config.yaml"
fi
echo ""

# ---------------------------------------------------------------------------
# 12. Query — Ask a natural language question against the vault
# ---------------------------------------------------------------------------
echo "======================================================================"
echo "  [12/12] oar query — Natural language query"
echo "======================================================================"
echo ""
echo "  Asks a question against the vault's knowledge base. The LLM uses"
echo "  retrieved articles as context to generate an answer. Requires an"
echo "  LLM provider to be configured."
echo ""

if oar query "$VAULT" "What are transformers?" 2>/dev/null; then
  echo "  Query succeeded."
else
  echo "  [SKIPPED] No LLM provider available or query not configured."
  echo "  To enable: set ANTHROPIC_API_KEY, OPENAI_API_KEY, or configure"
  echo "  a provider in .oar/config.yaml"
fi
echo ""

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo "======================================================================"
echo "  Walkthrough Complete"
echo "======================================================================"
echo ""
echo "  All 12 commands demonstrated. Commands 11 and 12 (compile/query)"
echo "  require an LLM provider — they were skipped if none was available."
echo ""
echo "  To explore the vault interactively, open it in Obsidian:"
echo "    obsidian://open?vault=$VAULT"
echo ""
