---
number: 1
title: One tmux session per task
status: accepted
date: 2026-07-05
---

# ADR-001: One tmux session per task

## Context

Tasks often span multiple tmux windows/panes (Claude in one, logs in another, dev server in a third). Notifications and external tooling need to target the right tmux context. Targeting a specific window or pane from outside tmux (`session:window.pane`) is unreliable — terminal emulators and notification handlers can't navigate to a window, only to a session.

The user independently reached this conclusion before design began.

## Decision

Each loom task maps to exactly one tmux session, named `<prefix>-<slug>` (default prefix: `loom`). Window 0, pane 0 of that session is always the canonical Claude prompt. Additional windows/panes within the session are task-local resources (dev server, logs, distillation).

## Consequences

**Positive:**
- `tmux switch-client -t <session>` and `tmux attach -t <session>` work reliably from anywhere.
- Notifications can deep-link to a session by name.
- `capture-pane -t <session>:0.0` always gives the Claude prompt area.

**Negative / trade-offs:**
- Users working on many tasks simultaneously create many tmux sessions (acceptable; tmux handles 50+ fine).
- Session names must be unique; `loom new` enforces this.

## Status History

- 2026-07-05: accepted (confirmed by user during design)
