---
aliases: []
backlink_count: 0
confidence: 0.9
created: '2025-01-15T10:00:00+00:00'
id: vector-databases
read_time_min: 1
related:
- '[[retrieval-augmented-generation]]'
- '[[embeddings]]'
source_count: 0
sources: []
status: draft
tags:
- databases
- vectors
- embeddings
- similarity-search
title: Vector Databases
type: concept
updated: '2025-01-15T10:00:00+00:00'
version: 1
word_count: 258
---

> **TL;DR**: Vector databases store and search high-dimensional vector [[embeddings]], enabling similarity search that powers [[retrieval-augmented-generation]] and recommendation systems.

## What Are Vector Databases?

Specialized databases optimized for storing, indexing, and querying high-dimensional vectors (typically 128-1536 dimensions). They enable "find me things similar to this" queries at scale.

## Core Concepts

### Embeddings
Text, images, or other data converted to dense vectors by neural networks. Similar items have vectors close together in the embedding space.

### Similarity Metrics
- **Cosine similarity**: Angle between vectors (most common)
- **Euclidean distance**: Straight-line distance
- **Dot product**: Simple and fast

### Indexing Algorithms
- **HNSW** (Hierarchical Navigable Small World): Graph-based, fast approximate nearest neighbor
- **IVF** (Inverted File Index): Partition space into clusters
- **PQ** (Product Quantization): Compress vectors for memory efficiency

## Popular Vector Databases

| Database | Type | Key Feature |
|----------|------|-------------|
| Pinecone | Managed | Fully managed, serverless |
| Weaviate | Open-source | Hybrid search (vector + keyword) |
| Qdrant | Open-source | Rust-based, high performance |
| ChromaDB | Open-source | Python-native, easy setup |
| Milvus | Open-source | Scales to billions of vectors |
| pgvector | Extension | PostgreSQL extension |

## Use Cases

1. **Semantic search**: Find documents by meaning, not keywords
2. **[[retrieval-augmented-generation|RAG]]**: Ground LLM responses in real data
3. **Recommendations**: Find similar items/users
4. **Deduplication**: Detect near-duplicate content
5. **Anomaly detection**: Find outliers in embedding space

## See Also

- [[retrieval-augmented-generation]]
- [[embeddings]]
- [[similarity-search]]

## References

- Johnson et al. (2019). "Billion-scale similarity search with GPUs"
