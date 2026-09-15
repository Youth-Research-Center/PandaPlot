# Overview and Data Flow

## Application Startup

```
app.py::main()
  └── create_project_data_manager()   # Build storage layer
  └── build_app_context()             # Wire all services into AppContext
        ├── EventBus
        ├── AppState
        ├── CommandExecutor
        ├── ConfigManager  (loads ~/.pandaplot/config.json)
        ├── ThemeManager
        ├── TaskScheduler
        ├── FitService
        ├── UIController
        └── ProjectDataManager
  └── create_qt_application()         # Create PandaMainWindow
  └── launch()                        # Start Qt event loop
```

## Primary Data Flow: Import CSV and Create Chart

```
1. USER ACTION
   MainMenu → File → Import CSV
   └── UIController.show_import_csv_dialog() → file path

2. COMMAND EXECUTION
   ImportCsvCommand(app_context, filepath).execute()
   ├── pandas.read_csv(filepath) → DataFrame
   ├── Dataset item created wrapping DataFrame
   ├── project.add_item(dataset)
   ├── ProjectDataManager auto-saves to .pplot ZIP
   └── EventBus.emit(DatasetEvents.DATASET_CREATED, {...})

3. EVENT PROPAGATION (hierarchical)
   dataset.created
     └── project.item_added
           └── project.changed
   All registered subscribers are called in order.

4. GUI REACTION
   ProjectTreeManager  ← receives project.item_added → updates tree view
   TabContainer        ← receives dataset.created   → opens DatasetTab

5. CHART CREATION
   CreateChartFromWizardCommand(dataset_id, preselected_column_ids).execute()
   ├── ChartWizard shown non-blocking (show(), not exec()); execute() returns True
   └── on ChartWizard.finished(Accepted) → _on_wizard_finished()
       ├── ChartWizard collects the chart type and one DataSeries per configured card
       ├── Chart item created with DataSeries referencing dataset columns
       ├── project.add_item(chart)
       └── EventBus.emit(ChartEvents.CHART_CREATED, {...})

6. CHART RENDERING
   ChartTab receives chart.created
   └── ChartRenderEngine builds matplotlib Figure from Chart model
       └── Renders to embedded Qt canvas (FigureCanvasQTAgg)
```

## Analysis Operation Flow (Asynchronous)

```
User selects analysis type (Derivative / Integral / Smoothing / Interpolation)
└── AnalysisCommand.execute()
    ├── UI panel displays BusySpinner
    ├── TaskScheduler.run_task(AnalysisEngine.calculate_*, params) on QThreadPool
    ├── On task completion:
    │   ├── Result appended as new column to Dataset
    │   ├── ApplyAnalysisResultCommand created and pushed to undo stack
    │   └── EventBus.emit(AnalysisEvents.ANALYSIS_COMPLETED + DatasetEvents.DATASET_COLUMN_ADDED)
    └── UI panel hides BusySpinner
```

## Curve Fitting Flow

```
User selects data series and fit type (Linear / Quadratic / Exponential / Power / Custom)
└── ApplyFitCommand.execute()
    ├── FitService.perform_fit(chart, series, fit_config)
    │   ├── Extract x, y arrays from Dataset columns
    │   └── scipy.optimize.curve_fit() → parameters, errors, R²
    ├── FitData object attached to Chart
    └── ChartTab re-renders with fit curve overlaid
```

## Project Save/Load

```
SAVE
SaveProjectCommand.execute()
└── ProjectDataManager.save(project, filepath)
    ├── Create / overwrite .pplot ZIP file
    ├── Write project.json  (item hierarchy metadata)
    └── For each item:
        ├── Chart   → chart_{id}.json
        ├── Dataset → dataset_{id}.parquet (or HDF5)
        ├── Note    → note_{id}.json
        └── Folder  → folder_{id}.json

LOAD
OpenProjectCommand.execute()
└── ProjectDataManager.load(filepath)
    ├── Read project.json → item hierarchy
    └── Reconstruct each item via ItemDataManagerFactory
└── AppState.load_project(project)
└── EventBus.emit(ProjectEvents.PROJECT_LOADED)
```

## Undo / Redo

```
Every command execution:
  CommandExecutor.execute_command(cmd)
  ├── cmd.execute()
  └── undo_stack.append(cmd)   # max 10 entries

Ctrl+Z:
  CommandExecutor.undo()
  ├── cmd = undo_stack.pop()
  ├── cmd.undo()               # Reverses state change + emits events
  └── redo_stack.append(cmd)

Ctrl+Y:
  CommandExecutor.redo()
  ├── cmd = redo_stack.pop()
  ├── cmd.redo()               # Re-applies change + emits events
  └── undo_stack.append(cmd)
```
