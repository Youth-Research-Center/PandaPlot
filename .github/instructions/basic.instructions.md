---
applyTo: '**'
---

## Source of truth
Read `AGENTS.md` at the repository root first: it holds the conventions, commands, and the "Recurring Review Pitfalls" checklist. When reviewing a PR, check the change against that checklist (command results and redo semantics, async/stale callbacks, event payloads and refresh coverage, serialization round-trips, accessibility, test fidelity, PR description accuracy). The summary below may lag behind it.

## Context
Project Type: GUI application for scientific data visualization and analysis inspired by SigmaPlot, OriginPro, and LabPlot.
Language: Python (>= 3.12)
Framework / Libraries: PySide6, Matplotlib, NumPy, Pandas, SciPy, Statsmodels
Architecture: MVC, Clean Architecture, Event-Driven, Command pattern

## General Guidelines
- Use Pythonic patterns (PEP 8, PEP 257) with Python >= 3.12 features.
- Prefer named functions and class-based structures over inline lambdas.
- Use type hints on all function parameters and return types.
- Follow `ruff` for linting, code formatting, and import sorting (max line length = 150).
- Keyword-only booleans: Make boolean parameters keyword-only (`def f(*, flag: bool)`) to adhere to `FBT` rules unless overriding a Qt method.
- Prefer keyword arguments at call sites when passing multiple arguments of similar type.
- Emphasize simplicity, readability, and DRY principles.
- Prefer existing `EventBus` (`pandaplot/models/events/event_bus.py`) implementation over raw Qt signals and slots for component communication.

### Python Environment & Package Manager
- We use **uv** for dependency management. Always run commands with `uv run`.

## Running the Application

### Primary Application Entry Point
```bash
uv run python -m pandaplot.app
```

## Running Tests
In headless environments (CI, remote servers, agent sandboxes), export or prefix `QT_QPA_PLATFORM=offscreen`:

```bash
QT_QPA_PLATFORM=offscreen uv run pytest
```

## Static Analysis & Quality Checks
```bash
uv run ruff check .
```
The repo has no `ruff format` step.

## Project Structure

### Core Modules
- `pandaplot/` - Main application package
  - `app.py` - Application entry point & AppContext initialization
  - `analysis/` - Math and statistical analysis routines
  - `commands/` - Undoable command implementations
  - `gui/` - PySide6 user interface components & controllers
  - `models/` - Data models (chart, dataset, event bus, state, project)
  - `services/` - Business logic, configuration, themes, data managers
  - `storage/` - Persistence layer
  - `utils/` - Utility functions and helpers
- `tests/` - Test suite mirroring `pandaplot/` package structure
- `pandaplot_storybook/` - Standalone PySide6 component storybook
