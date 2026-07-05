#!/usr/bin/env python3
"""loom core library — vault, state, tmux, and notification operations."""

import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class Config:
    """Load configuration from ~/.config/loom/config and environment."""

    DEFAULTS = {
        "LOOM_VAULT": str(Path.home() / "vault"),
        "LOOM_SESSION_PREFIX": "loom",
        "LOOM_WEB_PORT": "7799",
        "LOOM_WEB_BIND": "0.0.0.0",
        "LOOM_WEB_TOKEN": "",
        "LOOM_DISTILL": "auto",
        "LOOM_DISTILL_MODEL": "claude-sonnet-4-5",
        "LOOM_NOTIFICATIONS": "notify-send",
        "LOOM_NTFY_TOPIC": "loom",
        "LOOM_NTFY_SERVER": "https://ntfy.sh",
    }

    def __init__(self):
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        self._data: Dict[str, str] = dict(self.DEFAULTS)

        config_file = config_home / "loom" / "config"
        if config_file.exists():
            for line in config_file.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                v = v.strip().strip("\"'")
                self._data[k.strip()] = os.path.expandvars(os.path.expanduser(v))

        # Environment overrides config file
        for k in self.DEFAULTS:
            if k in os.environ:
                self._data[k] = os.environ[k]

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key, default)

    @property
    def vault(self) -> Path:
        return Path(self.get("LOOM_VAULT"))

    @property
    def session_prefix(self) -> str:
        return self.get("LOOM_SESSION_PREFIX")

    @property
    def web_port(self) -> int:
        return int(self.get("LOOM_WEB_PORT"))

    @property
    def web_bind(self) -> str:
        return self.get("LOOM_WEB_BIND")

    @property
    def web_token(self) -> str:
        return self.get("LOOM_WEB_TOKEN")

    @property
    def distill(self) -> str:
        return self.get("LOOM_DISTILL")  # auto | manual | off

    @property
    def distill_model(self) -> str:
        return self.get("LOOM_DISTILL_MODEL")

    @property
    def notifications(self) -> List[str]:
        return [n.strip() for n in self.get("LOOM_NOTIFICATIONS").split(",") if n.strip()]


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
_ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def _parse_frontmatter(content: str) -> Tuple[Dict[str, str], str]:
    m = _FM_RE.match(content)
    if not m:
        return {}, content
    fields: Dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fields[k.strip()] = v.strip()
    body = content[m.end():]
    return fields, body


def _write_frontmatter(fields: Dict[str, str], body: str) -> str:
    lines = ["---"]
    for k, v in fields.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines) + body


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_display() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def slugify(text: str) -> str:
    """Convert text to a safe slug."""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:60]


