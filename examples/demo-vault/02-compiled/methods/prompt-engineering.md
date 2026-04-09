---
aliases: []
backlink_count: 0
confidence: 0.9
created: '2025-01-15T10:00:00+00:00'
id: prompt-engineering
read_time_min: 1
related:
- '[[large-language-models]]'
- '[[chain-of-thought]]'
- '[[rag]]'
source_count: 0
sources: []
status: draft
tags:
- prompting
- llm
- techniques
- ai
title: Prompt Engineering
type: method
updated: '2025-01-15T10:00:00+00:00'
version: 1
word_count: 243
---

> **TL;DR**: Prompt engineering is designing inputs to [[large-language-models]] for better outputs. Key techniques include few-shot, chain-of-thought, and structured format control.

## Core Techniques

### Zero-Shot
Just ask directly. Works for simple tasks with capable models.

### Few-Shot
Provide 2-5 examples of input → output format before the task.

### Chain-of-Thought (CoT)
Ask the model to "think step by step." Dramatically improves reasoning.

### System Prompts
Set behavior, persona, or constraints. Most powerful lever for control.

## Advanced Techniques

- **Tree-of-Thought (ToT)**: Explore multiple reasoning paths, pick the best
- **Self-Consistency**: Generate multiple CoT paths, take majority answer
- **ReAct**: Alternate between reasoning and tool use

## Practical Tips

1. **Be specific** — vague prompts → vague results
2. **Provide context** — more background = better output
3. **Iterate** — refine based on results
4. **Use delimiters** — ```, ###, XML tags to separate sections
5. **Positive instructions** — say what you want, not what you don't

## Anti-Patterns

- Overly long prompts (confuse the model)
- Contradictory instructions
- Assuming knowledge of recent events
- Ignoring token limits

## When to Prompt vs. Fine-Tune

**Prompt** when you need quick iteration, flexibility, no training budget.
**Fine-tune** when you need consistent style across thousands of calls, domain specificity.

## See Also

- [[large-language-models]]
- [[chain-of-thought]]
- [[rag]]
- [[fine-tuning]]
- [[hallucination]]

## References

- Wei et al. (2022). "Chain-of-Thought Prompting"
- Yao et al. (2023). "Tree of Thoughts"
- Yao et al. (2022). "ReAct"
