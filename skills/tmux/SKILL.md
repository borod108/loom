---
name: tmux
description: "Run commands in tmux windows/panes within the current loom session. Use for interactive tools, dev servers, builds, SSH — anything that needs a separate terminal."
disable-model-invocation: false
allowed-tools:
  - Bash
---

# tmux Skill — Session-Aware Terminal Control

Run commands in tmux windows and panes within your current loom session.
Every command targets the current session only — never another session.

## Step 1: Detect Your Session

Before any tmux operation, detect the current session name.
If the session-start hook injected `SESSION SLUG: <slug>`, your session is `loom-<slug>`.
Otherwise, detect it dynamically:

```bash
SESSION=$(tmux display-message -p '#{session_name}')
```

All subsequent commands MUST use `-t "$SESSION:..."` targeting.
NEVER omit the session prefix — bare window/pane targets can hit the wrong session.

## Quick Reference

| Task | Command |
|------|---------|
| Detect session | `tmux display-message -p '#{session_name}'` |
| List windows | `tmux list-windows -t "$SESSION" -F '#{window_index}: #{window_name}'` |
| List panes | `tmux list-panes -t "$SESSION:$WINDOW" -F '#{pane_index}: #{pane_current_command}'` |
| Create window | `tmux new-window -t "$SESSION" -n "$NAME" -c "$DIR"` |
| Split pane | `tmux split-window -t "$SESSION:$WINDOW" -h -c "$DIR"` |
| Send keys | `tmux send-keys -t "$SESSION:$WINDOW" -- 'command text'` then `sleep 0.35` then `tmux send-keys -t "$SESSION:$WINDOW" Enter` |
| Capture output | `tmux capture-pane -p -t "$SESSION:$WINDOW" -S -200` |
| Kill window | `tmux kill-window -t "$SESSION:$WINDOW"` |
| Kill pane | `tmux kill-pane -t "$SESSION:$WINDOW.$PANE"` |

## Core Operations

### Create a Window

```bash
SESSION=$(tmux display-message -p '#{session_name}')
tmux new-window -t "$SESSION" -n dev-server -c /path/to/project
```

Always use `-n` to name the window. Always use `-c` to set the working directory.

### Send Keys (IMPORTANT: Enter must be separate)

Claude Code's TUI treats text+Enter in one `send-keys` call as a paste — the command
is typed but NOT submitted. Always send Enter as a separate call with a brief delay:

```bash
SESSION=$(tmux display-message -p '#{session_name}')
tmux send-keys -t "$SESSION:dev-server" -- 'npm start'
sleep 0.35
tmux send-keys -t "$SESSION:dev-server" Enter
```

For literal text (prevents tmux from interpreting special key names), use `-l`:

```bash
tmux send-keys -t "$SESSION:dev-server" -l -- 'echo "hello $USER"'
sleep 0.35
tmux send-keys -t "$SESSION:dev-server" Enter
```

For control keys, send them directly (these are tmux key names, not text):

```bash
tmux send-keys -t "$SESSION:dev-server" C-c      # Ctrl+C
tmux send-keys -t "$SESSION:dev-server" C-d      # Ctrl+D / EOF
tmux send-keys -t "$SESSION:dev-server" Escape   # ESC
```

### Capture Output

```bash
SESSION=$(tmux display-message -p '#{session_name}')
tmux capture-pane -p -t "$SESSION:dev-server" -S -200
```

`-S -200` includes 200 lines of scrollback. Use `-S -` for the full scrollback buffer.
For just the visible area, omit `-S`.

### Wait for Output

Poll for a pattern before proceeding (e.g., wait for a server to start):

```bash
SESSION=$(tmux display-message -p '#{session_name}')
TARGET="$SESSION:dev-server"
for i in $(seq 1 60); do
  if tmux capture-pane -p -t "$TARGET" -S -50 2>/dev/null | grep -q "ready on port"; then
    echo "Server is ready"
    break
  fi
  sleep 1
done
```

### Kill a Window

```bash
SESSION=$(tmux display-message -p '#{session_name}')
tmux kill-window -t "$SESSION:dev-server"
```

### Split a Pane

```bash
SESSION=$(tmux display-message -p '#{session_name}')
# Horizontal split (side by side)
tmux split-window -h -t "$SESSION:dev-server" -c /path/to/project
# Vertical split (top/bottom)
tmux split-window -v -t "$SESSION:dev-server" -c /path/to/project
```

## Targeting Rules

