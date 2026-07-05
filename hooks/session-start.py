#!/usr/bin/env python3
"""Hook: SessionStart — register or update task when a Claude session starts."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from _lib import setup

data = setup()

from loom import Config, VaultManager, StateManager

try:
    session_id     = data.get("session_id", "")
    cwd            = data.get("cwd", "")
    transcript     = data.get("transcript_path", "")
    trigger        = data.get("hook_event_name", "SessionStart")

    cfg   = Config()
    vault = VaultManager(cfg)
    state = StateManager(cfg)

    if not session_id:
        sys.exit(0)

    slug = vault.find_by_session_id(session_id)
    if slug:
        # Known task — update with fresh transcript path and status
        vault.update_task(slug, status="waiting", transcript_path=transcript)
        state.upsert(slug, status="waiting", transcript_path=transcript, cwd=cwd)

        # Inject vault awareness so Claude proactively writes knowledge as it works
        task_note = str(vault.task_path(slug))
        vault_root = str(cfg.vault)
        context = f"""\
You are working in a loom-tracked session. Your knowledge vault is at {vault_root}/.

TASK NOTE (your session record): {task_note}
SESSION SLUG: {slug}

As you work, write knowledge to the vault so it persists across sessions:
- Research findings → {vault_root}/40-Research/<topic>.md
- Architecture decisions → {vault_root}/30-Decisions/ADR-NNN-<slug>.md  (run: loom adr "<title>")
- Append discoveries to your task log: {task_note}  (under ## Log)
- Link a document you create: loom link {slug} <path>

The /recall skill searches the vault for prior work on any topic. Use it at the start of new investigations."""

        # Return additionalContext so Claude sees vault instructions each session
        import json as _json
        print(_json.dumps({"additionalContext": context}))
    # Unknown session (started outside loom) — do NOT auto-register.

except Exception as e:
    print(f"loom session-start hook error: {e}", file=sys.stderr)

sys.exit(0)
