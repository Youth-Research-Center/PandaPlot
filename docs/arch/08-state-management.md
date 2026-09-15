# State Management and AppContext

## AppContext (`models/state/app_context.py`)

`AppContext` is the central dependency injection container. It is created once at startup and passed to every command, service, and GUI component that needs access to application services.

```
AppContext
├── app_state: AppState
├── event_bus: EventBus
├── command_executor: CommandExecutor
├── config_manager: ConfigManager
├── theme_manager: ThemeManager
├── task_scheduler: TaskScheduler
├── fit_service: FitService
├── ui_controller: UIController
├── project_data_manager: ProjectDataManager
├── autosave_service: AutosaveService
├── session_manager: SessionManager
├── transform_engine: TransformEngine
├── note_render_service: NoteRenderService
└── note_search_service: NoteSearchService
```

### Type-Safe Manager Retrieval

```python
config = app_context.get_manager(ConfigManager)
theme  = app_context.get_manager(ThemeManager)
```

`get_manager(T)` raises `KeyError` if `T` is not registered, preventing silent `None` errors.

## AppState (`models/state/app_state.py`)

Holds the single runtime state that changes throughout a session: the currently open project.

```
AppState
├── current_project: Project | None
├── load_project(project)
│   ├── self.current_project = project
│   └── EventBus.emit(ProjectEvents.PROJECT_LOADED, {...})
└── close_project()
    ├── self.current_project = None
    └── EventBus.emit(ProjectEvents.PROJECT_CLOSED, {...})
```

## Service Layer Overview

- **AutosaveService (`services/autosave/`)**: Listens to project and dataset modification events on `EventBus`. When auto-save is enabled in `ConfigManager`, triggers debounced asynchronous project saves.
- **SessionManager (`services/session/`)**: Saves and restores application session state (open tabs, window geometry, last active item) across application launches.
- **TransformEngine (`services/transform/`)**: Safely evaluates mathematical expressions over pandas DataFrame columns using `pandas.eval`.
- **NoteRenderService & NoteSearchService (`services/note_render/`, `services/note_search/`)**: Converts Markdown notes to HTML/LaTeX and provides full-text search across project notes.
- **ExcelImportService (`services/data_import/`)**: Parses single and multi-sheet Excel workbooks into project Datasets with sheet previews.

## Full State Tree

```
AppContext
└── AppState
    └── current_project: Project | None
        └── root: ItemCollection
            ├── Dataset  → dataframe: pd.DataFrame
            ├── Chart    → series: list[DataSeries]
            │              fit_data: list[FitData]
            ├── Note     → content: str
            └── Folder   → items: list[Item]

AppContext
├── CommandExecutor
│   ├── undo_stack: deque[Command]   (max 10)
│   └── redo_stack: deque[Command]
├── ConfigManager
│   └── config: ApplicationConfig   (persisted to ~/.pandaplot/config.json)
└── ThemeManager
    └── current_theme: ThemeMode    (LIGHT | DARK)
```

## State Change Flow

All state changes flow through Commands and are announced via Events:

```
GUI Action
  → Command.execute()
      → Mutate AppState / Project
      → EventBus.emit(event, data)
          → GUI subscribers react (update views)
          → Service subscribers react (e.g. auto-save)
```

There is no two-way data binding. The GUI never mutates state directly.

## Initialization Sequence (`app.py`)

```python
def build_app_context() -> AppContext:
    event_bus        = EventBus()
    app_state        = AppState(event_bus)
    command_executor = CommandExecutor(event_bus)
    config_manager   = ConfigManager(event_bus)
    theme_manager    = ThemeManager(event_bus, config_manager)
    task_scheduler   = TaskScheduler()
    fit_service      = FitService()
    data_manager     = create_project_data_manager()
    ui_controller    = UIController()

    ctx = AppContext()
    ctx.register(AppState,            app_state)
    ctx.register(EventBus,            event_bus)
    ctx.register(CommandExecutor,     command_executor)
    ctx.register(ConfigManager,       config_manager)
    ctx.register(ThemeManager,        theme_manager)
    ctx.register(TaskScheduler,       task_scheduler)
    ctx.register(FitService,          fit_service)
    ctx.register(ProjectDataManager,  data_manager)
    ctx.register(UIController,        ui_controller)

    config_manager.load()   # Triggers ConfigEvents.CONFIG_LOADED
    return ctx
```

## Configuration State (`services/config/`)

`ApplicationConfig` persisted to `~/.pandaplot/config.json`:

| Field | Type | Default |
|-------|------|---------|
| `theme` | `str` | `"light"` |
| `window_geometry` | `dict` | `{}` |
| `recent_projects` | `list[str]` | `[]` |
| `auto_save` | `bool` | `False` |

On update, `ConfigManager` writes the JSON file and emits `ConfigEvents.CONFIG_UPDATED`. Services like `ThemeManager` subscribe and react immediately.
