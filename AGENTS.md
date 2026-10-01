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

## Code Quality
The repo has no `ruff format` step; `ruff check` (rules `E`, `F`, `B`, `Q`, `I`, `FBT`) is the only gate. Run it, plus the tests for the code you touched, before every push. Unsorted imports (`I001`), unused imports (`F401`) and missing `noqa` on Qt overrides are the most common avoidable review comments:

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

## Recurring Review Pitfalls
These come from review comments (mostly Copilot's) on previous merged PRs. Each was a real defect or a repeated nit that cost a review round. Check your change against them before opening or updating a PR.

### Commands (`pandaplot/commands/`)
- Every `execute()`/`undo()`/`redo()` returns an explicit `CommandResult` on **every** path (see `base_command.py`). Never return `None`/`bool`, and never test a result by truthiness: every member is truthy, so use `is CommandResult.SUCCESS`.
- Return `NOOP` when nothing changed (renaming to the same name, converting to the same dtype, resizing to the current size) so no misleading history entry is created. Use `FAILURE` only for a real error, and `ABORTED` only from `undo()`/`redo()` when a precondition refused to make any change.
- Do not assign `self.dataset`, `self.project`, or other "executed" state until the mutation has actually succeeded; otherwise `undo()`/`redo()` act on a failed `execute()`. Guard with `is not None`, not truthiness (`0` and `""` are valid column labels).
- `redo()` must replay the original action, not blindly re-run `execute()`: do not mint new item IDs, re-open dialogs, re-snapshot "before" state, or build a new object. Later commands in the history reference the original IDs and objects.
- Multi-step mutations must be transactional: if step N raises, restore steps 1..N-1 (including parent `modified_at` and ordering) and report failure. Never leave an orphaned or half-edited item. If a command cascades to dependents (charts, fits, error or confidence columns), undo must restore all of them.
- Override `cleanup()` to drop large retained state (DataFrames, arrays, dialogs, cached projects). Override `occupies_undo_slot()` / `marks_project_modified()` for commands that are not real undoable edits (dialog openers, lifecycle commands, pure computation). Exceptions in `cleanup()` or in user-facing hooks must not break the executor.
- Background commands: capture the project (and `modification_revision`) at dispatch and validate it in the completion callback; never re-resolve `app_state.current_project` when the result arrives. Do not mutate command state or emit events from the worker thread; return data in the result payload and apply it on the main thread. Reset any "running" flag if dispatch itself raises, and before invoking user callbacks that may re-dispatch.
- Add tests for undo **and** redo of any new command or cascade, including the failure path.

### Events (`pandaplot/models/events/`)
- Payload keys must match what subscribers read (e.g. `PROJECT_ITEM_REMOVED` consumers need `item_id`). When you emit an event from a new code path, check every subscriber of that event and of its parents in `EventHierarchy`.
- UI that displays names, labels, or chart/dataset lists must refresh on **all** events that can change them (created, renamed, moved, removed, retyped, data changed), not only the one you tested.
- When retiring an event, remove it from `EventHierarchy.HIERARCHY_MAP` and every subscriber. Emit from the main thread only. Iterate over snapshots when callbacks may subscribe or unsubscribe.
- Anything that is not a `WidgetExtension` but subscribes (table models, floating windows) must unsubscribe when destroyed.

### Models, persistence, and migrations
- `to_dict()`/`from_dict()` must round-trip every new field, and the result must be JSON-safe (NumPy/pandas nullable values, NaN, and tuples converted). Add a round-trip test.
- Deserialization is resilient: unknown or invalid enum values, missing keys, and legacy keys fall back to defaults or are migrated (e.g. `show_grid` to `show_grid_x`/`show_grid_y`) instead of raising. Reject, rather than silently open, project files whose `schema_version` is newer than `CURRENT_SCHEMA_VERSION`. Persisted-format changes need a migration under `pandaplot/models/migrations/` plus a test; do not weaken migration assertions to subset checks.
- New column references must be handled by `DeleteColumnsCommand`, `RenameColumnCommand`, `Chart.retype_series()`, `snapshot_chart_state()`/`restore_chart_state()`, and copy/transform commands (carry over `y_axis`, style, and error/confidence columns consistently, or clear them deliberately).
- No mutable containers in frozen dataclasses (use `frozenset`/tuples). Validate invariants (e.g. style class vs `series_type`) in `__post_init__`. Prefer typed dataclasses and enums over string-keyed dicts and magic strings, and pass required values via the constructor instead of mutating afterwards.
- Names are not unique: projects allow duplicate item names. Use `pandaplot/utils/item_display_options.py` (`dataset_display_options`, `chart_display_options`, `disambiguated_display_options`) for any picker, and `get_chart_type_spec(chart_type).display_name`, never `value.capitalize()`, for chart-type labels.
- Never `eval()` user input without an AST allowlist; omitting `__builtins__` does not make `eval` safe.

### GUI (`pandaplot/gui/`)
- Keep computation and business logic out of widgets. Put it in a service or analysis class (invoked from a command) and keep the widget to rendering and input.
- Async results are stale by the time they arrive. Capture a context token (chart, series, dataset and column ids, dispatch parameters) at dispatch, compare it on completion, and ignore mismatches. Restore button enabled-state from the *current* context, disable every action that would start a competing operation, and keep busy indicators running until the pending command actually completes.
- Guard against empty or NaN data before `min()`/`max()`, division, or `median()`. Drop non-finite rows before building grids, coerce column data with `pd.to_numeric` before passing it to Matplotlib, and fail with a clear message instead of a chart-wide exception.
- Qt hygiene:
  - Parent `QAction`s to the menu that owns them so `QMenu.clear()` deletes them; enable menu tooltips explicitly if you set them.
  - Use `blockSignals` when setting several linked controls, then apply the change once. Do not connect a signal twice (`PButton(on_click=...)` already connects `clicked`).
  - Guard slots that may run during teardown with `shiboken6.isValid`. Do not swallow exceptions with a bare `except`/`pass`; log them.
  - Do not clear a whole stylesheet to remove one color; restore the themed stylesheet and clear stale error text and icons too.
  - Do not rely on private attributes of third-party widgets (e.g. the Matplotlib toolbar's `_actions`) without a guard.
  - Reuse existing base classes and helpers (`SidebarPanel._set_content`, `PButton`, `WidgetExtension`) instead of ad hoc containers.
- Accessibility: every icon-only, custom-painted, or card-style (`QPushButton` with child labels) control needs `setAccessibleName`/`setAccessibleDescription` and must be keyboard-focusable and activatable. Use a native checkable control instead of a bare `QWidget` toggle, and expose busy/status indicators to assistive technology.
- Add new constructor or function parameters as keyword-only and **after** existing ones so positional callers do not break.
- Units and wording must be consistent (do not mix cm and inches), and a setting shown in a dialog must actually be persisted and applied.

### Chart rendering (`gui/components/tabs/chart/`)
- Series renderers draw on the series' own target axes (primary or secondary), and honor `alpha`, visibility, series order (`zorder`), and the series or marker color. Value labels, error bars, histograms, and fits follow the same rules as the main artist.
- Reset Matplotlib state you changed (locators, formatters, GridSpec, secondary axes, mathtext parsing) when a setting returns to auto/default, because `update_chart()` reuses axes.
- Interactions (hover, pick) must respect toolbar pan/zoom mode, flush the final throttled event, and work for legends placed outside the axes.

### Tests (`tests/`)
- Mirror production shapes in mocks (`FitResult.params` is a dict; commands return `CommandResult`). A fake that differs from production hides the bug the test claims to cover. Fakes for schedulers and executors must clean up on every path (success, error, cancel, callback raising), like production.
- Every bug fix gets a regression test that fails without the fix. Assert semantics (full `Series`/dtype equality, parameters actually forwarded, call counts), not a marker such as `dtype == "category"`.
- Bound anything that can hang: finite deadlines in worker stubs, `timeout=` on subprocesses, and `QT_QPA_PLATFORM=offscreen` for subprocess Qt tests. Put fixture teardown in `try/finally`.
- Do not weaken an existing assertion to make a test pass; add an explicit exclusion instead.

### Code hygiene
- No commented-out code, `print()` or debug logging, `TODO` comments that express uncertainty, or references to gitignored or local-only files (link an issue number instead). No duplicate imports; keep stdlib / third-party / local order (`ruff check --select I --fix .`).
- Prefer a dict or enum over long `if/elif` chains on strings, and extract lists or constants used in more than one place.
- Docstrings and comments must describe what the code does *now*. Stale docstrings and type annotations after a refactor are a frequent finding.
- CI workflows (`.github/workflows/`): never interpolate `${{ inputs.* }}` or `github.event.*` into shell source; pass them via `env:` and quote the variable. Use forward slashes in paths that run on Linux/macOS (e.g. `pysidedeploy.spec`), archive directories (such as macOS `.app` bundles) before uploading artifacts so permissions survive, and revert files that tools rewrite locally before committing.

## Pull Requests
- The PR description must match what the PR actually does. Update it when scope changes during review (features added, removed, or deferred; test counts; behavior such as inclusive vs. exclusive ranges). Reviewers flag every mismatch.
- Keep a PR to one concern, and call out known gaps and pre-existing issues explicitly instead of leaving them for a reviewer to find.
- Fix valid review comments with a regression test; if you disagree, reply with the reasoning. When a comment names a bug class, audit sibling code for the same defect (all `Command` subclasses, all subscribers of an event) in the same PR.
- Before pushing: `uv run ruff check .` and `QT_QPA_PLATFORM=offscreen uv run pytest <touched test dirs>`.
