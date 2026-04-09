"""Frontmatter management — read, write, and validate YAML frontmatter on markdown files."""

from __future__ import annotations

from pathlib import Path

import frontmatter


class FrontmatterManager:
    """Read and write YAML frontmatter on markdown files."""

    def read(self, path: Path) -> tuple[dict, str]:
        """Return ``(frontmatter_dict, body_text)`` from a markdown file.

        Files without frontmatter delimiters return an empty dict and the
        full file content as the body.
        """
        post = frontmatter.load(str(path))
        return dict(post.metadata), post.content

    def write(self, path: Path, metadata: dict, body: str) -> None:
        """Write *metadata* as YAML frontmatter + *body* to *path*."""
        post = frontmatter.Post(body, **metadata)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(frontmatter.dumps(post))

    def update_metadata(self, path: Path, updates: dict) -> None:
        """Merge *updates* into existing frontmatter, preserving the body."""
        meta, body = self.read(path)
        meta.update(updates)
        self.write(path, meta, body)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    VALID_RAW_TYPES = {"article", "paper", "repo", "file", "url"}

    def validate_raw(self, metadata: dict) -> list[str]:
        """Validate raw article frontmatter.

        Returns a list of error strings — empty when valid.
        """
        errors: list[str] = []

        # Required fields.
        for field in ("id", "title", "source_type"):
            if field not in metadata:
                errors.append(f"Missing required field: {field}")

        # Type checks.
        if "compiled" in metadata and not isinstance(metadata["compiled"], bool):
            errors.append("'compiled' must be a boolean")
        if "word_count" in metadata and not isinstance(metadata["word_count"], int):
            errors.append("'word_count' must be an integer")

        return errors

    VALID_COMPILED_TYPES = {
        "concept",
        "entity",
        "method",
        "comparison",
        "tutorial",
        "timeline",
    }
    VALID_STATUSES = {"stub", "draft", "mature", "review"}

    def validate_compiled(self, metadata: dict) -> list[str]:
        """Validate compiled article frontmatter.

        Returns a list of error strings — empty when valid.
        """
        errors: list[str] = []

        # Required fields.
        for field in ("id", "title", "type", "status"):
            if field not in metadata:
                errors.append(f"Missing required field: {field}")

        # Enum checks.
        if "type" in metadata and metadata["type"] not in self.VALID_COMPILED_TYPES:
            errors.append(
                f"Invalid type '{metadata['type']}'; "
                f"must be one of {sorted(self.VALID_COMPILED_TYPES)}"
            )
        if "status" in metadata and metadata["status"] not in self.VALID_STATUSES:
            errors.append(
                f"Invalid status '{metadata['status']}'; "
                f"must be one of {sorted(self.VALID_STATUSES)}"
            )

        # Range check.
        if "confidence" in metadata:
            c = metadata["confidence"]
            if not isinstance(c, (int, float)) or not (0 <= c <= 1):
                errors.append("'confidence' must be a number between 0 and 1")

        return errors
