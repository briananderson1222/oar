---
aliases: []
backlink_count: 0
confidence: 0.9
created: '2025-01-15T10:00:00+00:00'
id: transformer-architecture
read_time_min: 1
related:
- '[[attention-mechanisms]]'
- '[[large-language-models]]'
- '[[positional-encoding]]'
source_count: 0
sources: []
status: draft
tags:
- transformers
- neural-networks
- deep-learning
- attention
title: Transformer Architecture
type: concept
updated: '2025-01-15T10:00:00+00:00'
version: 1
word_count: 316
---

> **TL;DR**: The Transformer processes sequences entirely through [[attention-mechanisms]], abandoning recurrence. It is the foundation of [[large-language-models]] and modern AI.

## Overview

Introduced by Vaswani et al. in 2017 ("Attention Is All You Need"). The Transformer has become the dominant architecture in AI — GPT, BERT, Claude, and Llama are all Transformer variants.

## Key Components

### Encoder-Decoder Structure
- **Encoder**: Self-attention + feed-forward, processes input
- **Decoder**: Self-attention + cross-attention + feed-forward, generates output
- Modern variants use only encoder (BERT) or only decoder (GPT)

### Positional Encoding
Since attention is permutation-invariant, Transformers inject order through positional encodings:
- Sinusoidal (original): `PE(pos, i) = sin/cos(pos / 10000^(2i/d))`
- Learned embeddings (common)
- Rotary Position Embeddings (RoPE) — used in Llama

### Feed-Forward Network
Each layer: `FFN(x) = ReLU(xW₁ + b₁)W₂ + b₂`, typically 4x model dimension. Modern: SwiGLU for better performance.

### Layer Normalization
Stabilizes training. Pre-norm (normalize before residual) is more stable for deep networks than post-norm.

## Scaling Laws

Performance scales predictably with model size, data, and compute (Kaplan et al. 2020). This drove the trend toward larger models.

## Key Variants

| Model | Type | Key Innovation | Size |
|-------|------|---------------|------|
| BERT | Encoder | Bidirectional pretraining | 340M |
| GPT-3 | Decoder | Few-shot in-context learning | 175B |
| T5 | Enc-Dec | Text-to-text framework | 11B |
| ViT | Encoder | Patch-based image processing | 632M |
| Llama 2 | Decoder | Open-source, efficient | 7-70B |

## Efficiency Techniques

- **Flash Attention**: IO-aware attention, reduces memory reads/writes
- **KV Caching**: Cache key-value pairs during inference
- **Quantization**: INT8/INT4 for faster inference
- **Mixed Precision**: FP16/BF16 training

## See Also

- [[attention-mechanisms]]
- [[large-language-models]]
- [[positional-encoding]]
- [[fine-tuning]]
- [[prompt-engineering]]

## References

- Vaswani et al. (2017). "Attention Is All You Need"
- Devlin et al. (2018). "BERT"
- Brown et al. (2020). "GPT-3"
