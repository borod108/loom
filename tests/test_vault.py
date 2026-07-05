#!/usr/bin/env python3
"""Tests for VaultManager — vault CRUD, frontmatter parsing, dashboard."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from loom import Config, VaultManager, _parse_frontmatter, _write_frontmatter, slugify, format_age


class TestFrontmatterParsing(unittest.TestCase):
    def test_parse_basic(self):
        content = "---\nstatus: working\nsession_id: abc\n---\n\n# Body"
        fields, body = _parse_frontmatter(content)
        self.assertEqual(fields["status"], "working")
        self.assertEqual(fields["session_id"], "abc")
        self.assertIn("# Body", body)

    def test_parse_no_frontmatter(self):
        fields, body = _parse_frontmatter("# Just a heading")
        self.assertEqual(fields, {})
        self.assertEqual(body, "# Just a heading")

    def test_write_roundtrip(self):
        fields = {"status": "waiting", "cwd": "/home/user"}
        body = "\n# My Task\n"
        result = _write_frontmatter(fields, body)
        parsed, parsed_body = _parse_frontmatter(result)
        self.assertEqual(parsed["status"], "waiting")
        self.assertEqual(parsed["cwd"], "/home/user")
        self.assertIn("# My Task", parsed_body)

    def test_parse_with_colon_in_value(self):
        content = "---\ncwd: /home/user/work:my-project\n---\n"
        fields, _ = _parse_frontmatter(content)
        self.assertEqual(fields["cwd"], "/home/user/work:my-project")


class TestSlugify(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify("Auth Refactor"), "auth-refactor")

    def test_special_chars(self):
        self.assertEqual(slugify("Fix: bug #123!"), "fix-bug-123")

    def test_truncation(self):
        long_name = "a" * 100
        self.assertLessEqual(len(slugify(long_name)), 60)

    def test_already_slug(self):
        self.assertEqual(slugify("my-task"), "my-task")


class TestFormatAge(unittest.TestCase):
    def test_seconds(self):
        from datetime import datetime, timezone, timedelta
        ts = (datetime.now(timezone.utc) - timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(format_age(ts), "30s")

    def test_minutes(self):
        from datetime import datetime, timezone, timedelta
        ts = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(format_age(ts), "5m")

    def test_hours(self):
        from datetime import datetime, timezone, timedelta
        ts = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(format_age(ts), "2h")

    def test_invalid(self):
        self.assertEqual(format_age("not-a-date"), "?")
        self.assertEqual(format_age(None), "?")


class TestVaultManager(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cfg = Config.__new__(Config)
        self.cfg._data = {
            "LOOM_VAULT": self.tmpdir,
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
        self.vault = VaultManager(self.cfg)
        self.vault.ensure_structure()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_ensure_structure_creates_dirs(self):
        for d in VaultManager.DIRS:
            self.assertTrue((Path(self.tmpdir) / d).is_dir(), f"Missing dir: {d}")

    def test_create_task(self):
        path = self.vault.create_task("test-task", "session-uuid", "/home/user/proj", "Do the thing")
        self.assertTrue(path.exists())
        content = path.read_text()
        self.assertIn("session_id: session-uuid", content)
        self.assertIn("status: starting", content)
        self.assertIn("Do the thing", content)

    def test_create_task_duplicate_raises(self):
        self.vault.create_task("dup-task", "uuid1", "/tmp")
        with self.assertRaises(FileExistsError):
            self.vault.create_task("dup-task", "uuid2", "/tmp")

    def test_get_task(self):
        self.vault.create_task("get-test", "uuid-get", "/tmp/project")
        task = self.vault.get_task("get-test")
        self.assertIsNotNone(task)
        self.assertEqual(task["session_id"], "uuid-get")
        self.assertEqual(task["slug"], "get-test")

    def test_get_task_not_found(self):
        self.assertIsNone(self.vault.get_task("nonexistent"))

    def test_update_task_status(self):
        self.vault.create_task("upd-test", "uuid-upd", "/tmp")
        self.vault.update_task("upd-test", status="working")
        task = self.vault.get_task("upd-test")
        self.assertEqual(task["status"], "working")

    def test_list_tasks(self):
        self.vault.create_task("task-a", "uuid-a", "/tmp/a")
        self.vault.create_task("task-b", "uuid-b", "/tmp/b")
        tasks = self.vault.list_tasks()
        slugs = [t["slug"] for t in tasks]
        self.assertIn("task-a", slugs)
        self.assertIn("task-b", slugs)

    def test_find_by_session_id(self):
        self.vault.create_task("find-test", "unique-uuid-123", "/tmp")
        slug = self.vault.find_by_session_id("unique-uuid-123")
        self.assertEqual(slug, "find-test")

    def test_find_by_session_id_not_found(self):
        self.assertIsNone(self.vault.find_by_session_id("nonexistent-uuid"))

    def test_archive_task(self):
        self.vault.create_task("arch-test", "uuid-arch", "/tmp")
        self.vault.archive_task("arch-test")
        self.assertFalse(self.vault.task_path("arch-test").exists())
        self.assertTrue(self.vault.archive_path("arch-test").exists())

    def test_rebuild_dashboard(self):
        self.vault.create_task("dash-task", "uuid-dash", "/tmp/proj")
        dash = Path(self.tmpdir) / "00-Dashboard" / "Active Tasks.md"
        content = dash.read_text()
        self.assertIn("dash-task", content)

    def test_append_log(self):
        self.vault.create_task("log-test", "uuid-log", "/tmp")
        self.vault.append_log("log-test", "Something happened")
        content = self.vault.task_path("log-test").read_text()
        self.assertIn("Something happened", content)

    def test_append_compact_checkpoint(self):
        self.vault.create_task("compact-test", "uuid-c", "/tmp")
        self.vault.append_compact_checkpoint("compact-test", "/path/to/transcript.jsonl")
        content = self.vault.task_path("compact-test").read_text()
        self.assertIn("transcript.jsonl", content)
        self.assertIn("Compaction checkpoint", content)

    def test_next_adr_number_empty(self):
        self.assertEqual(self.vault.next_adr_number(), 1)

    def test_next_adr_number_increments(self):
        self.vault.create_adr("First Decision")
        self.assertEqual(self.vault.next_adr_number(), 2)

    def test_is_initialized(self):
        self.assertTrue(self.vault.is_initialized())

    def test_is_not_initialized(self):
        import shutil
        shutil.rmtree(Path(self.tmpdir) / "10-Tasks")
        self.assertFalse(self.vault.is_initialized())


if __name__ == "__main__":
    unittest.main(verbosity=2)
