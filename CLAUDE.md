# PandaPlot - Claude Code Instructions

@AGENTS.md

## Claude Code Notes
- `AGENTS.md` is the single source of truth for conventions and review pitfalls. Change shared guidance there; keep this file for Claude Code-specific notes only.
- Follow existing patterns and keep changes focused; do not add abstractions the task does not need.
- For a bug, reproduce it with a failing test first, then fix it.
- Before declaring work done, run `uv run ruff check .`, `uv run ruff check --select W291,W292,W293 <files you changed>` (CI does not select `W`, reviewers still flag it), and the relevant tests (with `QT_QPA_PLATFORM=offscreen`), and report failures honestly.
- Before opening or updating a PR, read the AGENTS.md pitfalls subsection for each area you touched, then sweep sibling code for the same defect class (all `Command` subclasses, all subscribers of an event, all series renderers, every `undo()`/`redo()` replay path).
- Verify a review finding against the code before acting on it, and reproduce it when you can. Some automated findings are wrong (a second `CONFIG_RESET` subscription would double-fire through `EventHierarchy`; the storybook import order is correct under its own ruff config). Reply with the evidence instead of changing the code.
- When asked to review a PR, report findings in chat first; post to GitHub only when explicitly asked.
