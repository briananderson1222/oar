"""Tests for oar.index.cluster_detector — ClusterDetector."""

from __future__ import annotations

from pathlib import Path

import pytest

from oar.core.link_resolver import LinkResolver
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.index.cluster_detector import ClusterDetector, ConceptCluster


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_compiled(
    ops: VaultOps,
    subdir: str,
    filename: str,
    article_id: str,
    title: str,
    body: str,
    *,
    tags: list[str] | None = None,
    domain: list[str] | None = None,
) -> Path:
    metadata = {
        "id": article_id,
        "title": title,
        "type": "concept",
        "status": "draft",
        "domain": domain or ["general"],
        "tags": tags or [],
    }
    return ops.write_compiled_article(subdir, filename, metadata, body)


# ---------------------------------------------------------------------------
# detect_clusters
# ---------------------------------------------------------------------------


class TestDetectClusters:
    """ClusterDetector.detect_clusters tests."""

    def test_detect_clusters_empty_vault(self, tmp_vault):
        """Empty vault → no clusters."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        resolver = LinkResolver(vault, ops)

        detector = ClusterDetector(vault, ops, resolver)
        clusters = detector.detect_clusters()
        assert clusters == []

    def test_detect_clusters_finds_connected(self, tmp_vault):
        """Connected component with ≥3 articles becomes a cluster."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)

        # Create 3 articles that link to each other.
        _write_compiled(
            ops,
            "concepts",
            "alpha.md",
            "alpha",
            "Alpha",
            "Content with [[beta]] and [[gamma]].",
        )
        _write_compiled(
            ops,
            "concepts",
            "beta.md",
            "beta",
            "Beta",
            "Content with [[alpha]].",
        )
        _write_compiled(
            ops,
            "concepts",
            "gamma.md",
            "gamma",
            "Gamma",
            "Content with [[alpha]].",
        )

        resolver = LinkResolver(vault, ops)
        detector = ClusterDetector(vault, ops, resolver)
        clusters = detector.detect_clusters(min_size=3)

        assert len(clusters) >= 1
        cluster = clusters[0]
        assert len(cluster.article_ids) >= 3
        assert "alpha" in cluster.article_ids

    def test_detect_clusters_min_size_filter(self, tmp_vault):
        """Small groups (< min_size) are filtered out."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)

        # Only 2 connected articles — below min_size=3.
        _write_compiled(
            ops,
            "concepts",
            "x.md",
            "x",
            "X",
            "Links to [[y]].",
        )
        _write_compiled(
            ops,
            "concepts",
            "y.md",
            "y",
            "Y",
            "Links to [[x]].",
        )

        resolver = LinkResolver(vault, ops)
        detector = ClusterDetector(vault, ops, resolver)
        clusters = detector.detect_clusters(min_size=3)
        assert clusters == []

    def test_detect_clusters_finds_central_article(self, tmp_vault):
        """Central article = most connected in the cluster."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)

        # alpha links to beta, gamma, delta → most connected.
        _write_compiled(
            ops,
            "concepts",
            "alpha.md",
            "alpha",
            "Alpha",
            "Links to [[beta]] [[gamma]] [[delta]].",
        )
        _write_compiled(
            ops,
            "concepts",
            "beta.md",
            "beta",
            "Beta",
            "Links to [[alpha]].",
        )
        _write_compiled(
            ops,
            "concepts",
            "gamma.md",
            "gamma",
            "Gamma",
            "Links to [[alpha]].",
        )
        _write_compiled(
            ops,
            "concepts",
            "delta.md",
            "delta",
            "Delta",
            "Links to [[alpha]].",
        )

        resolver = LinkResolver(vault, ops)
        detector = ClusterDetector(vault, ops, resolver)
        clusters = detector.detect_clusters(min_size=3)

        assert len(clusters) >= 1
        cluster = clusters[0]
        assert cluster.central_article == "alpha"


# ---------------------------------------------------------------------------
# build_cluster_page
# ---------------------------------------------------------------------------


class TestBuildClusterPage:
    """ClusterDetector.build_cluster_page tests."""

    def test_build_cluster_page_creates_file(self, tmp_vault):
        """Cluster page file is created at the expected path."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        resolver = LinkResolver(vault, ops)

        detector = ClusterDetector(vault, ops, resolver)

        cluster = ConceptCluster(
            name="Machine Learning",
            slug="machine-learning",
            article_ids=["alpha", "beta", "gamma"],
            central_article="alpha",
        )
        path = detector.build_cluster_page(cluster)

        assert path.exists()
        assert path.name == "cluster-machine-learning.md"
        assert "03-indices" in str(path)
        assert "clusters" in str(path)


# ---------------------------------------------------------------------------
# detect_and_build
# ---------------------------------------------------------------------------


class TestDetectAndBuild:
    """ClusterDetector.detect_and_build end-to-end tests."""

    def test_detect_and_build_returns_paths(self, tmp_vault):
        """End-to-end: detect clusters and build pages."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)

        _write_compiled(
            ops,
            "concepts",
            "a.md",
            "a",
            "A",
            "Links to [[b]] and [[c]].",
        )
        _write_compiled(
            ops,
            "concepts",
            "b.md",
            "b",
            "B",
            "Links to [[a]].",
        )
        _write_compiled(
            ops,
            "concepts",
            "c.md",
            "c",
            "C",
            "Links to [[a]].",
        )

        resolver = LinkResolver(vault, ops)
        detector = ClusterDetector(vault, ops, resolver)
        paths = detector.detect_and_build()

        assert len(paths) >= 1
        for p in paths:
            assert p.exists()
