# Command System and Undo/Redo

## Overview

Every user action is implemented as a Command object. This provides:
- Uniform execution interface
- Undo/redo without ad-hoc rollback logic
- Testability independent of the GUI

## Base Command (`commands/base_command.py`)

```python
class Command(ABC):
    def __init__(self, app_context: AppContext): ...
    
    @abstractmethod
    def execute(self) -> bool: ...   # Apply the change; return True on success
    
    def undo(self): ...              # Reverse the change
    def redo(self): ...              # Re-apply (default: calls execute())
    
    @property
    def description(self) -> str: ...  # Human-readable label for UI
```

## CommandExecutor (`commands/command_executor.py`)

```
CommandExecutor
├── undo_stack: deque[Command]    # Max 10 entries
├── redo_stack: deque[Command]
├── execute_command(cmd)
│   ├── cmd.execute()
│   ├── undo_stack.append(cmd)
│   └── redo_stack.clear()
├── undo()
│   ├── cmd = undo_stack.pop()
│   ├── cmd.undo()
│   └── redo_stack.append(cmd)
├── redo()
│   ├── cmd = redo_stack.pop()
│   ├── cmd.redo()
│   └── undo_stack.append(cmd)
├── can_undo() → bool
└── can_redo() → bool
```

Every `execute()`, `undo()`, and `redo()` is expected to emit the appropriate `EventBus` events so the GUI stays in sync automatically.

## Command Categories

### Project Commands (`commands/project/project/`)

| Command | Description |
|---------|-------------|
| `CreateProjectCommand` | Initializes a new empty project |
| `NewProjectCommand` | Creates and opens a new project |
| `OpenProjectCommand` | Opens an existing `.pplot` file |
| `LoadProjectCommand` | Loads project data from disk into AppState |
| `SaveProjectCommand` | Persists current project to disk |

### Dataset Commands (`commands/project/dataset/`)

| Command | Description |
|---------|-------------|
| `ImportCsvCommand` | Reads CSV via pandas, creates Dataset |
| `ExportDatasetCommand` | Writes Dataset to CSV/Excel |
| `CreateEmptyDatasetCommand` | Creates a blank Dataset |
| `AddColumnsCommand` | Appends column(s) to DataFrame |
| `DeleteColumnsCommand` | Removes column(s) from DataFrame |
| `ChangeColumnDtypeCommand` | Casts column to a different dtype |
| `AddRowsCommand` | Appends row(s) to DataFrame |
| `DeleteRowsCommand` | Removes row(s) by index |
| `EditCommand` | Sets a single cell value |
| `EditBatchCommand` | Sets multiple cell values atomically |
| `TransformColumnCommand` | Evaluates a formula over a column |
| `AnalysisCommand` | Runs an analysis operation, stores result as new column |

### Chart Commands (`commands/project/chart/`)

| Command | Description |
|---------|-------------|
| `CreateChartFromWizardCommand` | Opens `ChartWizard` non-blocking; creates the Chart item asynchronously on the wizard's `finished(Accepted)` signal |
| `AddSeriesCommand` | Adds a DataSeries to a Chart |
| `RemoveSeriesCommand` | Removes a DataSeries from a Chart |
| `ApplyChartPropertiesCommand` | Updates ChartConfiguration (title, labels, grid…) |

### Fit Commands

| Command | Description |
|---------|-------------|
| `ApplyFitCommand` (`commands/project/chart/`) | Runs curve fit, adds a `SeriesType.FIT` DataSeries to Chart.data_series |
| `ConvertSeriesToFitCommand` (`commands/project/chart/`) | Converts an existing DataSeries into a manually-editable `SeriesType.FIT` entry, at the same position |
| `PerformFitCommand` (`commands/project/fit/`) | Computes a fit preview for `FitPanel` on a background thread; runs through `CommandExecutor` as a non-undoable `BackgroundTaskCommand` (FitPanel's Apply uses `ApplyFitCommand`) |

A fit is removed the same way as any other series, via `RemoveSeriesCommand` -- there is no separate fit-removal command.

### Item / Folder Commands

| Command | Description |
|---------|-------------|
| `DeleteItemCommand` | Removes any item from the project |
| `RenameItemCommand` | Updates item name |
| `CreateFolderCommand` | Creates a new Folder item |

### App Commands (`commands/app/`)

| Command | Description |
|---------|-------------|
| `ExitCommand` | Prompts save-on-exit then quits |

## Example: ImportCsvCommand

```python
class ImportCsvCommand(Command):
    def __init__(self, app_context, filepath):
        super().__init__(app_context)
        self.filepath = filepath
        self.dataset_id = None

    def execute(self) -> bool:
        df = pd.read_csv(self.filepath)
        dataset = Dataset(name=Path(self.filepath).stem, dataframe=df)
        self.dataset_id = dataset.id
        self.app_state.current_project.add_item(dataset)
        self.event_bus.emit(DatasetEvents.DATASET_CREATED, {"dataset_id": dataset.id})
        return True

    def undo(self):
        self.app_state.current_project.remove_item(self.dataset_id)
        self.event_bus.emit(DatasetEvents.DATASET_DELETED, {"dataset_id": self.dataset_id})
```
