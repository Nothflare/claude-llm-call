---
name: llm-call
description: External LLM invocation. Triggered ONLY by @council, @gpt, @gemini, @grok. Claude remains primary—external models complement, don't replace.
---

# LLM Call

External LLM access. **Only activates on explicit triggers.**

## Triggers

| Trigger | Action |
|---------|--------|
| `@council` | Query GPT-5.1, Gemini 3 Pro, Grok 4.1 Fast |
| `@gpt` | GPT-5.1 Thinking only |
| `@gemini` | Gemini 3 Pro only |
| `@grok` | Grok 4.1 Fast only |

No trigger → Claude handles alone.

## Why This Pattern Exists

**The value is independent perspective, not review.**

If Claude shows its draft to external models, they anchor on it. Instead:
1. Claude forms complete answer first
2. External models answer the same question independently (they never see Claude's draft)
3. Claude compares all answers afterward

This serves different purposes depending on the task:

**For analytical/factual problems → Convergence signal:**
- 4 models independently reach same conclusion → high confidence
- 3 models agree, Claude differs → Claude likely wrong
- Models disagree with each other → genuinely hard, needs deeper analysis

**For creative/ideation tasks → Divergence signal:**
- Different models surface different framings, angles, and possibilities
- Disagreement is a feature—it expands the solution space
- Each model has different training biases; diversity reduces blind spots
- Claude synthesizes the best elements rather than picking a winner

**For exploration/brainstorming → Coverage signal:**
- Multiple models thinking independently cover more territory
- Surfaces assumptions Claude didn't know it was making
- Useful when you don't know what you don't know

**External models cannot:** search web, use tools, see files, or access conversation history. Claude must include all relevant context in the query.

## The `-c` Flag (Confidence)

**What it does:** Asks each model to rate its confidence and explain what would change its answer.

**When to use it:**
- Factual/analytical questions where certainty matters
- To surface what evidence each model is relying on

## Workflow - Follow STRICTLY

### Single Model (`@gpt`, `@gemini`, `@grok`)

```bash
# 1. Claude forms own answer (keep in working memory or write to file)

# 2. Write query with context for external model
cat > /tmp/query.txt << 'QUERY'
Question: [user's question]
Context: [relevant facts from search, doc summaries, constraints]
QUERY

# 3. Call model (add -c for confidence on analytical questions)
python3 /mnt/skills/user/llm-call/cli.py -m single -M gpt -f /tmp/query.txt

# 4. Compare response to own answer → output final answer to user
```

### Council (`@council`)

```bash
# 1. Claude forms own complete answer first
cat > /tmp/draft.txt << 'DRAFT'
[Claude's complete answer with reasoning]
DRAFT

# 2. Write query (question + context, NOT Claude's draft)
cat > /tmp/query.txt << 'QUERY'
Question: [user's question]  
Context: [search results, doc summaries, constraints]
QUERY

# 3. Init session (creates fresh session each time)
python3 /mnt/skills/user/llm-call/cli.py -m init -f /tmp/query.txt

# 4. Store draft in session (for display in context view, NOT sent to models)
python3 /mnt/skills/user/llm-call/cli.py -m draft -f /tmp/draft.txt

# 5. Dispatch to all models
# Add -c for analytical problems where confidence calibration matters
python3 /mnt/skills/user/llm-call/cli.py -m council -c

# 6. View everything: query + Claude's draft + all model responses
python3 /mnt/skills/user/llm-call/cli.py -m context

# 7. Compare and output final answer to user
```

## Interpreting Results

### Analytical/Factual Tasks

| Pattern | Signal | Action |
|---------|--------|--------|
| All agree with Claude | Strong confirmation | Proceed confidently |
| Models agree, Claude differs | Claude likely wrong | Investigate, probably update |
| Models disagree with each other | Hard problem | Analyze the disagreement |
| One model has unique insight | Potential blind spot | Evaluate, incorporate if valid |

### Creative/Ideation Tasks

| Pattern | Signal | Action |
|---------|--------|--------|
| All similar outputs | Obvious solution space | Push for more divergent framing |
| Diverse outputs | Good coverage | Synthesize best elements |
| One model takes unusual angle | Interesting possibility | Explore whether it opens new directions |
| Models cluster into 2-3 camps | Natural solution categories | Present options with tradeoffs |

### Exploration/Brainstorming

| Pattern | Signal | Action |
|---------|--------|--------|
| Models surface different assumptions | Assumption diversity | Make implicit assumptions explicit |
| One model asks clarifying questions | Ambiguity detected | Address the ambiguity |
| Models focus on different aspects | Multifaceted problem | Ensure all aspects are covered |

## Script Reference

| Mode | Purpose |
|------|---------|
| `single -M <model>` | Query one model |
| `init` | Start new session |
| `draft` | Store Claude's draft in session |
| `council` | Query all 3 models |
| `context` | Display draft + all responses |
| `probe -M <model>` | Follow-up question to one model |
| `clear` | Delete current session |

Options: `-M gpt|gemini|grok`, `-c` (request confidence levels), `-q` (quiet), `-f file`