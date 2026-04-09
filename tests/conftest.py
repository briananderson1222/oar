"""Shared pytest fixtures for the OAR test suite."""

import pytest
from pathlib import Path

from oar.core.vault import Vault
from oar.core.state import StateManager


@pytest.fixture
def tmp_vault(tmp_path):
    """Create a complete empty vault in a temp directory."""
    vault = Vault(tmp_path / "test-vault")
    vault.init()
    return vault.path


@pytest.fixture
def sample_raw_article(tmp_vault):
    """Write a valid raw article to 01-raw/articles/."""
    article_path = tmp_vault / "01-raw" / "articles" / "2024-01-15-test-article.md"
    article_path.write_text("""\
---
id: "2024-01-15-test-article"
title: "Test Article About Transformers"
source_url: "https://example.com/test"
source_type: article
author: "Test Author"
published: "2024-01-15"
clipped: "2024-01-15T10:00:00Z"
compiled: false
compiled_into: []
word_count: 100
language: en
---

This is a test article about transformer architectures.
It discusses attention mechanisms and neural networks.
""")
    return article_path


@pytest.fixture
def sample_compiled_article(tmp_vault):
    """Write a valid compiled article to 02-compiled/concepts/."""
    article_path = (
        tmp_vault / "02-compiled" / "concepts" / "transformer-architecture.md"
    )
    article_path.write_text("""\
---
id: "transformer-architecture"
title: "Transformer Architecture"
aliases: ["transformer", "transformers"]
created: "2024-01-15T10:30:00Z"
updated: "2024-01-15T10:30:00Z"
version: 1
type: concept
domain: [machine-learning, nlp]
tags: [transformer, attention, neural-network]
status: draft
confidence: 0.9
sources:
  - "[[2024-01-15-test-article]]"
source_count: 1
related:
  - "[[attention-mechanism]]"
word_count: 500
read_time_min: 3
backlink_count: 0
complexity: intermediate
---

# Transformer Architecture

> **TL;DR**: The Transformer is a neural network architecture based on self-attention.

## Overview

The Transformer architecture revolutionized NLP.
""")
    return article_path


@pytest.fixture
def sample_state(tmp_vault):
    """Create a .oar/state.json with test data."""
    state_mgr = StateManager(tmp_vault / ".oar")
    state = state_mgr.load()
    state["articles"]["2024-01-15-test-article"] = {
        "path": "01-raw/articles/2024-01-15-test-article.md",
        "content_hash": "sha256:abc123",
        "compiled": False,
        "compiled_into": [],
        "last_compiled": None,
    }
    state["stats"]["raw_articles"] = 1
    state_mgr.save(state)
    return state
