---
number: 6
title: Web UI — accessible, mobile-friendly, with basic session actions
status: accepted
date: 2026-07-05
---

# ADR-006: Web UI — accessible, mobile-friendly, with basic session actions

## Context

Requirements from the user:
- Accessible from LAN and future remote setup (not just localhost).
- Must work on mobile (phone).
- Should support basic actions: view status, kill session, send input.
- Future: a remote server setup where the web UI server proxies to the machine running tmux sessions.

## Decision

The web UI is a Python stdlib HTTP server (`web/server.py`) binding to `0.0.0.0` by default. It serves a responsive single-page application built with vanilla HTML/CSS/JS (no build chain). Actions are REST: `POST /api/tasks/<slug>/send`, `DELETE /api/tasks/<slug>`.

Optional token auth (`LOOM_WEB_TOKEN`) via query param (`?token=…`) or `Authorization: Bearer` header. The URL-with-token pattern works on mobile without any special client setup.

Status updates use AJAX polling (3-second interval) rather than WebSockets — simpler, works everywhere including mobile and across NAT without persistent connections.

## Consequences

**Positive:**
- Zero external dependencies for the server.
- Works on any device with a browser.
- Token-in-URL makes bookmarking trivial on mobile.

**Negative / trade-offs:**
- Polling is less real-time than WebSockets (3s lag). Acceptable for a monitoring UI.
- "Attach" action from the browser can only suggest the CLI command (can't open a terminal directly). The `attach` button shows the `loom go <slug>` command.

**Future (v2):** WebSocket support for real-time streaming; SSH reverse tunnel setup for the remote-server scenario.

## Status History

- 2026-07-05: accepted
