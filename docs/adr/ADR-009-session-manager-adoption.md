---
number: 9
title: Adopt tmux-claude-session-manager patterns behind an abstraction layer
status: accepted
date: 2026-07-05
---

# ADR-009: Adopt tmux-claude-session-manager patterns behind an abstraction layer

## Context

`craftzdog/tmux-claude-session-manager` (https://github.com/craftzdog/tmux-claude-session-manager) is the closest existing tool to loom's Goal 1. It provides: one Claude session per tmux session, fzf-style popup listing with live working/waiting/idle status detection, jump-to-session. Its status detection uses capture-pane scraping.

Loom supersedes capture-pane scraping with hooks (ADR-003) but can borrow the design patterns: session naming, the popup picker concept, and the status-detection test approach.

## Decision

Loom does NOT vendor or depend on tmux-claude-session-manager as a library (it's a tmux plugin, not a Python library). Instead:
1. Loom's `TmuxManager` class abstracts all tmux session operations behind a stable Python API.
2. A test suite (`tests/test_status.sh`, `tests/test_vault.py`) validates the behaviors we depend on.
3. If a better session management implementation exists, only `TmuxManager` needs to change — not the CLI or web UI.

The test suite is explicitly designed to be implementation-agnostic: it tests the *behaviors* (session creates, status updates, pane capture) not the internal mechanism.

## Consequences

**Positive:**
- We can swap the session management implementation without touching other code.
- The test suite gives confidence before and after any swap.

**Negative / trade-offs:**
- We don't get the fzf popup UI for free — it would be a separate addition (using `tmux display-popup` + `loom ls`).

**Future (v2):** A `loom popup` command using `tmux display-popup` to show an fzf-style picker.

## Status History

- 2026-07-05: accepted
