# 🧵 loom

**tmux-based Claude Code workbench** — session management, automatic knowledge capture, cross-project skills, and a web UI. All in a single git repo you can install on any Linux machine.

## What it does

| Goal | How |
|------|-----|
| See what's running | `loom ls` — table with status (working / waiting / idle), cwd, age |
| Jump to a task | `loom go <task>` — attach or switch-client to the right tmux session |
| Never lose context | Hooks write every session's state into a markdown vault automatically |
| Resume past work | `loom resume <task>` — recreate the session and continue the Claude conversation |
| Web overview | `loom web` — dark-themed, mobile-friendly UI with live pane previews and actions |
| Cross-project skills | `recall`, `loom-status` — linked from your central skill library |
| Sync knowledge | `loom sync` — git push/pull the vault across machines |

## Install

```bash
git clone <this-repo> ~/loom
cd ~/loom
./install.sh
```

`install.sh` is idempotent — re-run it to upgrade.

### What the installer does
1. Checks prerequisites: `python3 >= 3.8`, `tmux`, `git`
2. Asks for your vault directory (default: `~/vault`)
3. Creates `~/.config/loom/config` with your settings
4. Adds `loom/bin/` to your `PATH`
5. Merges loom hook scripts into `~/.claude/settings.json`
6. Symlinks skills into `~/.claude/skills/`
7. Initializes the vault (creates structure + git init)

## Quick start

```bash
# Create a new task in your current directory
loom new auth-refactor --goal "Implement JWT auth for the API"

# List all active tasks
loom ls

# Attach to a task's tmux session
loom go auth-refactor

# Start the web UI
loom web                   # http://localhost:7799

# Mark a task done (archives it to the vault)
loom done auth-refactor

# Sync vault to git remote
loom sync
```

## Vault structure

```
~/vault/
  00-Dashboard/Active Tasks.md   # auto-generated overview
  10-Tasks/<slug>.md             # one file per task (session_id, status, log)
  20-Projects/<name>/            # per-project notes
  30-Decisions/ADR-NNN-<slug>.md # architecture decision records
  40-Research/<topic>.md         # evergreen research findings
  90-Archive/                    # completed tasks (auto-moved by `loom done`)
```

The vault is plain Markdown — works in Obsidian, Logseq, Foam, or grep.

## Skills

Two skills are installed globally via symlinks:

| Skill | Trigger | What it does |
|-------|---------|--------------|
| `/recall <topic>` | Start of a new task | Searches the vault for prior decisions, research, related tasks |
| `/loom-status` | Any time | Shows current task status and recent log from vault |

## Configuration

Edit `~/.config/loom/config`:

```bash
LOOM_VAULT="~/vault"            # vault directory
LOOM_SESSION_PREFIX="loom"      # tmux session prefix (default: loom)
LOOM_WEB_PORT="7799"
LOOM_WEB_BIND="0.0.0.0"        # set to 127.0.0.1 for localhost-only
LOOM_WEB_TOKEN=""               # Bearer token for web auth (empty = no auth)
LOOM_DISTILL="auto"             # auto | manual | off
LOOM_NOTIFICATIONS="notify-send" # notify-send, ntfy, bell (comma-separated)
```

## Web UI

```bash
loom web
# → http://0.0.0.0:7799
```

- Dark theme, mobile-responsive
- Shows task status, age, last N pane lines
- Actions: Send input, Kill session
- Optional token auth: `http://host:7799/?token=<your-token>`

## Architecture decisions

All design decisions are recorded in `docs/adr/`. Key ones:

- **ADR-001**: One tmux session per task (reliable targeting)
- **ADR-002**: Plain Markdown vault, Obsidian-optional
- **ADR-003**: Hooks as primary telemetry (not capture-pane scraping)
- **ADR-004**: Vault frontmatter = truth; `tasks.json` = fast cache
- **ADR-005**: Distillation via interactive tmux window, not hidden API calls
- **ADR-009**: `TmuxManager` abstraction layer — swap implementations freely

## Running tests

```bash
# Unit tests (no tmux required)
python3 -m pytest tests/test_vault.py tests/test_state.py -v

# Integration tests (requires tmux)
bash tests/test_status.sh --verbose
```

## Adding a new machine

```bash
git clone <this-repo> ~/loom
cd ~/loom
./install.sh
# Then set up your vault remote:
git -C ~/vault remote add origin git@github.com:you/vault.git
loom sync
```

## Directory structure

```
loom/
  bin/loom          — CLI entry point (Python)
  lib/loom.py       — core library (Config, VaultManager, StateManager, TmuxManager, NotifyManager)
  hooks/            — Claude Code hook scripts (Python) + hooks-template.json
  web/              — HTTP server (Python stdlib) + HTML/CSS/JS UI
  skills/           — central skill library (symlinked into ~/.claude/skills/)
  templates/        — Markdown templates for tasks, ADRs, research notes
  docs/adr/         — Architecture Decision Records for loom itself
  tests/            — unit tests (pytest) + integration tests (bash)
  install.sh        — idempotent installer
  loom.conf.example — annotated config reference
```

## Prior art & acknowledgements

The session-management design was inspired by **[tmux-claude-session-manager](https://github.com/craftzdog/tmux-claude-session-manager)** by [@craftzdog](https://github.com/craftzdog) — a genuinely excellent tool that nails the core UX of one-Claude-session-per-tmux-session with a live working/waiting/idle picker. If you want a focused, polished session switcher without the vault and web UI overhead, go use it. It's great.

loom borrows the session-per-task pattern and status-state model from that project, and adds the knowledge-capture layer (vault), cross-project skills library, web UI, and install-anywhere design on top.

See also:
- [nielsgroen/claude-tmux](https://github.com/nielsgroen/claude-tmux) — tmux popup TUI with git-worktree support
- [obra/claude-session-driver](https://github.com/obra/claude-session-driver) — multi-agent orchestration via tmux
- [Tmux-Orchestrator](https://github.com/absmartly/Tmux-Orchestrator) — autonomous multi-project agent patterns

## License

MIT
