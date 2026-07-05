# loom Test Plan

## 1. Unit Tests (no tmux required)

Run: `python3 -m unittest tests/test_vault.py tests/test_state.py -v`

### 1.1 VaultManager
- [x] `create_task` — creates file with correct frontmatter (session_id, model, status=starting)
- [x] `create_task` — raises `FileExistsError` on duplicate slug
- [x] `get_task` — reads active and archived tasks
- [x] `update_task` — updates frontmatter fields, bumps `updated`
- [x] `list_tasks` — returns active tasks by default
- [x] `list_tasks(include_archived=True)` — returns active + archived
- [x] `find_by_session_id` — locates task by UUID
- [x] `archive_task` — moves to 90-Archive/, rebuilds dashboard
- [x] `link_doc` — appends wikilink to Linked Documents section
- [x] `rebuild_dashboard` — writes Active Tasks.md correctly
- [x] `next_adr_number` — increments correctly
- [x] `is_initialized` / `init` — vault structure and git init

### 1.2 StateManager
- [x] `upsert` — creates and updates entries
- [x] `get` — returns correct entry
- [x] `remove` — removes entry
- [x] `list_all` — returns all entries
- [x] `rebuild_from_vault` — regenerates tasks.json
- [x] Atomic write — no leftover .tmp files

### 1.3 Utility functions
- [x] `slugify` — normalizes text to slug
- [x] `format_age` — formats seconds/minutes/hours/days correctly

---

## 2. Integration Tests (requires tmux)

Run: `bash tests/test_status.sh --verbose`

### 2.1 TmuxManager session lifecycle
- [x] `session_exists` returns False for unknown slug
- [x] `new_session` creates tmux session
- [x] `session_exists` returns True for running session
- [x] `capture_pane` returns string
- [x] `send_keys` returns True for live session
- [x] `kill_session` removes the tmux session
- [x] `list_sessions` filters to loom-prefixed sessions only

---

## 3. CLI Feature Tests (manual / scripted)

Run: `bash tests/test_cli.sh`

### 3.1 `loom init`
- [ ] Creates vault directory structure (00-Dashboard through 90-Archive)
- [ ] Creates git repo (unless --no-git)
- [ ] Idempotent: safe to run twice

### 3.2 `loom new`
- [ ] Creates task with correct vault note (session_id, model, goal in frontmatter)
- [ ] Creates tmux session named `loom-<slug>`
- [ ] Launches `claude --model <model> --session-id <uuid>` in window 0
- [ ] With `--goal`: sends goal to Claude once prompt is visible
- [ ] With `--model opus`: skips picker, uses specified model
- [ ] Without `--model` in non-TTY: uses LOOM_DEFAULT_MODEL
- [ ] Duplicate slug: fails with clear error, session still exists
- [ ] Session state: `loom ls` shows task with `starting` status

### 3.3 `loom ls`
- [ ] Shows active tasks (status, project, age, cwd)
- [ ] Dead session (tmux killed) shows status=`dead` with red ✗
- [ ] Done task does NOT appear by default
- [ ] `--all` shows done/archived tasks (dimmed)
- [ ] `--plain` produces clean output for fzf (no ANSI)
- [ ] Empty vault shows "No active tasks."

### 3.4 `loom go`
- [ ] Inside tmux: runs `switch-client` to the task session
- [ ] Outside tmux: attaches to the session
- [ ] Dead session: prints helpful message with `loom resume` hint

### 3.5 `loom resume`
- [ ] Session exists, Claude running: switches to it
- [ ] Session exists, no Claude: sends `claude --resume <id>`
- [ ] Session doesn't exist: creates new session with `claude --resume <id>`
- [ ] Passes model from vault frontmatter to `claude --model`

### 3.6 `loom done`
- [ ] Kills tmux session
- [ ] Moves vault note to 90-Archive/
- [ ] Updates state to `status=done` (not removed)
- [ ] Task appears in `loom ls --all` as done
- [ ] `--no-distill`: skips distillation window, goes straight to archive

