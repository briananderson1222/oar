#!/usr/bin/env bash
# Initialize an OAR vault at the specified path (default: ./oar-vault).
set -euo pipefail

VAULT_PATH="${1:-./oar-vault}"

echo "Initializing OAR vault at: $VAULT_PATH"
oar init --path "$VAULT_PATH"
echo "Done."
