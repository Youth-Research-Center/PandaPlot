# PandaPlot - Claude Code Instructions

@AGENTS.md

## Claude Code Notes
- `AGENTS.md` is the single source of truth for conventions and review pitfalls. Change shared guidance there; keep this file for Claude Code-specific notes only.
- Follow existing patterns and keep changes focused; do not add abstractions the task does not need.
- For a bug, reproduce it with a failing test first, then fix it.
- Before declaring work done, run `uv run ruff check .` and the relevant tests (with `QT_QPA_PLATFORM=offscreen`), and report failures honestly.
