---
aliases: []
backlink_count: 0
confidence: 0.9
created: '2025-01-15T10:00:00+00:00'
id: retrieval-augmented-generation
read_time_min: 1
related:
- '[[large-language-models]]'
- '[[vector-databases]]'
- '[[embeddings]]'
- '[[prompt-engineering]]'
source_count: 0
sources: []
status: draft
tags:
- rag
- retrieval
- llm
- knowledge-base
- vectors
title: Retrieval Augmented Generation
type: concept
updated: '2025-01-15T10:00:00+00:00'
version: 1
word_count: 250
---

> **TL;DR**: RAG (Retrieval Augmented Generation) grounds [[large-language-models]] in real data by retrieving relevant documents at inference time and injecting them into the context. This reduces [[hallucination]] without fine-tuning.

## How RAG Works

1. **Index**: Convert documents into vector [[embeddings]], store in [[vector-databases]]
2. **Retrieve**: When a query comes in, find the most similar documents via vector search
3. **Augment**: Insert retrieved documents into the LLM prompt as context
4. **Generate**: LLM answers using both its knowledge and the retrieved context

## Why RAG?

- **Reduces hallucination**: Model answers from real documents, not memorized patterns
- **No retraining**: Update knowledge by updating the document store
- **Citable**: Can trace answers back to source documents
- **Cost-effective**: Cheaper than fine-tuning on new data

## RAG vs. Alternatives

| Approach | Cost | Freshness | Accuracy | Complexity |
|----------|------|-----------|----------|------------|
| Pure LLM | Low | Static | Medium | Low |
| Fine-tuning | High | Slow | High | High |
| RAG | Medium | Real-time | High | Medium |

## Advanced RAG Patterns

- **Query rewriting**: Transform the user query for better retrieval
- **Re-ranking**: Use a second model to re-score retrieved documents
- **Hybrid search**: Combine vector search with keyword (BM25) search
- **Chunking strategies**: Split documents into optimal-sized pieces
- **Multi-hop retrieval**: Retrieve iteratively for complex questions

## See Also

- [[large-language-models]]
- [[vector-databases]]
- [[embeddings]]
- [[prompt-engineering]]
- [[hallucination]]
- [[fine-tuning]]

## References

- Lewis et al. (2020). "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
