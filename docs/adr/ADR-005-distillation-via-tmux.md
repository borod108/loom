---
number: 5
title: Distillation via interactive tmux window, not headless API
status: accepted
date: 2026-07-05
---

# ADR-005: Distillation via interactive tmux window, not headless API

## Context

When a task session ends or context is compacted, loom can distill a summary: what was accomplished, key decisions, research findings. Two mechanisms:
1. **Headless `claude -p "summarize…"`**: fires an API call behind the scenes. Transparent to user. Costs tokens as a separate call.
2. **Interactive tmux window**: opens a `distill` window in the task's session, resumes Claude there, user sees and controls the summarization. Same token cost as a normal interactive turn.

## Decision

Distillation opens an interactive window in the task's tmux session. The user can review, correct, and copy the summary to the vault. This is more transparent, controllable, and does not add a hidden API call.

Configurable: `LOOM_DISTILL=auto` (default) runs on `PreCompact` and `loom done`. `manual` runs only on `loom done`. `off` disables it.

## Consequences

**Positive:**
- User can see and guide the distillation.
- No surprise API costs.
- Summary quality is higher because the user can iterate.

**Negative / trade-offs:**
- Requires the user to actively review the distillation window.
- Does not produce a fully automated vault note without user interaction.

**Future option:** if the user wants fully automated distillation, headless mode can be added behind the `LOOM_DISTILL=headless` config value.

## Status History

- 2026-07-05: accepted
