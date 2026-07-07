# loom — End-to-End Test Plan (real usage scenarios)

Date: 2026-07-06 · Machine: bod108 desktop (Linux, tmux 3.x, claude 2.1.201)
Tester: Claude (driving a dedicated tmux session `loomdrv` for interactive commands).
All Claude task sessions use `--model claude-haiku-4-5` to keep testing cheap.
Backup taken of `~/.claude/settings.json` before install.

Legend: ✅ pass · ❌ fail · ⚠️ partial/concern · ⏭ skipped (reason)

---

## Phase 0 — Installation & self-tests

| # | Scenario | Expected |
|---|----------|----------|
| 0.1 | Backup `~/.claude/settings.json`, run `./install.sh` (non-interactive) | Completes; prereqs detected; vault `~/vault` created with PARA dirs + git repo + initial commit |
| 0.2 | Inspect artifacts | `~/.config/loom/config`, `~/.config/loom/loom_dir`, PATH line in shell rc, `recall`+`loom-status` symlinks in `~/.claude/skills/`, 6 hook events merged into settings.json with correct absolute paths |
| 0.3 | Re-run `./install.sh` (idempotency = upgrade path) | No duplicate hooks, no duplicate PATH lines, config untouched |
| 0.4 | Repo's own unit tests (`tests/test_vault.py`, `test_state.py`) | All pass |
| 0.5 | Repo's integration tests (`tests/test_status.sh`) | All pass |

## Phase 1 — Task lifecycle basics (Goal 1: see what's running, easy access)

| # | Scenario | Expected |
|---|----------|----------|
| 1.1 | `loom ls` on empty vault; `loom --help` | "No active tasks."; help lists all commands |
| 1.2 | **Real scenario:** `loom new demo-fizzbuzz --dir <tmp project> --goal "write fizzbuzz.py…" -m claude-haiku-4-5` | Task note created with correct frontmatter (session_id UUID, cwd, model, status starting); tmux session `loom-demo-fizzbuzz` running claude; goal auto-sent once Claude ready (send_after_ready watcher) |
| 1.3 | Status transitions via hooks | UserPromptSubmit→`working`, Stop→`waiting`; visible in `loom ls`, task frontmatter, tasks.json |
| 1.4 | `loom preview demo-fizzbuzz` | Shows recent pane content, UI chrome stripped |
| 1.5 | `loom send demo-fizzbuzz -y "…follow-up…"` | Text lands in Claude prompt, Claude responds; status flips working→waiting |
| 1.6 | Duplicate slug / weird name (`My Cool Task!!`) | Duplicate → clear error; name slugified to `my-cool-task` |
| 1.7 | Interactive pickers (`loom new` with no --dir/--model) driven in `loomdrv` window | Model list + dir list render; number selection works; recent cwds appear |
| 1.8 | `loom go` from inside tmux (driver session) | switch-client lands on task session |
| 1.9 | `loom popup` without fzf | Clear error message (fzf not installed here) |

## Phase 2 — Second brain (Goal 2: knowledge is captured & findable)

| # | Scenario | Expected |
|---|----------|----------|
| 2.1 | SessionStart context injection: ask task Claude "Where is your knowledge vault and task note?" | Claude knows vault path + task note path (proves additionalContext reached it) |
| 2.2 | **Real scenario:** ask task Claude to research a small topic and persist it (write `40-Research/<topic>.md`, run `loom adr`, `loom link`) | Files appear in vault; ADR numbered ADR-001; link added under Linked Documents |
| 2.3 | Automatic log & status maintenance | Task note frontmatter `updated` bumps; log entries appear **under `## Log`** (suspected bug: appends at EOF) |
| 2.4 | **Cross-session recall:** new task `demo-recall` in a different dir; invoke `/recall <topic>` | Claude finds the research + ADR from 2.2 without redoing it — the core second-brain loop |
| 2.5 | `loom adr "…"` + `loom link` from CLI | ADR file created with next number; wikilink appended |
| 2.6 | PreCompact hook (synthetic stdin + real transcript file; then real `/compact` in task session) | Compaction checkpoint line + snapshot of recent assistant output appended to task note; distill window opened when LOOM_DISTILL=auto |
| 2.7 | SessionEnd: exit Claude (`/exit`) in task session | Status→idle, "Claude session ended" logged, window snapshot saved to note |
| 2.8 | Dashboard `00-Dashboard/Active Tasks.md` | Regenerated table matches reality after each mutation |
| 2.9 | Vault is valid Obsidian-style markdown | Frontmatter parses, wikilinks used, files greppable |

