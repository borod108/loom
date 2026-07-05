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
        # Known task — update with fresh transcript path and set running
        vault.update_task(slug, status="waiting", transcript_path=transcript)
        state.upsert(slug, status="waiting", transcript_path=transcript, cwd=cwd)
    else:
        # Unknown session (claude started outside loom) — register a minimal entry
        from loom import slugify
        from pathlib import Path
        import uuid as _uuid
        slug = slugify(Path(cwd).name or "unknown") + "-" + session_id[:8]
        if vault.is_initialized():
            try:
                vault.create_task(slug, session_id, cwd, goal="(started outside loom)")
                vault.update_task(slug, transcript_path=transcript, status="waiting")
                state.upsert(slug, session_id=session_id, status="waiting",
                             cwd=cwd, transcript_path=transcript)
            except FileExistsError:
                pass

except Exception as e:
    print(f"loom session-start hook error: {e}", file=sys.stderr)

sys.exit(0)
