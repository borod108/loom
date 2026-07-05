"""Shared bootstrap for loom hook scripts."""

import json
import os
import sys
from pathlib import Path


def find_lib() -> Path:
    """Locate loom lib directory via config file or env var."""
    loom_dir = os.environ.get("LOOM_DIR", "")
    if not loom_dir:
        config_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "loom"
        loom_dir_file = config_dir / "loom_dir"
        if loom_dir_file.exists():
            loom_dir = loom_dir_file.read_text().strip()
    if loom_dir:
        return Path(loom_dir) / "lib"
    # Fallback: assume hooks/ is a sibling of lib/
    return Path(__file__).resolve().parent.parent / "lib"


def setup():
    """Add loom lib to sys.path and return parsed hook input from stdin."""
    lib_path = find_lib()
    if str(lib_path) not in sys.path:
        sys.path.insert(0, str(lib_path))
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        data = {}
    return data
