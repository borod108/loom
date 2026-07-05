---
number: 7
title: Git is the vault sync mechanism
status: accepted
date: 2026-07-05
---

# ADR-007: Git is the vault sync mechanism

## Context

The vault must be installable by others (each person with their own vault) and syncable across machines. Options: git, Syncthing, Obsidian Sync (proprietary), rsync.

User's answer: git. One vault per person, synced via git. Not necessarily the same tasks across machines.

## Decision

The vault is a git repository initialized by `loom init`. `loom sync` runs:
1. `git add -A` (stage all changes)
2. `git commit -m "loom: auto-sync <timestamp>"` (if anything changed)
3. `git pull --rebase` (fetch remote changes)
4. `git push` (push local commits)

Each user configures their own remote (e.g., a private GitHub/GitLab repo). `install.sh` does not configure the remote — the user does this once manually.

## Consequences

**Positive:**
- Simple, universally available.
- Full history of the vault (including deleted task notes in archive).
- Merge conflicts resolve with standard git tools.

**Negative / trade-offs:**
- Requires the user to set up a git remote and handle auth (SSH key or token).
- Concurrent writes from multiple machines can create merge conflicts in Active Tasks.md. Mitigated by: `loom sync` uses `--rebase`; the dashboard is auto-generated so conflicts in it can always be resolved by re-running `loom rebuild`.

## Status History

- 2026-07-05: accepted
