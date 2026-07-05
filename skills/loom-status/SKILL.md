---
name: loom-status
description: Show the current loom task status from inside a Claude session.
disable-model-invocation: false
allowed-tools:
  - Bash
---

Show the current task's status and context from the vault.

## What to do

1. Find the current session's task by reading the `session_id` from the environment or hook context.
2. Look up the corresponding task note in the vault (`~/vault/10-Tasks/`).
3. Show:
   - Task slug and goal
   - Current status
   - Recent log entries
   - Any compaction checkpoints (prior context snapshots)
4. If the vault is not available, fall back to: `loom ls` via Bash.

## Commands available

```bash
loom ls              # list all active tasks
loom preview <slug>  # show current pane state
loom rebuild         # rebuild cache from vault
```

## Output format

Keep it short. One block with task name, goal, status, and last 3 log entries.
