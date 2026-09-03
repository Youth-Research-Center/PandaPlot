# Architectural Issues

This document records real problems found in the codebase, with file references and concrete evidence.

---

## HIGH: Commands import from the GUI layer (20 files)

**Every command file imports `UIController` directly from `pandaplot.gui`.**

```
pandaplot/commands/project/dataset/edit_command.py:4
pandaplot/commands/project/dataset/import_csv_command.py:8
pandaplot/commands/project/chart/create_chart_command.py:8
... (17 more files)
```

Commands are supposed to be pure business logic. Importing from `pandaplot.gui` means:

- Commands cannot be executed without a running Qt application — they are untestable in isolation.
- Any refactor of `UIController` requires touching all 20 command files.
- The intended architecture (GUI → Commands → Models) is actually (GUI ↔ Commands ↔ GUI).

The `UIController` is used inside commands to show error dialogs. The correct fix is to propagate errors via return values or exceptions and let the GUI layer decide how to display them.

---

## HIGH: `CommandExecutor` ignores the return value of `execute()`

**File:** [commands/command_executor.py:35-38](../../pandaplot/commands/command_executor.py)

```python
command.execute()          # Returns bool — True = success, False = failure
self.undo_stack.append(command)   # Always appended, even when execute() returned False
```

When a command returns `False` (e.g., dataset not found, validation failed), the command is still pushed to the undo stack. Pressing Ctrl+Z will then attempt to undo an operation that never actually happened, corrupting state.

---

## HIGH: `undo()` and `redo()` pop the command before calling it

**File:** [commands/command_executor.py:74-76](../../pandaplot/commands/command_executor.py), [102-104](../../pandaplot/commands/command_executor.py)

```python
command = self.undo_stack.pop()   # Command removed from stack BEFORE undo runs
command.undo()                     # If this raises, command is gone — stack is corrupted
self.redo_stack.append(command)
```

If `command.undo()` raises an exception, the command has already been removed from `undo_stack` but is never added to `redo_stack`. The undo history is now in an undefined state with no recovery path. The same pattern exists in `redo()`.

---

## MEDIUM: `EditCommand.undo()` has no error handling and assumes `self.dataset` is set

**File:** [commands/project/dataset/edit_command.py:76-82](../../pandaplot/commands/project/dataset/edit_command.py)

```python
def undo(self):
    self.dataset.data.iloc[self.index[0], self.index[1]] = self.old_value  # No guard
    self.app_context.event_bus.emit(...)
```

