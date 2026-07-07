#!/usr/bin/env python3
"""Hook: Stop — flip task status to 'waiting' when Claude finishes a turn."""

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
        vault.update_task(slug, status="waiting")
        state.upsert(slug, status="waiting")
        vault.rebuild_dashboard()

        if cfg.get("LOOM_NOTIFY_ON_STOP") in ("1", "true"):
            from loom import NotifyManager
            NotifyManager(cfg).send(
                "loom: turn finished",
                f"[{slug}] Claude finished a turn",
                slug=slug,
            )

except Exception as e:
    print(f"loom stop hook error: {e}", file=sys.stderr)

sys.exit(0)
