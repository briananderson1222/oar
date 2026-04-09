---
aliases: []
backlink_count: 0
confidence: 0.9
created: '2025-01-15T10:00:00+00:00'
id: embeddings
read_time_min: 1
related:
- '[[vector-databases]]'
- '[[retrieval-augmented-generation]]'
- '[[transformer-architecture]]'
source_count: 0
sources: []
status: draft
tags:
- embeddings
- vectors
- representations
- deep-learning
title: Embeddings
type: concept
updated: '2025-01-15T10:00:00+00:00'
version: 1
word_count: 231
---

> **TL;DR**: Embeddings are dense vector representations that capture semantic meaning. They power [[vector-databases|vector search]], [[retrieval-augmented-generation|RAG]], and are fundamental to how [[transformer-architecture|transformers]] process language.

## What Are Embeddings?

Embeddings map discrete items (words, sentences, images) to dense vectors in a continuous space, where similar items are close together. A word embedding might be a 768-dimensional vector where "dog" and "puppy" have similar representations.

## Types

### Word Embeddings
- **Word2Vec** (2013): First popular method, shallow neural network
- **GloVe** (2014): Global co-occurrence statistics
- **FastText** (2017): Subword information, handles OOV words

### Contextual Embeddings
- **BERT embeddings**: Different vector for each context (bank as financial vs. river)
- Sentence transformers: Optimized for sentence-level similarity

### Multimodal Embeddings
- **CLIP**: Joint text-image embedding space
- Image embeddings for visual similarity search

## Properties

- **Dimensionality**: Typically 128-1536 dimensions
- **Distance metrics**: Cosine similarity, Euclidean, dot product
- **Training**: Self-supervised on massive corpora, or contrastive learning

## Popular Models

| Model | Dimensions | Best For |
|-------|-----------|----------|
| OpenAI text-embedding-3-small | 1536 | General purpose |
| all-MiniLM-L6-v2 | 384 | Fast, lightweight |
| BGE-large | 1024 | High accuracy |
| Cohere embed-v3 | 1024 | Multilingual |

## See Also

- [[vector-databases]]
- [[retrieval-augmented-generation]]
- [[transformer-architecture]]
- [[similarity-search]]

## References

- Mikolov et al. (2013). "Efficient Estimation of Word Representations in Vector Space"
- Pennington et al. (2014). "GloVe"