def format_age(iso_ts: str) -> str:
    """Human-readable age from an ISO timestamp."""
    try:
        dt = datetime.strptime(iso_ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        secs = int((datetime.now(timezone.utc) - dt).total_seconds())
    except (ValueError, TypeError):
        return "?"
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m"
    if secs < 86400:
        return f"{secs // 3600}h"
    return f"{secs // 86400}d"


# ---------------------------------------------------------------------------
# Vault templates
# ---------------------------------------------------------------------------

_TASK_TEMPLATE = """\
---
session_id: {session_id}
tmux_session: {tmux_session}
status: starting
cwd: {cwd}
project: {project}
started: {now}
updated: {now}
---

# {slug}

## Goal

{goal}

## Log

- {now} Task created
"""

_COMPACT_NOTE = "\n- {now} Compaction checkpoint · transcript: `{transcript_path}`\n"

_SUMMARY_TEMPLATE = """\

---

## Session Summary ({date})

### Accomplished

{accomplished}

### Decisions Made

{decisions}

### Research Findings

{findings}

### Next Steps

{next_steps}
"""


# ---------------------------------------------------------------------------
# Vault manager
# ---------------------------------------------------------------------------

class VaultManager:
    """Read/write the markdown vault."""

    DIRS = [
        "00-Dashboard",
        "10-Tasks",
        "20-Projects",
        "30-Decisions",
        "40-Research",
        "90-Archive",
    ]

    def __init__(self, config: Config):
        self.config = config
        self.vault = config.vault

    # --- structure ---

    def ensure_structure(self):
        for d in self.DIRS:
            (self.vault / d).mkdir(parents=True, exist_ok=True)

    def is_initialized(self) -> bool:
        return (self.vault / "10-Tasks").exists()

    def init(self, git: bool = True):
        self.ensure_structure()
        dash = self.vault / "00-Dashboard" / "Active Tasks.md"
        if not dash.exists():
            dash.write_text(
                "# Active Tasks\n\n> Auto-generated by loom.\n\n| Task | Status | Project | Age |\n"
                "|------|--------|---------|-----|\n"
            )
        if git and not (self.vault / ".git").exists():
            subprocess.run(["git", "init"], cwd=self.vault, capture_output=True)
            (self.vault / ".gitignore").write_text(".DS_Store\n*.swp\n")
            subprocess.run(["git", "add", "-A"], cwd=self.vault, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "init: loom vault"],
                cwd=self.vault, capture_output=True
            )

    # --- task paths ---

    def task_path(self, slug: str) -> Path:
        return self.vault / "10-Tasks" / f"{slug}.md"

    def archive_path(self, slug: str) -> Path:
        return self.vault / "90-Archive" / f"{slug}.md"

    def adr_dir(self) -> Path:
        return self.vault / "30-Decisions"

    # --- CRUD ---

    def create_task(
        self, slug: str, session_id: str, cwd: str, goal: str = ""
    ) -> Path:
        self.ensure_structure()
        path = self.task_path(slug)
        if path.exists():
            raise FileExistsError(f"Task already exists: {slug}")
        content = _TASK_TEMPLATE.format(
            session_id=session_id,
            tmux_session=f"{self.config.session_prefix}-{slug}",
            cwd=cwd,
            project=Path(cwd).name,
            now=_now_iso(),
            slug=slug,
            goal=goal if goal else "_not set_",
        )
        path.write_text(content)
        self.rebuild_dashboard()
        return path

    def get_task(self, slug: str) -> Optional[Dict[str, Any]]:
        for p in [self.task_path(slug), self.archive_path(slug)]:
            if p.exists():
                fields, body = _parse_frontmatter(p.read_text())
                return {**fields, "slug": slug, "body": body, "path": str(p)}
        return None

    def update_task(self, slug: str, **updates: str) -> bool:
        path = self.task_path(slug)
        if not path.exists():
            return False
        fields, body = _parse_frontmatter(path.read_text())
        fields.update(updates)
        fields["updated"] = _now_iso()
        path.write_text(_write_frontmatter(fields, body))
        return True

    def append_log(self, slug: str, message: str) -> bool:
        path = self.task_path(slug)
        if not path.exists():
            return False
        content = path.read_text()
        log_line = f"- {_now_iso()} {message}\n"
        if "## Log\n" in content:
            # Append after "## Log" section header
            content += log_line
        path.write_text(content)
        return True

    def append_compact_checkpoint(self, slug: str, transcript_path: str) -> bool:
        path = self.task_path(slug)
        if not path.exists():
            return False
        note = _COMPACT_NOTE.format(now=_now_iso(), transcript_path=transcript_path)
        content = path.read_text()
        path.write_text(content + note)
        return True

    def list_tasks(self) -> List[Dict[str, Any]]:
        tasks_dir = self.vault / "10-Tasks"
        if not tasks_dir.exists():
            return []
        results = []
        for p in sorted(tasks_dir.glob("*.md")):
            fields, _ = _parse_frontmatter(p.read_text())
            results.append({**fields, "slug": p.stem})
        return results

    def archive_task(self, slug: str) -> bool:
        src = self.task_path(slug)
        if not src.exists():
            return False
        self.ensure_structure()
        shutil.move(str(src), str(self.archive_path(slug)))
        self.rebuild_dashboard()
        return True

    def find_by_session_id(self, session_id: str) -> Optional[str]:
        tasks_dir = self.vault / "10-Tasks"
        if not tasks_dir.exists():
            return None
        for p in tasks_dir.glob("*.md"):
            fields, _ = _parse_frontmatter(p.read_text())
            if fields.get("session_id") == session_id:
                return p.stem
        return None

    def rebuild_dashboard(self):
        tasks = self.list_tasks()
        lines = [
            "# Active Tasks\n",
            f"> Auto-generated by loom — {_now_display()}\n",
            "",
            "| Task | Status | Project | CWD | Started |",
            "|------|--------|---------|-----|---------|",
        ]
        for t in tasks:
            slug = t.get("slug", "")
            status = t.get("status", "unknown")
            project = t.get("project", "")
            cwd = t.get("cwd", "")
            started = (t.get("started") or "")[:10]
            lines.append(f"| [[{slug}]] | {status} | {project} | `{cwd}` | {started} |")
        dash = self.vault / "00-Dashboard" / "Active Tasks.md"
        dash.write_text("\n".join(lines) + "\n")

    def next_adr_number(self) -> int:
        adr_dir = self.adr_dir()
        if not adr_dir.exists():
            return 1
        existing = list(adr_dir.glob("ADR-*.md"))
        if not existing:
            return 1
        nums = []
        for p in existing:
            m = re.match(r"ADR-(\d+)", p.stem)
            if m:
                nums.append(int(m.group(1)))
        return max(nums) + 1 if nums else 1

    def create_adr(self, title: str, context: str = "", decision: str = "", consequences: str = "") -> Path:
        self.ensure_structure()
        num = self.next_adr_number()
        slug = slugify(title)
        path = self.adr_dir() / f"ADR-{num:03d}-{slug}.md"
        content = f"""\
---
number: {num}
title: {title}
status: accepted
date: {_now_iso()[:10]}
---

# ADR-{num:03d}: {title}

## Context

{context or '_Fill in context._'}

## Decision

{decision or '_Fill in decision._'}

## Consequences

{consequences or '_Fill in consequences._'}

## Status History

- {_now_iso()[:10]}: accepted
"""
        path.write_text(content)
        return path


