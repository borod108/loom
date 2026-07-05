#!/usr/bin/env python3
"""Hook: UserPromptSubmit — flip task status to 'working' on user input."""

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
        vault.update_task(slug, status="working")
        state.upsert(slug, status="working")

except Exception as e:
    print(f"loom user-prompt-submit hook error: {e}", file=sys.stderr)

sys.exit(0)
