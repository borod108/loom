#!/usr/bin/env python3
"""loom web UI server — read/write access to tasks via HTTP.

Endpoints:
  GET  /                          → index.html
  GET  /api/tasks                 → JSON list of tasks
  GET  /api/tasks/<slug>          → task detail + pane preview
  POST /api/tasks/<slug>/send     → send input to session  {text, enter}
  DELETE /api/tasks/<slug>        → kill session
  GET  /api/health                → {ok, version}
"""

import argparse
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Resolve lib path
_DIR = Path(__file__).resolve().parent
_LIB = _DIR.parent / "lib"
sys.path.insert(0, str(_LIB))

from loom import Config, VaultManager, StateManager, TmuxManager, NotifyManager, format_age

VERSION = "0.1.0"

# ---------------------------------------------------------------------------
# Global managers (shared across requests)
# ---------------------------------------------------------------------------

_cfg: Config
_vault: VaultManager
_state: StateManager
_tmux: TmuxManager

STATIC_DIR = _DIR / "static"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _check_auth(handler: "LoomHandler") -> bool:
    token = _cfg.web_token
    if not token:
        return True  # No auth configured

    # Check query param
    qs = parse_qs(urlparse(handler.path).query)
    if qs.get("token", [""])[0] == token:
        return True

    # Check Authorization header
    auth = handler.headers.get("Authorization", "")
    if auth == f"Bearer {token}":
        return True

    return False


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _json_response(handler: "LoomHandler", data, status: int = 200):
    body = json.dumps(data, indent=2).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


def _error(handler: "LoomHandler", msg: str, status: int = 400):
    _json_response(handler, {"error": msg}, status)


def _read_body(handler: "LoomHandler") -> dict:
    length = int(handler.headers.get("Content-Length", 0))
    if not length:
        return {}
    try:
        return json.loads(handler.rfile.read(length))
    except (json.JSONDecodeError, ValueError):
        return {}


# ---------------------------------------------------------------------------
# API handlers
# ---------------------------------------------------------------------------

def _build_task_summary(slug: str, fields: dict) -> dict:
    alive    = _tmux.session_exists(slug)
    status   = fields.get("status", "unknown")
    archived = fields.get("_archived", False)
    # Compute display status
    if status in ("idle", "starting") and not alive and not archived:
        display_status = "dead"
    elif archived:
        display_status = "done"
    else:
        display_status = status
    return {
        "slug":           slug,
        "status":         display_status,
        "raw_status":     status,
        "archived":       archived,
        "project":        fields.get("project", ""),
        "cwd":            fields.get("cwd", ""),
        "model":          fields.get("model", ""),
        "started":        fields.get("started", ""),
        "updated":        fields.get("updated", ""),
        "age":            format_age(fields.get("updated") or fields.get("started", "")),
        "session":        _tmux.session_name(slug),
        "alive":          alive,
        "session_id":     fields.get("session_id", ""),
    }


def api_tasks_list(handler: "LoomHandler"):
    qs = parse_qs(urlparse(handler.path).query)
    include_all = qs.get("all", [""])[0] in ("1", "true")
    tasks = _vault.list_tasks(include_archived=include_all)
    result = []
    for t in tasks:
        slug = t.pop("slug", None)
        t.pop("body", None)
        t.pop("path", None)
        if slug:
            result.append(_build_task_summary(slug, t))
    _json_response(handler, result)


def api_task_detail(handler: "LoomHandler", slug: str):
    task = _vault.get_task(slug)
    if not task:
        _error(handler, f"Task not found: {slug}", 404)
        return

    detail = _build_task_summary(slug, task)
    detail["goal"]    = ""
    detail["body"]    = task.get("body", "")
    detail["preview"] = ""

    # Extract goal from body
    body = task.get("body", "")
    m = __import__("re").search(r"## Goal\n\n(.*?)(?:\n##|\Z)", body, __import__("re").DOTALL)
    if m:
        detail["goal"] = m.group(1).strip()

    # Live pane preview if session is alive
    if detail["alive"]:
        detail["preview"] = _tmux.capture_pane(slug, lines=30)

    _json_response(handler, detail)


