# PandaPlot - Agent Instructions

This document provides instructions and guidelines for AI agents working in this repository.

## Project Overview
PandaPlot is an educational scientific visualization and analysis application built with Python, PySide6 (Qt), Matplotlib, Pandas, SciPy, NumPy, and Statsmodels.

## Package & Environment Management
We use **uv** for dependency management. Always run commands through `uv run` or within the synchronized environment.

```bash
uv sync                  # Install dependencies
uv sync --group dev      # Install dev dependencies
uv add <package>         # Add a new dependency
```

## Running the Application
```bash
uv run python -m pandaplot.app
```

## Running Tests
In headless environments (CI, agent sandboxes, SSH servers), set `QT_QPA_PLATFORM=offscreen` when running PySide6 GUI tests:

```bash
QT_QPA_PLATFORM=offscreen uv run pytest
QT_QPA_PLATFORM=offscreen uv run pytest tests/gui/
QT_QPA_PLATFORM=offscreen uv run pytest --cov=pandaplot
```

## Code Quality & Formatting
Run linting checks before finalizing changes:

```bash
uv run ruff check .                     # Lint check
uv run ruff check --fix .               # Lint auto-fix
uv run ruff check --select I --fix .     # Auto-sort imports
```

## Architectural Patterns
- **Architecture:** MVC, Clean Architecture, Event-Driven, Command Pattern.
- **Event Bus:** Prefer the application `EventBus` (`pandaplot/models/events/event_bus.py`) over direct Qt signals/slots for decoupled inter-component communication.
- **Dependency Injection:** `AppContext` (`pandaplot/models/state/app_context.py`) centralizes core managers and services.
- **Command Pattern:** Undoable/redoable operations are implemented via `Command`, `CommandExecutor`, and `CompositeCommand` (`pandaplot/commands/`).
- **Separation of Concerns:** Models store state; GUI handles rendering and user input; Services contain business logic; Analysis handles computational math/stats.

## Code Conventions
- **Python Version:** Python >= 3.12 syntax and features.
- **Type Hints:** Required on all function parameters and return types.
- **Line Length:** 150 characters maximum (enforced by `ruff`).
- **Boolean Parameters:** Make boolean parameters keyword-only (`def f(x, *, enabled: bool = True)`) to comply with `ruff` `FBT` (flake8-boolean-trap) rules.
  - If a function overrides a Qt virtual method or is connected directly to a Qt signal, append `# noqa: FBT00x` with a brief comment explaining why.
- **Positional Arguments:** Prefer keyword arguments at call sites when passing multiple consecutive arguments of the same type.
- **Naming Conventions:**
  - `PascalCase` for classes
  - `snake_case` for functions, variables, and methods
  - `_leading_underscore` for private methods and attributes
- **Logging:** Use class-level loggers (`self.logger = logging.getLogger(self.__class__.__name__)`).
- **Docstrings:** Use Google style docstrings (`Args:`, `Returns:`, `Raises:` sections).

## Project Structure
- `pandaplot/` - Main application package
  - `app.py` - Application entry point
  - `analysis/` - Data analysis engine (derivatives, fits, transforms, smoothing)
  - `commands/` - Command pattern implementations for undo/redo
  - `gui/` - PySide6 Qt GUI (views, controllers, dialogs, custom widgets)
  - `models/` - Data models (chart, dataset, event bus, state, project)
  - `services/` - Business logic (data managers, export, theme, fit service)
  - `storage/` - Persistence layer (project and dataset load/save)
  - `utils/` - Shared utilities and helpers
- `tests/` - Pytest test suite mirroring `pandaplot/`
- `pandaplot_storybook/` - Standalone PySide6 component storybook subpackage
- `docs/` - Architecture, user guide, and design specifications
