---
number: 11
title: Name the tool "loom"
status: accepted
date: 2026-07-05
---

# ADR-011: Name the tool "loom"

## Context

From §9 of the design brief. Candidates: Loom, Weft, Mycelium, Atrium, Tesserae, Conductor.

Design brief's reasoning for Loom: "tmux threads woven into fabric; short; verb-able ('loom new auth-fix')." Note: loom.com (video tool) exists, but an OSS CLI with a different purpose is acceptable.

User choice: Loom.

## Decision

The tool is named **loom**. CLI binary: `loom`. tmux session prefix: `loom-<slug>`. Config dir: `~/.config/loom/`. State dir: `~/.local/state/loom/`. Vault dir: user-configured (default `~/vault`).

The name is short, memorable, verb-able, and evokes the weaving metaphor: many threads of work woven into a coherent picture, with a memory (the vault) that persists across sessions.

## Consequences

- No `loom` binary name collision in common Linux distributions (verified 2026-07-05).
- loom.com is a different category (video tool vs. CLI) — no trademark conflict for personal OSS tooling.

## Status History

- 2026-07-05: accepted
