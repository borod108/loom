#!/usr/bin/env python3
"""Tests for StateManager — tasks.json cache operations."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from loom import Config, StateManager, VaultManager


def _make_cfg(tmpdir: str) -> Config:
    cfg = Config.__new__(Config)
    cfg._data = {
        "LOOM_VAULT": tmpdir,
        "LOOM_SESSION_PREFIX": "loom",
        "LOOM_WEB_PORT": "7799",
        "LOOM_WEB_BIND": "0.0.0.0",
        "LOOM_WEB_TOKEN": "",
        "LOOM_DISTILL": "auto",
        "LOOM_DISTILL_MODEL": "claude-sonnet-4-5",
        "LOOM_NOTIFICATIONS": "bell",
        "LOOM_NTFY_TOPIC": "loom",
        "LOOM_NTFY_SERVER": "https://ntfy.sh",
    }
    return cfg


class TestStateManager(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Override state dir to temp location
        os.environ["XDG_STATE_HOME"] = os.path.join(self.tmpdir, "state")
        os.makedirs(os.environ["XDG_STATE_HOME"], exist_ok=True)
        self.cfg = _make_cfg(self.tmpdir)
        self.state = StateManager(self.cfg)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)
        del os.environ["XDG_STATE_HOME"]

    def test_initial_empty(self):
        self.assertEqual(self.state.list_all(), {})

    def test_upsert_and_get(self):
        self.state.upsert("my-task", status="working", cwd="/tmp")
        entry = self.state.get("my-task")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["status"], "working")
        self.assertEqual(entry["cwd"], "/tmp")

    def test_upsert_updates_existing(self):
        self.state.upsert("task-a", status="starting")
        self.state.upsert("task-a", status="working")
        self.assertEqual(self.state.get("task-a")["status"], "working")

    def test_remove(self):
        self.state.upsert("remove-me", status="idle")
        self.state.remove("remove-me")
        self.assertIsNone(self.state.get("remove-me"))

    def test_remove_nonexistent_is_safe(self):
        self.state.remove("does-not-exist")  # Should not raise

    def test_list_all(self):
        self.state.upsert("task-1", status="working")
        self.state.upsert("task-2", status="waiting")
        all_tasks = self.state.list_all()
        self.assertIn("task-1", all_tasks)
        self.assertIn("task-2", all_tasks)

    def test_updated_timestamp_set(self):
        self.state.upsert("ts-task", status="idle")
        entry = self.state.get("ts-task")
        self.assertIn("updated", entry)
        self.assertRegex(entry["updated"], r"\d{4}-\d{2}-\d{2}T")

    def test_rebuild_from_vault(self):
        import shutil
        os.environ["LOOM_VAULT"] = self.tmpdir
        cfg = _make_cfg(self.tmpdir)
        vault = VaultManager(cfg)
        vault.ensure_structure()
        vault.create_task("rebuild-task", "uuid-rebuild", "/tmp/project")
        vault.update_task("rebuild-task", status="waiting")

        state = StateManager(cfg)
        state.rebuild_from_vault(vault)

        entry = state.get("rebuild-task")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.get("session_id"), "uuid-rebuild")

    def test_atomic_write(self):
        # Ensure .tmp file is not left behind on successful write
        self.state.upsert("atomic-task", status="working")
        state_dir = self.state._dir
        tmp_files = list(state_dir.glob("*.tmp"))
        self.assertEqual(tmp_files, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