# ---------------------------------------------------------------------------
# State manager (tasks.json cache)
# ---------------------------------------------------------------------------

class StateManager:
    """Fast JSON cache of task state; rebuilt from vault when needed."""

    def __init__(self, config: Config):
        state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
        self._dir = state_home / "loom"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "tasks.json"
        if not self._file.exists():
            self._file.write_text("{}")

    def _load(self) -> Dict[str, Any]:
        try:
            return json.loads(self._file.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, data: Dict[str, Any]):
        tmp = self._file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self._file)

    def upsert(self, slug: str, **fields: Any):
        data = self._load()
        entry = data.setdefault(slug, {})
        entry.update(fields)
        entry["updated"] = _now_iso()
        self._save(data)

    def get(self, slug: str) -> Optional[Dict[str, Any]]:
        return self._load().get(slug)

    def remove(self, slug: str):
        data = self._load()
        data.pop(slug, None)
        self._save(data)

    def list_all(self) -> Dict[str, Any]:
        return self._load()

    def rebuild_from_vault(self, vault: VaultManager):
        tasks = vault.list_tasks()
        data = {}
        for t in tasks:
            slug = t.pop("slug", None)
            t.pop("body", None)
            t.pop("path", None)
            if slug:
                data[slug] = t
        self._save(data)


# ---------------------------------------------------------------------------
# Tmux manager
# ---------------------------------------------------------------------------

