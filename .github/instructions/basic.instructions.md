---
applyTo: '**'
---

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
