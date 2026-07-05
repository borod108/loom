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
    # Unknown session (started outside loom) — do NOT auto-register.
    # Auto-registration creates unmanaged clutter in the vault and web UI.
    # Users who want to track an external session should run: loom new <slug>

except Exception as e:
    print(f"loom session-start hook error: {e}", file=sys.stderr)

sys.exit(0)
