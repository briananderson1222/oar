---
aliases: []
backlink_count: 0
confidence: 0.9
created: '2025-01-15T10:00:00+00:00'
id: fine-tuning-llms
read_time_min: 1
related:
- '[[large-language-models]]'
- '[[prompt-engineering]]'
- '[[lora]]'
source_count: 0
sources: []
status: draft
tags:
- fine-tuning
- llm
- training
- adaptation
title: Fine-Tuning LLMs
type: method
updated: '2025-01-15T10:00:00+00:00'
version: 1
word_count: 267
---

> **TL;DR**: Fine-tuning adapts pre-trained [[large-language-models]] to specific tasks or domains. Methods range from full fine-tuning to parameter-efficient approaches like [[lora]].

## Why Fine-Tune?

Pre-trained LLMs are general-purpose. Fine-tuning specializes them for:
- Domain-specific language (medical, legal, technical)
- Consistent output format (JSON, SQL, specific schemas)
- Company-specific knowledge and style
- Improved performance on narrow tasks

## Methods

### Full Fine-Tuning
Update all model parameters. Expensive (requires multi-GPU setup) but most flexible.

### Parameter-Efficient Fine-Tuning (PEFT)
Update only a small number of parameters while keeping the base model frozen.

- **[[lora|LoRA]]**: Low-rank adaptation matrices — train <1% of parameters
- **QLoRA**: Quantized LoRA — fine-tune on consumer GPUs
- **Prefix tuning**: Learn soft prompts prepended to input
- **Adapters**: Small modules inserted between transformer layers

### Supervised Fine-Tuning (SFT)
Train on input-output pairs. Direct and effective for task specialization.

### RLHF
Reinforcement Learning from Human Feedback:
1. Collect human preference data
2. Train a reward model
3. Optimize the LLM against the reward model using PPO

## Practical Considerations

- **Data quality** matters more than quantity (1000 good examples > 100K mediocre ones)
- **Catastrophic forgetting**: Fine-tuning can degrade general capabilities
- **Evaluation**: Always hold out a test set, measure on your specific task
- **Cost**: LoRA on a 7B model can run on a single consumer GPU

## When to Fine-Tune vs. Prompt

See [[prompt-engineering]] for the comparison framework.

## See Also

- [[large-language-models]]
- [[prompt-engineering]]
- [[lora]]
- [[rlhf]]

## References

- Hu et al. (2021). "LoRA: Low-Rank Adaptation of Large Language Models"
- Ouyang et al. (2022). "Training language models to follow instructions"
