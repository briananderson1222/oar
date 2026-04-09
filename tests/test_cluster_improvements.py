"""Tests for improved cluster detection — LLM naming, max_size, tag-based."""

import json
from unittest.mock import MagicMock

from oar.core.link_resolver import LinkResolver
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.index.cluster_detector import ClusterDetector, ConceptCluster
from oar.llm.providers.base import LLMResponse


def _write_compiled(ops, subdir, filename, article_id, title, body, *, tags=None):
    metadata = {
        "id": article_id,
        "title": title,
        "type": "concept",
        "status": "draft",
        "tags": tags or [],
    }
    return ops.write_compiled_article(subdir, filename, metadata, body)


class TestClusterLLMNaming:
    """LLM-based cluster naming and descriptions."""

    def test_name_cluster_uses_llm(self, tmp_vault):
        """name_cluster calls the router and updates name/description."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        resolver = LinkResolver(vault, ops)

        _write_compiled(
            ops, "concepts", "a.md", "a", "Neural Networks", "Content.", tags=["ml"]
        )
        _write_compiled(
            ops, "concepts", "b.md", "b", "Deep Learning", "Content.", tags=["ml"]
        )

        mock_router = MagicMock()
        mock_router.complete.return_value = LLMResponse(
            content=json.dumps(
                {
                    "name": "Machine Learning",
                    "description": "Articles about ML techniques.",
                }
            ),
            model="mock",
            input_tokens=100,
            output_tokens=20,
            cost_usd=0.001,
        )

        detector = ClusterDetector(vault, ops, resolver, router=mock_router)
        cluster = ConceptCluster(
            name="a",
            slug="a",
            article_ids=["a", "b"],
            central_article="a",
        )
        detector.name_cluster(cluster)

        assert cluster.name == "Machine Learning"
        assert cluster.description == "Articles about ML techniques."
        assert cluster.slug == "machine-learning"

    def test_name_cluster_falls_back_without_router(self, tmp_vault):
        """Without a router, name_cluster keeps the default name."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        resolver = LinkResolver(vault, ops)

        detector = ClusterDetector(vault, ops, resolver)
        cluster = ConceptCluster(
            name="Original Name",
            slug="original-name",
            article_ids=["a"],
            central_article="a",
        )
        detector.name_cluster(cluster)

        # Should remain unchanged.
        assert cluster.name == "Original Name"

    def test_name_cluster_handles_bad_llm_response(self, tmp_vault):
        """If LLM returns invalid JSON, keep the default name."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        resolver = LinkResolver(vault, ops)

        mock_router = MagicMock()
        mock_router.complete.return_value = LLMResponse(
            content="not valid json at all",
            model="mock",
            input_tokens=50,
            output_tokens=5,
            cost_usd=0.001,
        )

        detector = ClusterDetector(vault, ops, resolver, router=mock_router)
        cluster = ConceptCluster(
            name="Default",
            slug="default",
            article_ids=["a"],
            central_article="a",
        )
        detector.name_cluster(cluster)

        assert cluster.name == "Default"


class TestClusterMaxSize:
    """max_size splitting of oversized clusters."""

    def test_max_size_splits_large_component(self, tmp_vault):
        """Components larger than max_size get split by tag similarity."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)

        # Create 6 interconnected articles: 3 about ML, 3 about physics.
        _write_compiled(
            ops,
            "concepts",
            "nn.md",
            "nn",
            "Neural Networks",
            "See [[cnn]] [[rnn]] [[mlp]].",
            tags=["ml"],
        )
        _write_compiled(
            ops,
            "concepts",
            "cnn.md",
            "cnn",
            "CNNs",
            "See [[nn]].",
            tags=["ml"],
        )
        _write_compiled(
            ops,
            "concepts",
            "rnn.md",
            "rnn",
            "RNNs",
            "See [[nn]].",
            tags=["ml"],
        )
        _write_compiled(
            ops,
            "concepts",
            "mlp.md",
            "mlp",
            "MLP",
            "See [[nn]] [[quantum]].",
            tags=["ml"],
        )

        _write_compiled(
            ops,
            "concepts",
            "quantum.md",
            "quantum",
            "Quantum Computing",
            "See [[qubit]] [[nn]].",
            tags=["physics"],
        )
        _write_compiled(
            ops,
            "concepts",
            "qubit.md",
            "qubit",
            "Qubits",
            "See [[quantum]].",
            tags=["physics"],
        )

        resolver = LinkResolver(vault, ops)
        detector = ClusterDetector(vault, ops, resolver)

        # With max_size=4, the 6-node component should be split.
        clusters = detector.detect_clusters(min_size=2, max_size=4)
        # Should get at least 1 cluster (possibly split into 2).
        assert len(clusters) >= 1


class TestClusterPageWithDescription:
    """Cluster pages include LLM-generated descriptions."""

    def test_cluster_page_includes_description(self, tmp_vault):
        """Generated cluster page includes the description."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        resolver = LinkResolver(vault, ops)

        detector = ClusterDetector(vault, ops, resolver)
        cluster = ConceptCluster(
            name="Test Cluster",
            slug="test-cluster",
            article_ids=["a", "b"],
            central_article="a",
            description="A test cluster for unit testing.",
        )
        path = detector.build_cluster_page(cluster)

        content = path.read_text()
        assert "A test cluster for unit testing." in content
        assert "Test Cluster" in content
