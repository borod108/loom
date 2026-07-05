---
number: 10
title: Configurable notification backends (notify-send, ntfy, bell)
status: accepted
date: 2026-07-05
---

# ADR-010: Configurable notification backends

## Context

Notifications need to work across different setups:
- Linux desktop: `notify-send` (freedesktop)
- Remote/headless: `ntfy.sh` push to phone
- Minimal/universal: terminal bell (`\a`)

The user wants all backends supported, configurable.

## Decision

`LOOM_NOTIFICATIONS` is a comma-separated list of enabled backends: `notify-send`, `ntfy`, `bell`. All listed backends fire for each notification. The `NotifyManager` class iterates the list and silently skips backends that fail (tool not installed, network error, etc.).

`ntfy.sh` config: `LOOM_NTFY_TOPIC` (topic name) and `LOOM_NTFY_SERVER` (default: `https://ntfy.sh`). A self-hosted ntfy instance is supported via `LOOM_NTFY_SERVER`.

## Consequences

**Positive:**
- Works in every environment: desktop, headless server, phone.
- ntfy is open-source and self-hostable (https://ntfy.sh) — no proprietary push service required.
- Failures are silent so a broken notification backend never breaks the workflow.

**Negative / trade-offs:**
- ntfy topic is public on ntfy.sh unless self-hosted or using ntfy's paid access control. Users handling sensitive project names should self-host.

## Status History

- 2026-07-05: accepted
