---
name: recall
description: Search the loom vault for prior decisions, research, and session notes before starting work.
disable-model-invocation: false
allowed-tools:
  - Glob
  - Grep
  - Read
---

Search the loom vault for relevant prior work, decisions, and research on the given topic.

## What to do

1. Identify the search terms from the user's request.
2. Search `$LOOM_VAULT` (or `~/vault` if not set) using Glob and Grep:
   - `30-Decisions/` for ADRs — decisions that shape how work is done
   - `40-Research/` for evergreen research findings
   - `10-Tasks/` for related past tasks (check their summaries)
   - `00-Dashboard/` for the active task list
3. Read the most relevant notes (top 3-5 by relevance).
4. Summarize what was found: prior decisions that apply, research that's relevant, tasks that overlapped.
5. If nothing relevant is found, say so clearly — do not invent prior work.

## Output format

```
## Prior work found

### Decisions
- [[ADR-NNN]]: <one-line summary of why it applies>

### Research
- [[topic]]: <key finding>

### Related tasks
- [[task-slug]]: <what was done there>

### Summary
<2-3 sentences on what this prior work means for the current task>
```

## When to use

Run at the start of a new task or when the user asks "have we done this before?" or "what do we know about X?"
