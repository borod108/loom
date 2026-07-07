#!/usr/bin/env python3
"""Hook: SessionEnd — snapshot windows and mark task as idle when Claude exits."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from _lib import setup

data = setup()

from loom import Config, VaultManager, StateManager, TmuxManager

try:
    session_id = data.get("session_id", "")
    if not session_id:
        sys.exit(0)

    cfg   = Config()
    vault = VaultManager(cfg)
    state = StateManager(cfg)
    tmux  = TmuxManager(cfg)

    slug = vault.find_by_session_id(session_id)
    if not slug:
        sys.exit(0)

    task = vault.get_task(slug)
    if not task:
        sys.exit(0)

    # Snapshot all windows while the tmux session is still alive.
    # This lets `loom resume` restore extra windows after a restart.
    if tmux.session_exists(slug):
        windows = tmux.snapshot_windows(slug)
        if windows:
            vault.save_windows(slug, windows)

    # Only flip to idle if not already marked done by `loom done`
    if task.get("status") not in ("done", "archived"):
        vault.update_task(slug, status="idle")
        vault.append_log(slug, "Claude session ended")
        state.upsert(slug, status="idle")
    vault.rebuild_dashboard()

except Exception as e:
    print(f"loom session-end hook error: {e}", file=sys.stderr)

sys.exit(0)
