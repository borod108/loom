---
number: 8
title: Central skills library via symlinks into ~/.claude/skills/
status: accepted
date: 2026-07-05
---

# ADR-008: Central skills library via symlinks into ~/.claude/skills/

## Context

Claude Code supports skills (slash commands) at multiple scopes: `~/.claude/skills/` (user-wide) and `.claude/skills/` (project). Skills can also be packaged as plugins. Symlinks are officially supported.

Goal: keep the canonical skill library in the loom git repo so editing the repo updates all linked skills immediately. Claude Code live-reloads `SKILL.md` changes within a running session.

## Decision

`install.sh` symlinks each directory under `<loom>/skills/` into `~/.claude/skills/`. This makes every loom skill available in all Claude Code sessions machine-wide. Adding a new skill to the repo + re-running `install.sh` is the update mechanism.

Plugin packaging (proper `plugin.json`, marketplace listing) is deferred to v2. The `skills/` directory structure is already compatible with the plugin format.

Project-level skills (`.claude/skills/` inside work repos) are not used by default, but the user can add symlinks manually if they want task-specific skills.

## Consequences

**Positive:**
- No install step needed to update skills — editing the file is the update.
- Works across all projects immediately.

**Negative / trade-offs:**
- All loom skills are always available (no per-project scoping). Acceptable for personal tooling.
- Symlinks require loom to remain at a stable path after install. Moving the repo requires re-running `install.sh`.

## Status History

- 2026-07-05: accepted