1. **Always include the session name**: `-t "$SESSION:window"`, never just `-t "window"`
2. **Target windows by NAME, not index**: `-t "$SESSION:dev-server"`, not `-t "$SESSION:1"` (indices depend on user's `base-index` setting)
3. **For panes, use window-name.pane-index**: `-t "$SESSION:dev-server.0"`
4. **After creating a pane**, use `tmux display-message -p -t "$SESSION:dev-server" '#{pane_index}'` to get its index if you need it

## Safety Rules

Before sending ANY command to a tmux pane, consider whether it is destructive or hard to reverse.

**ALWAYS ask the user before sending:**
- File deletion: `rm`, `rmdir`, `shred`
- Process killing: `kill`, `killall`, `pkill`
- Git destructive ops: `git push --force`, `git reset --hard`, `git clean -f`
- Database mutations: `DROP`, `DELETE`, `TRUNCATE`
- System changes: `systemctl stop/disable`, `shutdown`, `reboot`
- Broad permission changes: `chmod -R 777`, `chown -R`

**Safe to send without asking:**
- Read-only commands: `ls`, `cat`, `grep`, `find`, `git status/log/diff`
- Builds and tests: `make`, `go build`, `npm test`, `cargo build`
- Navigation: `cd`, `pwd`
- Starting dev servers, REPLs, or tools
- Environment setup: `export`, `source`

## Session Isolation Rules

- ONLY operate on the session returned by `tmux display-message -p '#{session_name}'`
- NEVER target a session by guessing or hardcoding a name
- NEVER use `tmux list-sessions` to find and target other sessions
- If the detected session name does not start with `loom-`, warn the user — you may not be in a loom-managed session
- If you need to interact with another loom task, tell the user to use `loom send <slug> <text>` from the CLI

## Common Recipes

### Run a dev server and monitor it

```bash
SESSION=$(tmux display-message -p '#{session_name}')
tmux new-window -t "$SESSION" -n server -c /path/to/project
tmux send-keys -t "$SESSION:server" -- 'npm run dev'
sleep 0.35
tmux send-keys -t "$SESSION:server" Enter

# Wait for it to start
for i in $(seq 1 30); do
  if tmux capture-pane -p -t "$SESSION:server" -S -50 | grep -qi "ready\|listening\|started"; then
    break
  fi
  sleep 1
done

# Check output
tmux capture-pane -p -t "$SESSION:server" -S -50
```

### Run a command and capture its output

```bash
SESSION=$(tmux display-message -p '#{session_name}')
tmux new-window -t "$SESSION" -n runner -c /path/to/project
tmux send-keys -t "$SESSION:runner" -- 'go test ./... 2>&1'
sleep 0.35
tmux send-keys -t "$SESSION:runner" Enter

# Wait for completion (shell prompt returns)
sleep 5
OUTPUT=$(tmux capture-pane -p -t "$SESSION:runner" -S -200)
echo "$OUTPUT"

# Clean up
tmux kill-window -t "$SESSION:runner"
```

### SSH into a remote host

```bash
SESSION=$(tmux display-message -p '#{session_name}')
tmux new-window -t "$SESSION" -n remote
tmux send-keys -t "$SESSION:remote" -- 'ssh user@host'
sleep 0.35
tmux send-keys -t "$SESSION:remote" Enter

# Wait for SSH connection
for i in $(seq 1 15); do
  if tmux capture-pane -p -t "$SESSION:remote" -S -10 | grep -q '\$\|#\|%\|>'; then
    break
  fi
  sleep 1
done

tmux capture-pane -p -t "$SESSION:remote" -S -20
```

### Interactive REPL (Python, Node, etc.)

```bash
SESSION=$(tmux display-message -p '#{session_name}')
tmux new-window -t "$SESSION" -n repl -c /path/to/project

# Python: use PYTHON_BASIC_REPL to prevent readline interference with send-keys
tmux send-keys -t "$SESSION:repl" -- 'PYTHON_BASIC_REPL=1 python3'
sleep 0.35
tmux send-keys -t "$SESSION:repl" Enter

# Wait for prompt
for i in $(seq 1 10); do
  if tmux capture-pane -p -t "$SESSION:repl" | grep -q '>>>'; then break; fi
  sleep 0.5
done

# Send code
tmux send-keys -t "$SESSION:repl" -l -- 'print("hello from python")'
sleep 0.35
tmux send-keys -t "$SESSION:repl" Enter
sleep 0.5

# Read output
tmux capture-pane -p -t "$SESSION:repl" -S -20

# Clean up
tmux send-keys -t "$SESSION:repl" C-d
sleep 0.5
tmux kill-window -t "$SESSION:repl"
```

## Troubleshooting

**"can't find window" or "session not found"**
Re-detect the session: `tmux display-message -p '#{session_name}'`. The session may have
been killed or you may be in a different context after compaction.

**Commands typed but not executed**
You forgot to send Enter separately. Always: `send-keys -- 'text'`, then `sleep 0.35`, then `send-keys Enter`.

**Output seems stale or empty**
Add a `sleep 1` before `capture-pane` to let the command finish. Use `-S -200` to include scrollback.

**Window indices don't match**
The user's `base-index` or `pane-base-index` setting can shift indices. Always target by window name, not index.
