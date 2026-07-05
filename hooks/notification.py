#!/usr/bin/env python3
"""Hook: Notification — forward Claude Code notifications through configured backends."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from _lib import setup

data = setup()

from loom import Config, VaultManager, NotifyManager

try:
    session_id   = data.get("session_id", "")
    notif_type   = data.get("type", "")          # permission_prompt | idle_prompt | …
    message      = data.get("message", "")
    event_name   = data.get("hook_event_name", "Notification")

    cfg    = Config()
    vault  = VaultManager(cfg)
    notify = NotifyManager(cfg)

    # Find task slug for context
    slug = ""
    if session_id:
        slug = vault.find_by_session_id(session_id) or ""

    # Build notification
    if notif_type == "permission_prompt":
        title   = f"loom: permission needed"
        body    = f"[{slug}] {message}" if slug else message
        urgency = "critical"
    elif notif_type == "idle_prompt":
        title   = f"loom: waiting for input"
        body    = f"[{slug}] Claude is waiting" if slug else "Claude is waiting"
        urgency = "normal"
    else:
        title   = f"loom: {notif_type or 'notification'}"
        body    = f"[{slug}] {message}" if slug else message
        urgency = "low"

    if title:
        notify.send(title, body, urgency=urgency)

except Exception as e:
    print(f"loom notification hook error: {e}", file=sys.stderr)

sys.exit(0)
