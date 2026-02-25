# PandaPlot - Claude Code Instructions

## Project Overview
PandaPlot is an educational scientific visualization and analysis application built with Python and PySide6 (Qt).

## Running the App
```bash
python -m pandaplot.app
```

## Package Manager
We use **uv** for dependency management.
```bash
uv sync                  # Install dependencies
uv sync --group dev      # Install with dev dependencies
uv add <package>         # Add a new dependency
```

## Tech Stack
- **Python** >=3.12
- **GUI:** PySide6
- **Plotting:** matplotlib
- **Data:** pandas, pyarrow, openpyxl
- **Scientific:** scipy, statsmodels
- **Linting:** ruff (line-length = 150)
- **Testing:** pytest, pytest-mock, pytest-cov, pytest-asyncio
- **Security:** bandit, pip-audit

## Linting & Formatting
```bash
ruff check .              # Lint check
ruff check --fix .        # Lint and auto-fix
ruff check --select I .   # Check import sorting only
ruff check --select I --fix .  # Auto-sort imports
```

## Testing
```bash
pytest                    # Run all tests
pytest --cov=pandaplot    # With coverage
```
Tests live in `tests/` and mirror the main package structure.

## Project Structure
- `pandaplot/` - Main application package
  - `app.py` - Entry point (builds AppContext, launches Qt event loop)
  - `analysis/` - Data analysis engine
  - `commands/` - Command pattern (undo/redo support)
  - `gui/` - Qt GUI (main window, components, controllers, dialogs)
  - `models/` - Data models (chart, events, project, state)
  - `services/` - Business logic (config, data managers, fit, theme)
  - `storage/` - Persistence layer
  - `utils/` - Logging, pandas helpers
- `tests/` - Test suite
- `examples/` - Example projects and datasets

## Architecture
- Event-driven via EventBus for inter-component communication
- AppContext provides dependency injection for all core managers
- Command pattern for undoable operations
- Clear separation: models / views / controllers / services

## Code Conventions
- Type hints on all function parameters and return types
- Naming: PascalCase classes, snake_case functions, _private methods
- Line length: 150 characters (enforced by ruff)
- Logging: `self.logger = logging.getLogger(self.__class__.__name__)`
- Docstrings: NumPy/Google style with Args, Returns, Notes sections
- Follow existing patterns — don't over-engineer or add unnecessary abstractions
