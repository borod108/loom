#!/usr/bin/env python3
"""Hook: PreCompact — snapshot a checkpoint before context compaction.

If LOOM_DISTILL=auto, also opens a distillation window so the summary
is captured in the running session before the context is trimmed.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from _lib import setup

data = setup()

from loom import Config, VaultManager, StateManager, TmuxManager

try:
    session_id      = data.get("session_id", "")
    transcript_path = data.get("transcript_path", "")
    trigger         = data.get("trigger", "")  # manual | auto

    if not session_id:
        sys.exit(0)

    cfg   = Config()
    vault = VaultManager(cfg)
    state = StateManager(cfg)
    tmux  = TmuxManager(cfg)

    slug = vault.find_by_session_id(session_id)
    if not slug:
        sys.exit(0)

    # Always record a checkpoint marker in the vault note
    vault.append_compact_checkpoint(slug, transcript_path)

    # Auto-distill: open a summary window in the tmux session
    if cfg.distill == "auto" and tmux.session_exists(slug):
        tmux.open_distill_window(slug, session_id)

except Exception as e:
    print(f"loom pre-compact hook error: {e}", file=sys.stderr)

sys.exit(0)