### 3.7 `loom link`
- [ ] Appends wikilink to task note's Linked Documents section
- [ ] Works on active and archived tasks
- [ ] Vault-relative and absolute paths both work

### 3.8 `loom popup`
- [ ] Opens `tmux display-popup` with fzf list of tasks
- [ ] Selecting a task and pressing Enter switches to that session
- [ ] Dead/done tasks (without live session): not listed in popup (active only)

### 3.9 `loom sync`
- [ ] Stages, commits, pulls, and pushes vault changes
- [ ] Warns on merge conflicts

### 3.10 `loom rebuild`
- [ ] Regenerates tasks.json from vault frontmatter
- [ ] Correct count reported

### 3.11 `loom adr`
- [ ] Creates ADR file in 30-Decisions/ with correct number

---

## 4. Hook Tests

Run: `bash tests/test_hooks.sh`

### 4.1 session-start.py
- [ ] Known session: updates `status=waiting`, `transcript_path`
- [ ] Unknown session (outside loom): does NOT create vault entry (no auto-register)
- [ ] Malformed input (empty JSON): exits 0 silently

### 4.2 user-prompt-submit.py
- [ ] Known session: sets `status=working`
- [ ] Unknown session: no-op

### 4.3 stop.py
- [ ] Known session: sets `status=waiting`

### 4.4 session-end.py
- [ ] Status is `done`: no change
- [ ] Status is other: sets `status=idle`

### 4.5 pre-compact.py
- [ ] Appends compaction checkpoint to vault note
- [ ] With `LOOM_DISTILL=auto` and live session: opens distill window

### 4.6 notification.py
- [ ] `permission_prompt` type: sends critical notification
- [ ] `idle_prompt` type: sends normal notification
- [ ] No notification backend installed: exits 0 silently

---

## 5. Web API Tests

Run: `bash tests/test_web.sh` (requires `loom web` to be running)

### 5.1 GET /api/tasks
- [ ] Returns JSON array of tasks
- [ ] `?all=1` includes archived tasks
- [ ] `status` field reflects dead/done correctly (not raw stored value)
- [ ] `alive` field is false for sessions without a live tmux session
- [ ] `model` field is present

### 5.2 GET /api/tasks/<slug>
- [ ] Returns task detail with `preview` (pane content if alive)
- [ ] 404 for unknown slug

### 5.3 POST /api/tasks/<slug>/send
- [ ] Sends text to session's main pane
- [ ] 409 if session not alive
- [ ] Text appears in tmux pane

### 5.4 DELETE /api/tasks/<slug>
- [ ] Kills tmux session
- [ ] 409 if session not alive

### 5.5 GET /api/health
- [ ] Returns `{ok: true, version, vault, vault_initialized}`

### 5.6 Authentication
- [ ] With `LOOM_WEB_TOKEN` set: request without token returns 401
- [ ] `?token=<correct>`: request succeeds
- [ ] `Authorization: Bearer <correct>`: request succeeds

---

## 6. Web UI Tests (visual/browser)

Manual checks:
- [ ] Task cards show correct status dot color (green=working, yellow=waiting, gray=idle, red=dead)
- [ ] ✏ and ✕ buttons visible on cards with live sessions (no expand needed)
- [ ] ▶ Resume button visible on dead-session cards
- [ ] "Show archived" toggle makes done tasks appear (dimmed)
- [ ] Send modal opens on ✏, sends text via Ctrl+Enter
- [ ] Kill button with confirmation dialog kills session, card updates
- [ ] Mobile layout: cards stack, buttons are large enough to tap
- [ ] Model tag visible on each task card

---

## 7. Install Tests

- [ ] `./install.sh` completes without error on fresh machine
- [ ] `./install.sh` is idempotent (safe to run twice)
- [ ] `loom ls` works after install (before any tasks)
- [ ] Hook scripts referenced in settings.json exist and are executable
- [ ] Skills symlinked in `~/.claude/skills/`
