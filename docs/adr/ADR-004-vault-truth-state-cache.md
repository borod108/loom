---
number: 4
title: Vault frontmatter is truth; tasks.json is a generated cache
status: accepted
date: 2026-07-05
---

# ADR-004: Vault frontmatter is truth; tasks.json is a generated cache

## Context

Two candidates for the source of truth for task state:
- **Vault frontmatter**: each task note has `status`, `session_id`, `cwd`, etc. in its YAML frontmatter. Human-readable, git-versioned, searchable by Claude.
- **`tasks.json`**: a compact JSON index under `~/.local/state/loom/`. Fast to read for `loom ls` and the web UI. Atomic updates. But duplicates vault data.

Pros/cons:
| | Vault frontmatter | tasks.json |
|---|---|---|
| Source of truth | ✓ Single source | ✗ Duplicate |
| Speed | ✗ Parse all .md files | ✓ One JSON file |
| Survives loss | ✓ (it IS the data) | ✗ Rebuilt from vault |
| Claude-searchable | ✓ | Partial |

## Decision

Both. Vault frontmatter is the canonical record. `tasks.json` is a generated index rebuilt by hooks and `loom rebuild`. Hooks update both atomically (vault first, then cache). If the cache is deleted or drifts, `loom rebuild` regenerates it in seconds.

## Consequences

**Positive:**
- `loom ls` and the web UI are fast (read one JSON file).
- The vault is the second-brain record; knowledge survives the cache.
- `loom rebuild` is the recovery mechanism for any sync issue.

**Negative / trade-offs:**
- Two writes per status update (minor; both are local file writes).
- The cache can theoretically drift if a hook errors mid-write. Mitigated by: hooks write vault first, then cache; `loom rebuild` at session start syncs them.

## Status History

- 2026-07-05: accepted
