---
number: 2
title: Plain-Markdown vault with optional Obsidian viewing
status: accepted
date: 2026-07-05
---

# ADR-002: Plain-Markdown vault with optional Obsidian viewing

## Context

The user originally said "open-source Obsidian." Obsidian is proprietary (free for personal use, not open source). However, the Obsidian vault format is just a folder of plain Markdown files with YAML frontmatter and `[[wikilinks]]` — there is no proprietary data layer.

## Decision

Loom owns a plain Markdown directory on disk. The vault format follows Obsidian conventions (YAML frontmatter, `[[wikilinks]]`, PARA folder layout) so it renders correctly in Obsidian. However, there is no hard dependency on Obsidian.

The loom web UI renders vault notes in the browser, serving as the primary open-source viewer. Obsidian, Logseq, Foam for VS Code, or plain grep are all optional lenses.

No Obsidian plugins (Local REST API, Dataview) are required for core functionality.

## Consequences

**Positive:**
- Zero dependency on any proprietary app.
- Claude can search the vault natively via `Read`/`Grep`/`Glob`.
- The vault is a normal git repo — versioned, diffable, syncable.

**Negative / trade-offs:**
- Obsidian's graph view and Dataview queries are optional extras, not guaranteed to work without community plugins.

## Status History

- 2026-07-05: accepted
