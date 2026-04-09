---
aliases: []
backlink_count: 0
confidence: 0.9
created: '2025-01-15T10:00:00+00:00'
id: attention-mechanisms
read_time_min: 1
related:
- '[[transformer-architecture]]'
- '[[large-language-models]]'
source_count: 0
sources: []
status: draft
tags:
- attention
- neural-networks
- deep-learning
- transformers
title: Attention Mechanisms
type: concept
updated: '2025-01-15T10:00:00+00:00'
version: 1
word_count: 172
---

> **TL;DR**: Attention mechanisms allow neural networks to dynamically focus on the most relevant parts of their input, enabling the [[transformer-architecture]] that powers modern AI.

## Overview

Attention mechanisms are a fundamental component of modern neural networks. Rather than compressing entire sequences into fixed-length vectors, attention allows models to selectively emphasize the most relevant information.

The core idea: compute a weighted sum of **values**, where weights come from the compatibility between a **query** and a set of **keys**.

```
Attention(Q, K, V) = softmax(QK^T / sqrt(d_k)) * V
```

## Types of Attention

- **Self-attention**: Q, K, V all come from the same sequence
- **Cross-attention**: Q from decoder, K/V from encoder
- **Multi-head attention**: Multiple parallel attention ops with different projections

## Applications

1. **NLP**: Machine translation, summarization, Q&A
2. **Computer Vision**: Vision Transformers, image captioning
3. **Speech**: Conformer models, speech translation
4. **Genomics**: Protein structure prediction (AlphaFold)

## See Also

- [[transformer-architecture]]
- [[self-attention]]
- [[multi-head-attention]]
- [[positional-encoding]]

## References

- Bahdanau et al. (2014) - Vaswani et al. (2017)
