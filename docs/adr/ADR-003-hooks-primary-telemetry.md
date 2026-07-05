---
number: 3
title: Claude Code hooks are the primary telemetry source
status: accepted
date: 2026-07-05
---

# ADR-003: Claude Code hooks are the primary telemetry source

## Context

Two options exist for tracking task status (working / waiting / idle):
1. **Hooks**: Claude Code fires `UserPromptSubmit` (→ working) and `Stop` (→ waiting) reliably.
2. **`tmux capture-pane` scraping**: Read the visual output of the Claude pane and infer status from the prompt area. Used by prior art like `tmux-claude-session-manager`.

## Decision

Hooks are the primary telemetry source. `capture-pane` is used only as a secondary enhancement where it adds accuracy — specifically for the web UI's live pane preview, not for status inference.

## Consequences

**Positive:**
- Hook-based status is accurate and event-driven, not polled.
- No fragile screen-scraping logic.
- Works regardless of terminal rendering details.

**Negative / trade-offs:**
- Hooks must be installed (once, by `install.sh`). Without hooks, status tracking degrades to "last seen" from vault frontmatter.
- Sessions started outside loom have hooks fire too; the `session-start.py` hook auto-registers them as "unmanaged" tasks.

## Status History

- 2026-07-05: accepted
