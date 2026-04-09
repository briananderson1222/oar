"""Content hashing — SHA-256 digests for change detection."""

from __future__ import annotations

import hashlib
from pathlib import Path


def content_hash(path: Path) -> str:
    """SHA-256 hash of file content.

    Returns ``'sha256:<hex>'``.
    """
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    return f"sha256:{digest}"


def content_hash_string(content: str) -> str:
    """SHA-256 hash of a string.

    Returns ``'sha256:<hex>'``.
    """
    digest = hashlib.sha256(content.encode()).hexdigest()
    return f"sha256:{digest}"


def has_content_changed(path: Path, previous_hash: str) -> bool:
    """Return ``True`` if the file's current hash differs from *previous_hash*."""
    return content_hash(path) != previous_hash
