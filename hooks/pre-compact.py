#!/usr/bin/env python3
"""Hook: PreCompact — extract and save knowledge before context is compacted away.

This is the most important hook for the second brain: the transcript is about
to be trimmed, so we parse it now and write a checkpoint summary to the vault.
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from _lib import setup

data = setup()

from loom import Config, VaultManager, StateManager, TmuxManager, _now_iso

try:
    session_id      = data.get("session_id", "")
    transcript_path = data.get("transcript_path", "")

    if not session_id:
        sys.exit(0)

    cfg   = Config()
    vault = VaultManager(cfg)
    state = StateManager(cfg)
    tmux  = TmuxManager(cfg)

    slug = vault.find_by_session_id(session_id)
    if not slug:
        sys.exit(0)

    # Always record the compaction checkpoint marker
    vault.append_compact_checkpoint(slug, transcript_path)

    # Parse the transcript and extract the last N Claude responses as a snapshot.
    # This saves the recent work before the context window is trimmed.
    snapshot_lines = []
    if transcript_path and os.path.exists(transcript_path):
        try:
            messages = []
            with open(transcript_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        messages.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

            # Collect the last few assistant text blocks before compaction.
            # Transcript lines wrap the API message: {"type": "assistant",
            # "message": {"role": "assistant", "content": [...]}, ...}
            recent = []
            for msg in messages[-40:]:
                if msg.get("type") != "assistant":
                    continue
                content = msg.get("message", {}).get("content", [])
                if isinstance(content, str):
                    recent.append(content.strip())
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            txt = block.get("text", "").strip()
                            if txt and not txt.startswith("{"):  # skip JSON tool outputs
                                recent.append(txt)

            if recent:
                snapshot_lines.append(f"\n\n### Compaction snapshot — {_now_iso()[:16]}\n")
                snapshot_lines.append(f"> Transcript: `{transcript_path}`\n")
                snapshot_lines.append("\n**Recent Claude output (last turns saved before compaction):**\n")
                for i, txt in enumerate(recent[-3:], 1):
                    excerpt = txt[:600] + ("…" if len(txt) > 600 else "")
                    snapshot_lines.append(f"\n{i}. {excerpt}\n")

        except Exception as parse_err:
            snapshot_lines.append(
                f"\n\n_Compaction at {_now_iso()[:16]} — transcript unreadable: {parse_err}_\n"
            )

    # Append the snapshot to the vault note
    if snapshot_lines:
        task_path = vault.task_path(slug)
        if task_path.exists():
            existing = task_path.read_text()
            task_path.write_text(existing + "".join(snapshot_lines))

    # Optionally open an interactive distillation window for the user
    if cfg.distill == "auto" and tmux.session_exists(slug):
        task = vault.get_task(slug) or {}
        tmux.open_distill_window(slug, session_id, cwd=task.get("cwd", ""))

except Exception as e:
    print(f"loom pre-compact hook error: {e}", file=sys.stderr)

sys.exit(0)
