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
QT_QPA_PLATFORM=offscreen uv run pytest tests/e2e/
QT_QPA_PLATFORM=offscreen uv run pytest --cov=pandaplot
QT_QPA_PLATFORM=offscreen uv run pytest -n 0 tests/gui/test_axes_tab.py   # serial: for --pdb and IDE debuggers
```

pytest runs in parallel by default (`pytest-xdist`, `addopts` in `pyproject.toml`:
`-n auto --maxprocesses=8 --dist=loadfile --max-worker-restart=1`), which cuts the full
suite from about 14 minutes serial (with coverage) to roughly 4-7 minutes. `loadfile` keeps each test file on one worker, so module-scoped
Qt fixtures keep working; do not rely on state shared between test files, because
files run in different processes and in no fixed order. Pass `-n 0` to run serially
(required for `--pdb` and IDE debuggers). `pytest-timeout` aborts any single test
(setup, call and teardown) that runs longer than 120s, so a hung Qt test cannot
consume the whole job: it dumps all stacks and kills the worker, which xdist
reports as `worker crashed while running <test>`. `--max-worker-restart=1` is one
replacement for the whole session, not per test: a second crash anywhere shuts down
the remaining workers and can leave tests unexecuted. Keep legitimate tests well under that limit. `--cov` works with xdist.

Every test runs with `HOME`/`USERPROFILE` redirected to its own empty directory
(the autouse `isolated_home` fixture in `tests/conftest.py`), so `build_app_context()`
and anything else that uses `~/.pandaplot` never touches the developer's real
config, log, or session files. Do not add per-test `monkeypatch.setenv("HOME", ...)`
workarounds, and never run code that saves config outside pytest without redirecting
the home directory first.

`tests/e2e/` exercises complete workflows through a real `PandaMainWindow`,
application services, menu clicks, dialogs, and background imports. Keep these
separate from isolated widget/controller tests in `tests/gui/`. Replace only
platform file pickers when a path must be supplied; do not mock commands,
project state, import workers, or the EventBus. Use `qtbot.waitUntil` for async
results rather than fixed sleeps.
Modal-dialog helpers must reject on failure so a failed assertion cannot hang
the test run. The Tests workflow runs the whole suite, including this GUI layer,
headlessly and in parallel, prints the 25 slowest tests, and uploads the JUnit
results even when a test fails.

## Code Quality
The repo has no `ruff format` step; `ruff check` (rules `E`, `F`, `B`, `Q`, `I`, `FBT`) is the only gate. Run it, plus the tests for the code you touched, before every push. Unsorted imports (`I001`), unused imports (`F401`) and missing `noqa` on Qt overrides are the most common avoidable review comments:

```bash
uv run ruff check .                     # Lint check
uv run ruff check --fix .               # Lint auto-fix
uv run ruff check --select I --fix .     # Auto-sort imports
uv run ty check                          # Type check
```

`ty` ([Astral](https://github.com/astral-sh/ty)) is still catching up with the existing codebase, so it currently reports pre-existing diagnostics unrelated to any given change -- focus on not introducing new ones in files you touch rather than clearing the full backlog.

## Icons
Icons are bundled Phosphor SVGs, never downloaded at runtime. To add or change one, add its Phosphor name to `icons` in `pandaplot/gui/resources/icons/icon_manifest.toml`, run `uv run python scripts/icons/build_icon_bundle.py`, and commit the regenerated `icon_bundle.json`, `licenses/` and `THIRD_PARTY_NOTICES.md` (`--check` fails when they are stale). Render icons on toolbars and buttons with `themed_icon(app_context, name)` or, for long-lived actions and buttons, an `ActionIcons` registry (`bind(target, name)` and `retint()` from `_apply_theme`) from `pandaplot/gui/resources/themed_icons.py`; both tint from design tokens (`build_icon` in `icon_library.py` is the low-level renderer). Decorative icons next to text (panel titles, headers) use `IconLabel` (`pandaplot/gui/components/common/icon_label.py`); a sidebar panel declares its icon with the `ICON_NAME` class attribute, which is used for both its title and its icon bar button. Item kinds (project tree, tabs, pickers) use `item_icon(app_context, item_type)` from `pandaplot/gui/resources/item_icons.py`, never an emoji prefix in a label: labels are plain names. Success, error, warning and info messages use `StatusMessage` (`pandaplot/gui/components/common/status_message.py`) next to the text area, not an emoji in the message text. Tests that mock the theme manager take their design tokens from `tests/gui/icon_testing.py` (`ICON_TOKENS`, `strongest_pixel`, `assert_tinted`). Rendered icons are cached (`icon_library.clear_icon_cache()` for tests that need a cold cache). Sidebar panels show messages with `SidebarPanel._show_status(kind, text)` / `_show_error(text)` (override `_status_output()` to return the text area): ERROR means the requested action or preview cannot run or failed (including validation), WARNING means it ran with a caveat. A destructive button's icon is red with a white hover icon: `ActionIcons.bind(button, name, role=IconRole.ERROR, hover_role=IconRole.ON_DANGER)` (Qt does not switch a QSS-styled button to `QIcon.Mode.Active` on hover). Menus (the main menu and every context menu) are plain text without icons. A single icon can come from another library through `[overrides]` in the manifest; the script then bundles that library's licence automatically.

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
- Return `NOOP` when nothing changed (renaming to the same name, converting to the same dtype, resizing to the current size) so no misleading history entry is created. Use `FAILURE` only for a real error, and `ABORTED` only from `undo()`/`redo()` when a precondition refused to make any change (a target element, layer or sketch no longer exists, or a rolled-back redo). `CommandExecutor` moves a `FAILURE` command to the opposite stack as if it had worked, so returning `FAILURE` for a missing target corrupts history.
- Every accepted `execute()` must be undoable: check up front that `undo()` can invert it, and reject before mutating. A swap that leaves X empty and then refuses its own undo, or a dtype change on a column labelled `None` that `undo()` rejects, put an un-undoable entry in history.
- Do not assign `self.dataset`, `self.project`, or other "executed" state until the mutation has actually succeeded; otherwise `undo()`/`redo()` act on a failed `execute()`. Guard with `is not None`, not truthiness (`0` and `""` are valid column labels).
- `redo()` must replay the original action, not blindly re-run `execute()`: do not mint new item IDs, re-open dialogs, re-snapshot "before" state, or build a new object. Later commands in the history reference the original IDs and objects.
- A command that retains a project item (`self.sketch`, `self.image`) must re-resolve the live item by ID in `undo()`/`redo()`: `DeleteItemCommand.undo()` rebuilds items from snapshots, so a retained reference points at a detached copy and the edit is silently lost. Snapshots must keep binary payloads (image bytes) and per-column metadata (stable column IDs, formula registry). Test delete, undo, then undo of an earlier edit, with byte and ID equality.
- Multi-step mutations must be transactional: if step N raises, restore steps 1..N-1 (including parent `modified_at` and ordering) and report failure. Never leave an orphaned or half-edited item. If a command cascades to dependents (charts, fits, error or confidence columns, formula columns), undo must restore all of them.
- Override `cleanup()` to drop large retained state (DataFrames, arrays, dialogs, cached projects). Override `occupies_undo_slot()` / `marks_project_modified()` for commands that are not real undoable edits (dialog openers, lifecycle commands, pure computation). Exceptions in `cleanup()` or in user-facing hooks must not break the executor.
- Background commands: capture the project (and `modification_revision`) at dispatch and validate it in the completion callback; never re-resolve `app_state.current_project` when the result arrives. Do not mutate command state or emit events from the worker thread; return data in the result payload and apply it on the main thread. Reset any "running" flag if dispatch itself raises, and before invoking user callbacks that may re-dispatch.
- Add tests for undo **and** redo of any new command or cascade, including the failure path.

### Events (`pandaplot/models/events/`)
- Payload keys must match what subscribers read (e.g. `PROJECT_ITEM_REMOVED` consumers need `item_id`). When you emit an event from a new code path, check every subscriber of that event and of its parents in `EventHierarchy`.
- UI that displays names, labels, or chart/dataset lists must refresh on **all** events that can change them (created, renamed, moved, removed, retyped, data changed), not only the one you tested. The same applies to caches of derived output (rendered chart snapshots, previews, live formula results): invalidate on create, delete, undo-restore, rename and move of every item they depend on, including items inside deleted or restored folders. Item lifecycle often arrives only as `PROJECT_ITEM_ADDED`/`PROJECT_ITEM_REMOVED` (with `item_type`, or a chart-specific key such as `chart_id`), not as the typed event.
- Undo/redo replay must emit the same events with the same payload keys as `execute()`. `EditBatchCommand.undo()` once emitted `DATASET_DATA_CHANGED` without `dataset_id`, which starved the note chart cache and live formula recompute. Handlers reached through `EventHierarchy` receive child payloads, so read keys defensively.
- Read `EventHierarchy.HIERARCHY_MAP` before adding a subscription: `CONFIG_RESET` already reaches `CONFIG_UPDATED` subscribers, so subscribing to both runs the handler twice. Opening or creating a project emits `PROJECT_LOADED`, not `PROJECT_CLOSED`, so per-project and per-tab caches must clear on both.
- Do not publish an expensive invalidation event on every keystroke (`dirtyOnly` fires while typing); emit it from committed model changes.
- When retiring an event, remove it from `EventHierarchy.HIERARCHY_MAP` and every subscriber. Emit from the main thread only. Iterate over snapshots when callbacks may subscribe or unsubscribe.
- Anything that is not a `WidgetExtension` but subscribes (table models, floating windows) must unsubscribe when destroyed.

### Models, persistence, and migrations
- `to_dict()`/`from_dict()` must round-trip every new field, and the result must be JSON-safe (NumPy/pandas nullable values, NaN, and tuples converted). Add a round-trip test **through the real storage path**: `ImageDataManager`, `DatasetDataManager` and `ProjectDataManager` build their own dicts, so a field can survive `to_dict()` and still be lost in a saved project file.
- New `ApplicationConfig` fields must be handled in `reset_defaults()`, `validate()` and `update_from_mapping()`, with a reset test (`max_undo_levels` was missing from `reset_defaults()`).
- Deserialization is resilient: unknown or invalid enum values, missing keys, and legacy keys fall back to defaults or are migrated (e.g. `show_grid` to `show_grid_x`/`show_grid_y`) instead of raising. Reject, rather than silently open, project files whose `schema_version` is newer than `CURRENT_SCHEMA_VERSION`. Persisted-format changes need a migration under `pandaplot/models/migrations/` plus a test; do not weaken migration assertions to subset checks. Bump `CURRENT_SCHEMA_VERSION` whenever an older build would silently drop or misread the new data (formula registry, live locks), so its forward-version check rejects the file.
- Check JSON types before dict lookups (`"type": []` as a discriminator raised `TypeError` and dropped a whole sketch), and treat optional data (cover images, thumbnails) as optional: a damaged ZIP entry is logged and skipped, never fatal for opening the project or listing the example.
- `Project.add_item()` does not enforce the parent's `accepts_item()` (`ImageGallery` accepts only images and albums): check it before attaching or moving, and make a move atomic so a failed validation leaves the item in its old collection.
- When replacing a render-time rule with stored state, port the old rule exactly in the migration, the new API's default and every caller (the old fit rule was "secondary if any matching series is on Y2", not "the first match"). When removing or replacing a public model or API, grep `examples/`, `docs/`, in-app help and tests for remaining uses.
- New column references must be handled by `DeleteColumnsCommand`, `RenameColumnCommand`, `Chart.retype_series()`, `snapshot_chart_state()`/`restore_chart_state()`, and copy/transform commands (carry over `y_axis`, style, and error/confidence columns consistently, or clear them deliberately).
- No mutable containers in frozen dataclasses (use `frozenset`/tuples). Validate invariants (e.g. style class vs `series_type`) in `__post_init__`. Prefer typed dataclasses and enums over string-keyed dicts and magic strings, and pass required values via the constructor instead of mutating afterwards.
- Names are not unique: projects allow duplicate item names. Use `pandaplot/utils/item_display_options.py` (`dataset_display_options`, `chart_display_options`, `disambiguated_display_options`) for any picker, and `get_chart_type_spec(chart_type).display_name`, never `value.capitalize()`, for chart-type labels.
- Never `eval()` user input without an AST allowlist; omitting `__builtins__` does not make `eval` safe. Expressions stored in project files are untrusted too: validate at the evaluation boundary, not only when the user creates them, and block dynamic dispatch that can write files (`x.agg("to_csv", ...)`, `to_string(buf=...)`, `getattr`). Add a regression test that asserts no file is created.

### GUI (`pandaplot/gui/`)
- Keep computation and business logic out of widgets. Put it in a service or analysis class (invoked from a command) and keep the widget to rendering and input.
- Async results are stale by the time they arrive. Capture a context token (chart, series, dataset and column ids, dispatch parameters) at dispatch, compare it on completion, and ignore mismatches. Restore button enabled-state from the *current* context, disable every action that would start a competing operation, and keep busy indicators running until the pending command actually completes. A tab that was closed and reopened, or a project that was reloaded, keeps the same IDs, so compare a lifecycle token as well. After a modal confirmation (delete, replace), re-check the document revision: offsets and rows captured before the dialog may be stale. Identify a series by its object or ID, never by list index or its dataset/X/Y columns, because duplicates are allowed and reordering shifts indices.
- Tools with an in-progress gesture (drag, resize, slider) must cancel or re-validate it when the model changes underneath (undo, a deleted layer): capture the target ID at gesture start, and apply the drag threshold before committing a click as an edit.
- Guard against empty or NaN data before `min()`/`max()`, division, or `median()`. Drop non-finite rows before building grids, coerce column data with `pd.to_numeric` before passing it to Matplotlib, and fail with a clear message instead of a chart-wide exception. Pick min/max points, labels and ranges only among drawable points (finite x and y, no `NaT`), and drop bad cells individually instead of rejecting the whole column. Use `pd.api.types.is_scalar` before `pd.isna` (tuple and array cells), and never treat the string `"nan"` as missing.
- Column labels can be `int` or `None`: keep the raw key in item data (`Qt.UserRole`) and display `str(name)`. Do not round-trip a key through combo text or rename-event payloads.
- `QTextCursor` positions are UTF-16 code units and Python string indices are code points: convert offsets before `setPosition`, and test with emoji in the text.
- Qt hygiene:
  - Parent `QAction`s to the menu that owns them so `QMenu.clear()` deletes them; enable menu tooltips explicitly if you set them.
  - Use `blockSignals` when setting several linked controls, then apply the change once. Do not connect a signal twice (`PButton(on_click=...)` already connects `clicked`).
  - Guard slots that may run during teardown with `shiboken6.isValid`. Do not swallow exceptions with a bare `except`/`pass`; log them.
  - Do not clear a whole stylesheet to remove one color; restore the themed stylesheet and clear stale error text and icons too. A widget-local `setStyleSheet` overrides the shared role rules and freezes its color across theme switches: use the shared roles, and re-tint an icon when its button changes role (for example promoted to primary).
  - A dialog or `QMessageBox` parented to the main window outlives `exec()`: call `deleteLater()` in a `finally`. When a nested modal closes, move Help or other windows to the surviving modal ancestor, not the main window.
  - Custom inputs: formatting, parsing and the validator must agree on locale syntax (non-Latin digits, grouped `1,234.5`), `setValue()` with an unchanged value is a no-op so typing does not reformat under the cursor, wheel handling accumulates `angleDelta` (120 per notch), and heights derive from the font (interface fonts go up to 36 pt).
  - Do not rely on private attributes of third-party widgets (e.g. the Matplotlib toolbar's `_actions`) without a guard.
  - Reuse existing base classes and helpers (`SidebarPanel._set_content`, `PButton`, `WidgetExtension`) instead of ad hoc containers.
- Error dialogs: call `show_error_message(title, "Couldn't X.", error=e)` (or `error=` a background result's `error_description`); never put exception text in `message`, and log the failure with `logger.exception` in the handler (`show_error_message` does not log).
- Raise `UserFacingError` (`pandaplot.utils.errors`) for messages written for the user, which dialogs show unchanged; keep plain `ValueError` for internal checks.
- Accessibility: every icon-only, custom-painted, or card-style (`QPushButton` with child labels) control needs `setAccessibleName`/`setAccessibleDescription` and must be keyboard-focusable and activatable. Use a native checkable control instead of a bare `QWidget` toggle, and expose busy/status indicators to assistive technology. Related traps: `QToolBar.addAction()` buttons are `NoFocus` by default; `addWidget()` controls in a `QToolBar` outside a `QMainWindow` never reach the overflow menu; single-letter tab-wide shortcuts must not fire while a text field or combo has focus; a `PButton` in a `QDialog` is an auto-default button, so call `setAutoDefault(False)` unless Enter should trigger it; icons and focus rings need 3:1 contrast against their real background in every theme and state (checked toggles included), verified against the actual theme palette.
- Add new constructor, function or dataclass-field parameters as keyword-only and **after** existing ones so positional callers do not break. This includes fields of dataclass mixins and spec classes: use `field(default=..., kw_only=True)`, because a field inserted earlier silently changes what `LineSeriesStyle(True)` or `ChartTypeSpec(..., True)` means.
- Units and wording must be consistent (do not mix cm and inches), and a setting shown in a dialog must actually be persisted and applied.

### Chart rendering (`gui/components/tabs/chart/`)
- Series renderers draw on the series' own target axes (primary or secondary), and honor `alpha`, visibility, series order (`zorder`), and the series or marker color. Value labels, error bars, histograms, and fits follow the same rules as the main artist. Apply `alpha` to every artist a renderer creates (fit bands, whiskers, caps, fliers, fills). A hidden series is drawn faded (effective alpha 0.3), not skipped.
- Anything a renderer plots differently from the raw columns (KDE curve, histogram bin edges, box positions, categorical text X, numeric strings in heatmaps, a fill baseline at 0) must be mirrored in `compute_axis_data_range()`, or switching an axis to Manual clips the data. Share one numeric-normalization helper between the renderer and the range code so a stray text cell cannot fail one and not the other.
- A capability flag on `ChartTypeSpec`/`SeriesTypeSpec` (`allows_fit`, `is_3d`, primary-axis-only) needs a runtime consumer at every entry point: the Fit panel source combo, data-tab actions such as Convert to Fit, the type picker, `Chart.set_chart_type()`/`retype_series()` (normalize `y_axis`, reject or convert fits), and wizard previews, which must use the same palette and styles as the chart they create.
- Reset Matplotlib state you changed (locators, formatters, GridSpec, secondary axes, mathtext parsing) when a setting returns to auto/default, because `update_chart()` reuses axes.
- Interactions (hover, pick) must respect toolbar pan/zoom mode, flush the final throttled event, and work for legends placed outside the axes.

### Tests (`tests/`)
- Mirror production shapes in mocks (`FitResult.params` is a dict; commands return `CommandResult`). A fake that differs from production hides the bug the test claims to cover. Fakes for schedulers and executors must clean up on every path (success, error, cancel, callback raising), like production.
- Every bug fix gets a regression test that fails without the fix. Assert semantics (full `Series`/dtype equality, parameters actually forwarded, call counts), not a marker such as `dtype == "category"`.
- Bound anything that can hang: finite deadlines in worker stubs, `timeout=` on subprocesses, and `QT_QPA_PLATFORM=offscreen` for subprocess Qt tests. Put fixture teardown in `try/finally`.
- Do not weaken an existing assertion to make a test pass; add an explicit exclusion instead.
- Never make a test pass by assigning attributes the model does not have (a `dataset.df` that is really `Dataset.data`, a `source_dataset_id` that is really `dataset_id`): build real objects, and let the test fail if the production attribute is wrong.
- Assert *which* items, not only how many (`len(axes.texts) == 2` also passes for the wrong two points). Drive input the way a user does: type or paste instead of `setText()` (it bypasses validators), and emit through the real EventBus, including the undo/redo replay events.
- Restore global state: use `caplog.set_level` or `monkeypatch`, never set a shared logger's level directly.

### Analysis and fitting (`pandaplot/analysis/`, `services/fit/`)
- Initial guesses must be translation- and scale-invariant: test with offset X (1000..1005) and tiny or huge rates, and fall back to zero damping rather than a seed that overflows (`exp(1000)`).
- Validate fixed parameters against the model's bounds just like free ones, rebuild the full parameter vector for variadic models (polynomials) before evaluating, and convert inputs with `np.asarray(..., dtype=float)` before `np.isfinite`.
- Keep the full canonical model name and derive colors and labels without substring matching on a short name (`Exponential` Decay/Growth collided). Error-message hints must be true: do not suggest a setting that does not exist.

### Code hygiene
- No commented-out code, `print()` or debug logging, `TODO` comments that express uncertainty, or references to gitignored or local-only files (link an issue number instead). No duplicate imports; keep stdlib / third-party / local order (`ruff check --select I --fix .`).
- Prefer a dict or enum over long `if/elif` chains on strings, and extract lists or constants used in more than one place.
- Docstrings and comments must describe what the code does *now*. Stale docstrings and type annotations after a refactor are a frequent finding. The same holds for `docs/` and in-app help content, including text generated from spec flags (`supports_error_bars` describes the default series, not overlays; Pie legend entries come from the labels column).
- Do not land model fields, modes or enum values that nothing in production can set (they become dead code and latent bugs); add them together with the UI that sets them.
- `ruff check` does not select the `W` rules, so trailing whitespace and a missing end-of-file newline pass CI and still draw review comments. Run `uv run ruff check --select W291,W292,W293 --fix <files you changed>` on your own files only (other files already have `W` warnings).
- `pandaplot_storybook/` has its own `pyproject.toml` and ruff config in which `pandaplot` counts as third-party, so its import order differs from the main package. Do not "fix" it.
- Release builds are compiled with Nuitka: use explicit imports, not `importlib` with computed module names, or add the package to the Nuitka config.
- CI workflows (`.github/workflows/`): never interpolate `${{ inputs.* }}` or `github.event.*` into shell source; pass them via `env:` and quote the variable. Use forward slashes in paths that run on Linux/macOS (e.g. `pysidedeploy.spec`), archive directories (such as macOS `.app` bundles) before uploading artifacts so permissions survive, and revert files that tools rewrite locally before committing.

## Pull Requests
- The PR description must match what the PR actually does. Update it when scope changes during review (features added, removed, or deferred; test counts; behavior such as inclusive vs. exclusive ranges), and it must not promise APIs that were not added or cite blockers that are already closed. Reviewers flag every mismatch.
- Use `Closes #N` only when the PR fully satisfies the issue; use `Refs #N` for a partial step.
- A user-facing change adds one entry under the matching `### Added`/`### Changed`/`### Fixed` heading below `## [Unreleased]` in `CHANGELOG.md`. Not directly under `[Unreleased]`, and not twice: the release workflow copies the whole section into the release notes.
- Keep a PR to one concern, and call out known gaps and pre-existing issues explicitly instead of leaving them for a reviewer to find. File each follow-up or known gap as a GitHub issue and link it from the PR.
- Fix valid review comments with a regression test; if you disagree, reply with the reasoning. When a comment names a bug class, audit sibling code for the same defect (all `Command` subclasses, all subscribers of an event) in the same PR.
- Before pushing: `uv run ruff check .` and `QT_QPA_PLATFORM=offscreen uv run pytest <touched test dirs>`.