`self.dataset` is assigned inside `execute()`. If undo is somehow called before execute (e.g. after deserialization, or due to executor bug #2 above), this raises `AttributeError`. Compare to `execute()` which has full `try/except` and validation. The inconsistency is present in multiple commands (`edit_batch_command.py`, `change_column_dtype_command.py`).

---

## MEDIUM: `PerformFitCommand` is not a Command and has no logic

**File:** [commands/project/fit/perform_fit_command.py](../../pandaplot/commands/project/fit/perform_fit_command.py)

```python
class PerformFitCommand:          # Does NOT extend Command
    def __init__(self, fit_panel):
        self.fit_panel = fit_panel
    #TODO: add undo and redo logic
```

The class is 9 lines, has no `execute()`, `undo()`, or `redo()`, and stores a reference to a GUI panel (`fit_panel`) — a GUI object inside a command. It is not wired into `CommandExecutor` anywhere in the codebase. Fit operations therefore have no undo support at all, despite the `ApplyFitCommand` / `RemoveFitCommand` being documented in the architecture.

---

## RESOLVED: Analysis operations blocked the Qt main thread

**Files:** [commands/project/dataset/analysis_command.py](../../pandaplot/commands/project/dataset/analysis_command.py), [commands/project/dataset/signal_analysis_command.py](../../pandaplot/commands/project/dataset/signal_analysis_command.py), [commands/project/fit/perform_fit_command.py](../../pandaplot/commands/project/fit/perform_fit_command.py)

`AnalysisCommand`, `SignalAnalysisCommand`, and `PerformFitCommand` used to call `AnalysisEngine`/`SignalEngine`/`FitService` synchronously inside `execute()`, freezing the UI on large datasets (#283).

Each now validates inputs synchronously, then dispatches the actual computation to `TaskScheduler.run_task()`. `AnalysisCommand` and `SignalAnalysisCommand` (which mutate project state) split into a dispatcher (`occupies_undo_slot() -> False`) and a separate `Apply*ResultCommand`, constructed and pushed onto the undo stack only once the background result is back — the same pattern `CreateChartFromWizardCommand` established for #185/#186. `PerformFitCommand` computes a preview only, so it needed no such split. All three panels (`AnalysisPanel`, `SignalPanel`, `FitPanel`) show a `BusySpinner` while their dispatched task runs.

---

## RESOLVED: `CreateChartCommand` queried the same dataset twice and had a dead TODO

**File:** [commands/project/chart/create_chart_from_wizard_command.py](../../pandaplot/commands/project/chart/create_chart_from_wizard_command.py)

`CreateChartCommand` used to look the dataset up twice (the second lookup guarded by a `# TODO: remove this`) and construct a chart with hardcoded default series from the first two columns with no user input, bypassing the intended series-configuration workflow.

It has been replaced by `CreateChartFromWizardCommand`, which opens `ChartWizard` and builds the chart type and each `DataSeries` from what the user actually configured. The duplicate lookup and the dead TODO are gone.

---

## LOW: Inconsistent `set_data()` usage when mutating DataFrames

Some commands update the DataFrame through the `Dataset.set_data()` method (which updates `updated_at` and can trigger hooks), while others mutate `dataset.data` directly:

```python
# analysis_command.py — uses set_data()
self.dataset.set_data(df_copy)

# change_column_dtype_command.py line 111 — direct mutation
self.dataset.data[self.column_name] = conversion_result["converted_data"]

# edit_command.py line 63 — direct mutation
self.dataset.data.iloc[self.index[0], self.index[1]] = self.new_value
```

Direct mutations bypass any metadata updates (`updated_at`, validation) that `set_data()` might perform, and make it harder to add future side-effects to data changes.

---

## LOW: Undo stack eviction does not clean command references

**File:** [commands/command_executor.py:39-42](../../pandaplot/commands/command_executor.py)

```python
if len(self.undo_stack) > self.max_undo_levels:
    #TODO: ensure we clean command references properly
    removed_command = self.undo_stack.pop(0)
```

Commands store snapshots of data for undo (e.g., full DataFrame copies in `ImportCsvCommand`, `AnalysisCommand`). When a command is evicted from the undo stack the variable `removed_command` is assigned and immediately goes out of scope, so CPython will collect it — but this is not guaranteed and no explicit cleanup (`del`, `None`-ing) is done. The TODO acknowledges this is unresolved.

---

## Summary Table

| # | Issue | Severity | Files |
|---|-------|----------|-------|
| 1 | Commands import `UIController` from GUI layer | **HIGH** | 20 command files |
| 2 | `execute()` return value ignored — failed commands enter undo stack | **HIGH** | `command_executor.py:35` |
| 3 | Command popped before `undo()`/`redo()` runs — stack corrupted on exception | **HIGH** | `command_executor.py:74,102` |
| 4 | `EditCommand.undo()` no error handling, assumes `self.dataset` set | **MEDIUM** | `edit_command.py`, `edit_batch_command.py`, `change_column_dtype_command.py` |
| 5 | `PerformFitCommand` is not a Command, no logic, no undo | **MEDIUM** | `perform_fit_command.py` |
| 6 | ~~Analysis operations blocked Qt main thread~~ (resolved: dispatched to TaskScheduler with BusySpinner UI) | **RESOLVED** | `analysis_command.py`, `signal_analysis_command.py`, `perform_fit_command.py` |
| 7 | ~~`CreateChartCommand` double dataset lookup + TODO dead code~~ (resolved: replaced by `CreateChartFromWizardCommand`) | **RESOLVED** | `create_chart_from_wizard_command.py` |
| 8 | Inconsistent `set_data()` vs direct DataFrame mutation | **LOW** | `edit_command.py`, `change_column_dtype_command.py` |
| 9 | Undo stack eviction leaves command data in memory | **LOW** | `command_executor.py:39` |