class TmuxManager:
    """Manage loom-prefixed tmux sessions."""

    def __init__(self, config: Config):
        self.config = config
        self.prefix = config.session_prefix

    def session_name(self, slug: str) -> str:
        return f"{self.prefix}-{slug}"

    def slug_from_session(self, name: str) -> Optional[str]:
        prefix = f"{self.prefix}-"
        return name[len(prefix):] if name.startswith(prefix) else None

    def session_exists(self, slug: str) -> bool:
        r = subprocess.run(
            ["tmux", "has-session", "-t", self.session_name(slug)],
            capture_output=True,
        )
        return r.returncode == 0

    def list_sessions(self) -> List[Dict[str, Any]]:
        r = subprocess.run(
            ["tmux", "list-sessions", "-F",
             "#{session_name}\t#{session_attached}\t#{session_activity}"],
            capture_output=True, text=True,
        )
        sessions = []
        if r.returncode != 0:
            return sessions
        for line in r.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            name, attached, activity = parts[0], parts[1], parts[2]
            slug = self.slug_from_session(name)
            if slug is None:
                continue
            sessions.append({
                "name": name,
                "slug": slug,
                "attached": attached == "1",
                "activity": int(activity) if activity.isdigit() else 0,
            })
        return sessions

    def new_session(self, slug: str, cwd: str, session_id: str) -> bool:
        name = self.session_name(slug)
        cwd = os.path.expanduser(cwd)
        # Create detached session with a plain shell first
        r = subprocess.run(
            ["tmux", "new-session", "-d", "-s", name, "-c", cwd],
            capture_output=True,
        )
        if r.returncode != 0:
            return False
        # Start claude in window 0
        subprocess.run(
            ["tmux", "send-keys", "-t", f"{name}:0.0",
             f"claude --session-id {session_id}", "Enter"],
        )
        return True

    def resume_in_session(self, slug: str, cwd: str, session_id: str) -> bool:
        name = self.session_name(slug)
        cwd = os.path.expanduser(cwd)
        r = subprocess.run(
            ["tmux", "new-session", "-d", "-s", name, "-c", cwd],
            capture_output=True,
        )
        if r.returncode != 0:
            return False
        subprocess.run(
            ["tmux", "send-keys", "-t", f"{name}:0.0",
             f"claude --resume {session_id}", "Enter"],
        )
        return True

    def attach(self, slug: str):
        name = self.session_name(slug)
        if os.environ.get("TMUX"):
            subprocess.run(["tmux", "switch-client", "-t", name])
        else:
            os.execlp("tmux", "tmux", "attach", "-t", name)

    def capture_pane(self, slug: str, lines: int = 25) -> str:
        name = self.session_name(slug)
        r = subprocess.run(
            ["tmux", "capture-pane", "-p", "-t", f"{name}:0.0"],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            return ""
        all_lines = r.stdout.splitlines()
        tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return "\n".join(_ANSI_RE.sub("", l) for l in tail)

    def send_keys(self, slug: str, text: str, enter: bool = True) -> bool:
        name = self.session_name(slug)
        cmd = ["tmux", "send-keys", "-t", f"{name}:0.0", text]
        if enter:
            cmd.append("Enter")
        return subprocess.run(cmd, capture_output=True).returncode == 0

    def send_after_ready(self, slug: str, text: str, timeout: int = 30):
        """Send text to a session once Claude's prompt is visible (non-blocking).

        On systemd-based Linux (Fedora, Ubuntu, etc.) plain Popen children are
        killed when the parent exits because Claude Code runs inside a systemd
        scope.  Use `systemd-run --user --no-block` to escape the scope.
        Falls back to a tmux window for non-systemd systems.
        """
        name = self.session_name(slug)
        target = f"{name}:0.0"

        # Write watcher to a temp file — avoids quoting hell in -c strings
        import tempfile
        script_path = tempfile.mktemp(suffix="_loom_goal.py")
        script = f"""import subprocess, time, os
target = {repr(target)}
text   = {repr(text)}
script = {repr(script_path)}

def pane():
    r = subprocess.run(
        ['tmux', 'capture-pane', '-p', '-t', target],
        capture_output=True, text=True,
    )
    return r.stdout if r.returncode == 0 else ''

# Poll until Claude's prompt glyph appears
for _ in range({timeout * 2}):
    time.sleep(0.5)
    p = pane()
    if '\\u276f' in p or 'Human:' in p:
        time.sleep(0.5)
        subprocess.run(['tmux', 'send-keys', '-t', target, text, 'Enter'])
        break

try:
    os.unlink(script)
except OSError:
    pass
"""
        with open(script_path, "w") as f:
            f.write(script)

        # Prefer systemd-run (escapes the Claude Code cgroup scope so the
        # process is not killed when loom new exits)
        if shutil.which("systemd-run"):
            subprocess.Popen(
                ["systemd-run", "--user", "--no-block", sys.executable, script_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            # Fallback: run in a hidden tmux window managed by tmux itself
            subprocess.run([
                "tmux", "new-window", "-d", "-t", name, "-n", ".goal",
                sys.executable, script_path,
            ], capture_output=True)

    def popup(self, loom_bin: str):
        """Open an fzf session picker in a tmux display-popup.

        switch-client cannot run from inside a display-popup (it targets the
        popup's pseudo-client, not the outer window).  Fix: fzf writes the
        selected slug to a tempfile, the popup closes, then we switch-client
        from the outer shell after display-popup returns.
        """
        if not shutil.which("fzf"):
            raise FileNotFoundError("fzf not found — install it (e.g. dnf install fzf)")
        if not os.environ.get("TMUX"):
            raise RuntimeError("popup requires an active tmux session")

        import tempfile
        sel_file = tempfile.mktemp(suffix=".loom-sel")

        try:
            # fzf writes selection to sel_file; we don't run loom go inside the popup
            script = (
                f"{repr(loom_bin)} ls --plain 2>/dev/null"
                " | grep -v '^[[:space:]]*$'"
                " | fzf --ansi --no-sort --reverse"
                "   --prompt='loom ❯ '"
                "   --header='Enter=attach  Esc=cancel'"
                f"  > {repr(sel_file)}"
            )
            subprocess.run(
                ["tmux", "display-popup", "-E", "-w", "80%", "-h", "50%", script]
            )
            # Now we're back in the outer shell — switch-client works correctly here
            if os.path.exists(sel_file):
                line = open(sel_file).read().strip()
                if line:
                    slug = line.split()[0]
                    self.attach(slug)
        finally:
            try:
                os.unlink(sel_file)
            except FileNotFoundError:
                pass

    def kill_session(self, slug: str) -> bool:
        name = self.session_name(slug)
        return subprocess.run(
            ["tmux", "kill-session", "-t", name], capture_output=True
        ).returncode == 0

    def open_distill_window(self, slug: str, session_id: str):
        """Open a 'distill' window in the task session for summarization."""
        name = self.session_name(slug)
        # Create new window named distill
        subprocess.run(
            ["tmux", "new-window", "-t", name, "-n", "distill"],
            capture_output=True,
        )
        # Resume the session there and send summarization prompt
        prompt = (
            "Please summarize this session: what was accomplished, "
            "key decisions made, research findings, and suggested next steps. "
            "Format in markdown with clear sections."
        )
        subprocess.run([
            "tmux", "send-keys", "-t", f"{name}:distill",
            f"claude --resume {session_id}", "Enter",
        ])
        # Give claude a moment to start, then send the prompt
        subprocess.run([
            "tmux", "send-keys", "-t", f"{name}:distill",
            f"; {prompt}", "",
        ])


# ---------------------------------------------------------------------------
# Notification manager
# ---------------------------------------------------------------------------

class NotifyManager:
    """Send notifications via configured backends."""

    def __init__(self, config: Config):
        self.config = config

    def send(self, title: str, body: str, urgency: str = "normal"):
        for backend in self.config.notifications:
            try:
                if backend == "notify-send":
                    self._notify_send(title, body, urgency)
                elif backend == "ntfy":
                    self._ntfy(title, body)
                elif backend == "bell":
                    self._bell()
            except Exception:
                pass

    def _notify_send(self, title: str, body: str, urgency: str):
        subprocess.run(
            ["notify-send", "-u", urgency, "-a", "loom", title, body],
            capture_output=True, timeout=5,
        )

    def _ntfy(self, title: str, body: str):
        import urllib.request
        topic = self.config.get("LOOM_NTFY_TOPIC")
        server = self.config.get("LOOM_NTFY_SERVER")
        data = json.dumps({"title": title, "message": body}).encode()
        req = urllib.request.Request(
            f"{server}/{topic}",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)

    def _bell(self):
        sys.stdout.write("\a")
        sys.stdout.flush()


# ---------------------------------------------------------------------------
# Convenience: load all managers from default config
# ---------------------------------------------------------------------------

def load_managers(config: Optional[Config] = None):
    cfg = config or Config()
    return cfg, VaultManager(cfg), StateManager(cfg), TmuxManager(cfg), NotifyManager(cfg)


def find_loom_dir() -> Path:
    """Locate the loom installation directory from this file's location."""
    return Path(__file__).resolve().parent.parent