## Phase 3 — Multi-window tasks, resume, jump (Goal 1 + resume from Goal 2)

| # | Scenario | Expected |
|---|----------|----------|
| 3.1 | Add extra windows (`server`, `logs`) to task session; `loom snapshot` | `## Window State` JSON block with 3 windows, paths recorded |
| 3.2 | Kill tmux session out-of-band; `loom ls` | Task shows `dead` (∅ marker) |
| 3.3 | `loom resume demo-fizzbuzz --no-attach` | Session recreated in correct cwd, `claude --resume <id>` fired, extra windows restored with names+paths |
| 3.4 | Continuity: ask resumed Claude "what was the goal I gave you?" | Remembers prior conversation (same session id) |
| 3.5 | `loom go` on a dead task | Auto-resumes then attaches |
| 3.6 | `loom resume` when session exists but Claude exited | Sends resume command into existing window |

## Phase 4 — Web UI (Goal 1 overview)

| # | Scenario | Expected |
|---|----------|----------|
| 4.1 | `loom web` (background, 127.0.0.1) | Server starts; `GET /api/health` ok |
| 4.2 | `GET /api/tasks` / `GET /api/tasks/<slug>` | Correct statuses, live pane previews, goal extracted, body included |
| 4.3 | `POST /api/tasks/<slug>/send` | Prompt reaches Claude; response observable in next preview |
| 4.4 | `DELETE /api/tasks/<slug>` | Session killed; status idle→displayed dead |
| 4.5 | Static UI served (`/`, app.js, style.css); HTML sanity | 200s, correct mime, page references API |
| 4.6 | Token auth (`LOOM_WEB_TOKEN`) | 401 without token; 200 with `?token=` and with Bearer header; static files also protected |
| 4.7 | Error paths: unknown slug (404), missing text (400), send to dead session (409) | Correct codes + JSON errors |
| 4.8 | Mobile/UX review of HTML/CSS (static analysis) | Responsive meta, dark theme, actions present |

## Phase 5 — Done, archive, sync (lifecycle end)

| # | Scenario | Expected |
|---|----------|----------|
| 5.1 | `loom done <slug>` with distill=auto on live session | Distill window opens, summary prompt visible **and submitted** (suspected bug: prompt not submitted; sent before claude ready) |
| 5.2 | `loom done <slug> --no-distill` (confirm y) | Session killed, note moved to 90-Archive, `loom ls` hides, `loom ls --all` shows ✓ done |
| 5.3 | `loom sync` without remote | Dashboard rebuilt, auto-commit created; pull/push fail gracefully with useful message |
| 5.4 | Delete tasks.json → `loom rebuild` | Cache regenerated from vault |

## Phase 6 — Robustness & edge cases

