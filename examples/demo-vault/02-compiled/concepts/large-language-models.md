---
aliases: []
backlink_count: 0
confidence: 0.9
created: '2025-01-15T10:00:00+00:00'
id: large-language-models
read_time_min: 1
related:
- '[[transformer-architecture]]'
- '[[prompt-engineering]]'
- '[[fine-tuning]]'
- '[[rag]]'
source_count: 0
sources: []
status: draft
tags:
- llm
- ai
- nlp
- gpt
- claude
- open-source
title: Large Language Models
type: concept
updated: '2025-01-15T10:00:00+00:00'
version: 1
word_count: 281
---

> **TL;DR**: Large Language Models (LLMs) are [[transformer-architecture]] networks trained on massive text datasets. They learn to predict the next token, and at scale develop emergent capabilities like reasoning and code generation.

## How They Work

1. **Tokenization**: Text → tokens via BPE or SentencePiece
2. **Training**: Predict next token across billions of examples (self-supervised)
3. **Inference**: Generate autoregressively, one token at a time

### Sampling Strategies
- **Greedy**: Always pick most likely token
- **Top-k**: Sample from k most likely
- **Top-p (nucleus)**: Sample from smallest set exceeding probability p
- **Temperature**: Control distribution sharpness

## Major Families

### OpenAI GPT
- GPT-3 (2020): 175B params, few-shot learning
- GPT-4 (2023): Multimodal, improved reasoning

### Anthropic Claude
- Claude 3 (2024): Haiku/Sonnet/Opus tiers
- Constitutional AI approach to safety

### Open Source
- **Llama** (Meta): Pioneered open frontier models
- **Mistral**: Efficient, mixture-of-experts
- **Phi** (Microsoft): Small but capable

## Capabilities

- Write and debug code
- Analyze and summarize documents
- Translate between languages
- Answer questions across domains
- Reason mathematically
- Act as agents with tool use

## Limitations

- **Hallucination**: Confident but wrong outputs
- **Context window**: Finite token limit (128K-1M+)
- **Bias**: Reproduces training data biases
- **Cost**: Expensive to run at scale

## Adaptation Methods

- **Supervised Fine-Tuning (SFT)**: Task-specific training
- **RLHF**: Reinforcement learning from human feedback
- **LoRA/QLoRA**: Parameter-efficient fine-tuning
- **RAG**: Ground responses in real data at inference time

## See Also

- [[transformer-architecture]]
- [[prompt-engineering]]
- [[fine-tuning]]
- [[rag]]
- [[hallucination]]

## References

- Brown et al. (2020). "Language Models are Few-Shot Learners"
- Ouyang et al. (2022). "Training language models to follow instructions"
- Hu et al. (2021). "LoRA"
