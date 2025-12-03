# Claude LLM Call

A Claude skill for querying external LLMs (GPT, Gemini, Grok) to get independent perspectives on problems.

## Why?

When you show your draft to someone, they anchor on it. Instead:

1. Claude forms its own complete answer first
2. External models answer the same question independently (never see Claude's draft)  
3. Claude compares all answers afterward

This surfaces blind spots, validates reasoning, and expands solution spaces.

## Installation

1. Clone this repo
2. Edit `config.py` with your API key and endpoint
3. Delete this README.md
4. Compress the repo into a .zip file and upload it to (https://claude.ai/settings/capabilities)[https://claude.ai/settings/capabilities]

## Triggers (Claude will use this skill when one is present)

| Trigger | Action |
|---------|--------|
| `@council` | Query GPT, Gemini, Grok in parallel |
| `@gpt` | GPT only |
| `@gemini` | Gemini only |
| `@grok` | Grok only |

No trigger → Claude handles alone.

## Features

- **Parallel execution** — All council models queried simultaneously
- **Session management** — Persists queries, drafts, and responses
- **Probe mode** — Follow-up questions with full context
- **Confidence mode** — Ask models to rate their certainty
- **CoT stripping** — Automatically removes `<think>` reasoning blocks
- **Zero dependencies** — Pure Python stdlib

## Limitations

External models **cannot**:
- Search the web
- Use tools
- See files
- Access conversation history

Claude must include all relevant context in the query.