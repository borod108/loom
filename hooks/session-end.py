#!/usr/bin/env python3
"""Hook: SessionEnd — mark task as idle when Claude session ends."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from _lib import setup

data = setup()

from loom import Config, VaultManager, StateManager

try:
    session_id = data.get("session_id", "")
    if not session_id:
        sys.exit(0)

    cfg   = Config()
    vault = VaultManager(cfg)
    state = StateManager(cfg)

    slug = vault.find_by_session_id(session_id)
    if slug:
        task = vault.get_task(slug)
        # Only flip to idle if not already marked done by `loom done`
        if task and task.get("status") not in ("done", "archived"):
            vault.update_task(slug, status="idle")
            vault.append_log(slug, "Claude session ended (session-end hook)")
            state.upsert(slug, status="idle")

except Exception as e:
    print(f"loom session-end hook error: {e}", file=sys.stderr)

sys.exit(0)