def api_task_send(handler: "LoomHandler", slug: str):
    body = _read_body(handler)
    text = body.get("text", "").strip()
    enter = body.get("enter", True)

    if not text:
        _error(handler, "Missing 'text' field")
        return

    if not _tmux.session_exists(slug):
        _error(handler, f"No live session for '{slug}'", 409)
        return

    ok = _tmux.send_keys(slug, text, enter=enter)
    if ok:
        _json_response(handler, {"ok": True})
    else:
        _error(handler, "Failed to send keys", 500)


def api_task_kill(handler: "LoomHandler", slug: str):
    if not _tmux.session_exists(slug):
        _error(handler, f"No live session for '{slug}'", 409)
        return

    ok = _tmux.kill_session(slug)
    if ok:
        _vault.update_task(slug, status="idle")
        _state.upsert(slug, status="idle")
        _json_response(handler, {"ok": True})
    else:
        _error(handler, "Failed to kill session", 500)


def api_health(handler: "LoomHandler"):
    _json_response(handler, {
        "ok": True,
        "version": VERSION,
        "vault": str(_vault.vault),
        "vault_initialized": _vault.is_initialized(),
    })


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

class LoomHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        ts = time.strftime("%H:%M:%S")
        print(f"  [{ts}] {fmt % args}")

    def _route(self, method: str):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/")

        # Auth check
        if not _check_auth(self):
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Bearer realm="loom"')
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        # CORS preflight
        if method == "OPTIONS":
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.end_headers()
            return

        # API routes
        if path == "/api/health" and method == "GET":
            api_health(self)
        elif path == "/api/tasks" and method == "GET":
            api_tasks_list(self)
        elif path.startswith("/api/tasks/") and method == "GET":
            parts = path.split("/")
            slug = parts[3] if len(parts) > 3 else ""
            if slug:
                api_task_detail(self, slug)
            else:
                _error(self, "Missing slug")
        elif path.endswith("/send") and method == "POST":
            slug = path.split("/")[3] if len(path.split("/")) > 3 else ""
            api_task_send(self, slug)
        elif path.startswith("/api/tasks/") and method == "DELETE":
            slug = path.split("/")[3] if len(path.split("/")) > 3 else ""
            api_task_kill(self, slug)

        # Static files
        elif method == "GET":
            self._serve_static(path)
        else:
            _error(self, "Not found", 404)

    def _serve_static(self, path: str):
        if path == "/" or path == "":
            path = "/index.html"
        file_path = STATIC_DIR / path.lstrip("/")
        if not file_path.exists() or not file_path.is_file():
            _error(self, "Not found", 404)
            return

        ext = file_path.suffix.lower()
        mime = {
            ".html": "text/html; charset=utf-8",
            ".css":  "text/css",
            ".js":   "application/javascript",
            ".ico":  "image/x-icon",
            ".png":  "image/png",
            ".svg":  "image/svg+xml",
        }.get(ext, "application/octet-stream")

        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):    self._route("GET")
    def do_POST(self):   self._route("POST")
    def do_DELETE(self): self._route("DELETE")
    def do_OPTIONS(self):self._route("OPTIONS")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    global _cfg, _vault, _state, _tmux

    parser = argparse.ArgumentParser(description="loom web UI server")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--bind", default=None)
    args = parser.parse_args()

    _cfg   = Config()
    _vault = VaultManager(_cfg)
    _state = StateManager(_cfg)
    _tmux  = TmuxManager(_cfg)

    port = args.port or _cfg.web_port
    bind = args.bind or _cfg.web_bind

    server = HTTPServer((bind, port), LoomHandler)
    print(f"loom web UI — http://{bind}:{port}")
    if _cfg.web_token:
        print(f"Auth: Bearer token required (set LOOM_WEB_TOKEN)")
    server.serve_forever()


if __name__ == "__main__":
    main()