| # | Scenario | Expected |
|---|----------|----------|
| 6.1 | Claude session started OUTSIDE loom (this very session) | Not auto-registered; hooks exit cleanly (note: ADR-003 text says "auto-registers as unmanaged" — code intentionally doesn't; doc/code mismatch to report) |
| 6.2 | Vault temporarily missing | Commands fail with clear errors, no tracebacks |
| 6.3 | Notification hook fired manually (permission_prompt / idle_prompt JSON) | notify-send invoked with [slug] context; no crash on unknown session |
| 6.4 | Hook scripts with empty/garbage stdin | Exit 0, no exceptions (they guard) |
| 6.5 | Task with status=waiting whose session died | `loom ls` display — expect ⚠️: shows "waiting" not "dead" (only idle/starting map to dead) |
| 6.6 | Two tasks same project different dirs; long cwd truncation in ls | Renders correctly |

## Phase 7 — Gap analysis (functionality it *should* have)

Assessed against the user's four goals; produces a recommendations list, not pass/fail:
notification → jump-to-session deep link; `loom search <term>` CLI; vault note view in web UI;
status accuracy issues; distillation robustness; `loom done` UX (two-step is awkward);
web UI auth default (0.0.0.0 with no token); anything discovered during Phases 0-6.

---

## Results

(filled in during execution — see RESULTS section appended below)

## Results (executed 2026-07-06)

### Verdict per phase
- **Phase 0 install**: ✅ all (prereqs, config, PATH, skill symlinks, hook merge alongside pre-existing hooks, vault init+git, idempotent re-run). Unit 38/38 ✅. Integration 6/7 → 7/7 after fix #1.
- **Phase 1 lifecycle**: ✅ after fixes #1–#4. new/ls/preview/send/go/popup-error/duplicate/slugify all pass.
- **Phase 2 second brain**: ✅ after fixes #5–#6. Research note written by task session; ADR + link via CLI; **cross-session /recall found and reused the knowledge (headline test)**; PreCompact checkpoint + snapshot; SessionEnd idle+log+window snapshot; context injection works on start/resume.
- **Phase 3 windows/resume**: ✅ after fix #2 follow-ups. 3-window layout snapshot + exact restore; `claude --resume` continuity across kill; `loom go` auto-resume + real client switch (verified — it moved a live client).
- **Phase 4 web UI**: ✅ after fix #7 (path traversal). health/tasks/detail/send/kill/404/400/409/auth(4 modes)/static/polling all pass.
- **Phase 5 done/sync**: ✅ after fix #8 (distill cwd). Distill fork produces real summary; archive to 90-Archive; rebuild OK. sync = ⚠️ (finding G6).
- **Phase 6 robustness**: ✅ hooks survive garbage stdin + unknown sessions; vault-missing errors clean; waiting+dead display fixed (#9); notification hook fires notify-send.

### Bugs found & FIXED during testing (all in working tree, uncommitted)
1. **tmux base-index breakage** — all `:claude.0`/`:0.0` targets fail with `base-index 1`/`pane-base-index 1` (this machine). Fixed: window-name targets everywhere; `restore_windows`/resume "extra window" logic now keys on min index, not 0. Broke: goal delivery, send, preview, resume, session-manager test.
2. **Goal watcher fired during the trust dialog** — fallback ready-check matched dialog text ("Claude Code") + zsh separator; goal text swallowed AND its Enter **auto-accepted the workspace-trust dialog** (security-relevant). Fixed: dialog-aware ready check (never send while "trust this folder"/"Esc to cancel" visible; require model name + ❯ prompt line). Timeout 30s→300s (trust dialog needs human time).
3. **`send_keys` text+Enter in one call = paste** — Claude Code TUI leaves it unsubmitted in the input box. Fixed: separate Enter after 0.35s (also in goal watcher).
4. **Pane preview chrome-stripping failed on wide terminals** — status-bar regex allowed only 40 chars between model name and `$`. Fixed.
5. **SessionStart context injection silently ignored** — hook printed top-level `additionalContext`; Claude Code requires `hookSpecificOutput.{hookEventName,additionalContext}`. Fixed — vault-awareness now reaches every loom session (verified: session cites vault + task note paths).
6. **PreCompact snapshot never produced** — parser read `msg["role"]/["content"]` but transcript lines are `{"type":"assistant","message":{...}}`. Fixed (verified against real transcript).
7. **Web server path traversal** — `GET /../../lib/loom.py` served arbitrary files (default bind 0.0.0.0, no token!). Fixed with resolve()+prefix check; encoded traversal already 404'd.
8. **Distill window resumed in wrong cwd** — window created without `-c`, and `claude --resume` is cwd-scoped → "No conversation found". Fixed: pass task cwd (done + pre-compact paths). Also: distill now uses `--fork-session` (two processes must not share one transcript) and the summary prompt is delivered by the ready-watcher and instructs Claude to append the summary to the task note (previously the summary was never persisted).
9. **`append_log` wrote at EOF** (entries landed under Linked Documents) — fixed to insert inside `## Log`. **waiting/working+no-session displayed as alive** — fixed to display `dead` (CLI + web).

### Open findings (NOT fixed — decisions for you)
- **G1 Dashboard staleness**: `00-Dashboard/Active Tasks.md` only rebuilds on create/archive/sync/rebuild — status changes from hooks don't refresh it. Suggest: rebuild in stop/session-end hooks (cheap) or cron.
- **G2 `loom go`/popup switch the *most recently active* client** — with several attached clients tmux picks one for you; fine solo, surprising with many terminals.
- **G3 Notifications carry no deep link**: notify-send default actions can't jump to a tmux session. Suggest: add action hint (`loom go <slug>` command in body) or ntfy click-URL to web UI task page.
- **G4 Web UI default is `0.0.0.0` with empty token** — recommend defaulting bind to 127.0.0.1 unless LOOM_WEB_TOKEN is set (installer could generate a token).
- **G5 `loom done` two-step UX** (`done` → review distill → `done --no-distill`) is easy to forget; the `--no-distill` re-run also *kills the distill window before you copy anything* if you're quick. Suggest `loom done --finish` that waits, or detect existing distill summary in note.
- **G6 `loom sync` no-remote output is misleading** ("pull had conflicts", then "✓ Vault synced"). Detect missing remote → "committed locally; no remote configured".
- **G7 ADR-003 doc/code mismatch**: ADR says sessions started outside loom auto-register as "unmanaged"; code deliberately ignores them. Pick one; an opt-in `LOOM_ADOPT_UNMANAGED=1` would make ALL your Claude work land in the vault, which matches goal 2.
- **G8 rebuild drops archived tasks from tasks.json** (cache = active only) — harmless today since ls/web read the vault, but cache and vault disagree after `loom done`.
- **G9 Trust dialog stalls unattended `loom new --goal`** — goal waits (correctly, post-fix) until a human accepts trust in a fresh dir. Suggest docs note or `--trust` passthrough research.
- **G10 fzf not installed here** — `loom popup` unusable until `sudo dnf install fzf` (error message is clear).

### Functionality worth adding (gap analysis vs. your goals)
- `loom search <term>` — grep the vault from CLI (today only /recall inside Claude does this).
- Web UI: render the task note markdown (vault view), not just pane preview; an "archive" action next to kill; show ADRs/Research lists.
- `loom note <slug> "text"` — append a log line manually from anywhere.
- Session-idle notification with the task slug (Notification hook covers permission/idle prompts; a "finished long turn" notify with `loom go` hint would close the monitor loop).
- Auto-`loom sync` on a timer/systemd (vault currently syncs only manually).
- `loom doctor` — check hooks installed, base-index compat, claude version, fzf, stale sessions.

## Recommendations implemented (2026-07-06, second pass)

All open findings G1–G10 and the gap-analysis features were implemented:

- **G1** Dashboard rebuilt by Stop + SessionEnd hooks — stays fresh as statuses change.
- **G2** `loom go`/popup now switch the *invoking* client (`switch-client -c <client_tty>`), not an arbitrary one.
- **G3** Notifications carry a deep link: body gets `→ loom go <slug>`; ntfy gets a click URL when `LOOM_WEB_URL` is set.
- **G4** Web security defaults: bind auto-selects 127.0.0.1 without a token / 0.0.0.0 with one; `install.sh` generates a random token for new configs (this machine's config updated too).
- **G5** `loom done` UX: re-running `done` after the summary landed proceeds to archive; `--finish` waits for the summary and archives automatically; `--yes` skips confirmation. Distill prompt now writes the summary into the task note itself.
- **G6** `loom sync` detects a missing remote: commits locally, says so, skips pull/push.
- **G7** `LOOM_ADOPT_UNMANAGED=1` registers non-loom Claude sessions as unmanaged tasks (slug `<dir>-<sid8>`, `unmanaged: true`, no false "dead" display); ADR-003 amended to match.
- **G8** `loom rebuild` includes archived tasks in tasks.json.
- **G9** `loom new --goal` prints a trust-dialog hint; watcher already waits 300s.
- **G10** `loom popup` works without fzf via a numbered fallback picker.
- **Features:** `loom search` (content + filename), `loom note`, `loom doctor`, `loom sync --enable-timer` (systemd units included), `LOOM_NOTIFY_ON_STOP`, web UI vault browser (Decisions/Research/Archive) with markdown note rendering, per-task 📄 note viewer and 📦 archive action.

## Full-flow integration test (tests/test_full_flow.sh)

Simulates the real developer day: 3 parallel tasks in separate tmux sessions → all write to the vault → finish one (others must survive) → a 4th task consumes the vault knowledge → session-end telemetry.

- **Mock mode** (default): isolated tmux server (`-L`, `-f /dev/null`, non-login `/bin/sh` panes), isolated vault/state/config, mock `claude` that fires the real loom hooks. Free, CI-safe. **Result: 32/32 passed.**
  - Lesson encoded in the test: tmux panes run login shells that rewrite PATH — a mock binary must be injected via a dedicated server whose `default-command` is a non-login shell.
- **Real mode** (`--real`): real `claude` (haiku) on the real vault; the script babysits trust dialogs and permission prompts. **Result: 32/32 passed** (run 2026-07-06: 3 parallel haiku sessions built the vault, flow-a archived without touching flow-b/c, flow-d recovered all three facts from the vault, SessionEnd telemetry correct; artifacts auto-cleaned).
