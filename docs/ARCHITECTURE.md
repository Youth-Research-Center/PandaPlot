# PandaPlot Architecture

PandaPlot is a Python-based desktop application for scientific data visualization and analysis. It provides an interactive GUI for managing hierarchical projects that contain datasets, charts, and notes, with support for mathematical analysis and curve fitting.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| GUI | PySide6 (Qt6) |
| Data processing | pandas, numpy |
| Visualization | matplotlib |
| Scientific computing | scipy, statsmodels |
| Persistence | ZIP-based `.pplot` files (JSON + Parquet) |
| Build system | uv (Python 3.12+) |

## Top-Level Package Structure

```
pandaplot/
├── app.py              # Entry point - wires all components together
├── models/             # Data models and event/state infrastructure
├── commands/           # Command pattern (~50 commands, undo/redo)
├── analysis/           # Analysis algorithms (scipy-based): fitting,
│                       # descriptive stats, preprocessing, signal processing
├── services/           # Config, theme, task scheduling, curve fitting,
│                       # data import, data managers, note rendering/search,
│                       # autosave, transform, session management
├── storage/            # ZIP-based project persistence
├── utils/              # Shared helpers (logging, pandas utilities, examples)
└── gui/                # PySide6 UI components and controllers

pandaplot_storybook/    # Standalone sub-project: PySide6 component storybook
                        # with light/dark theme switching, for previewing
                        # shared widgets (e.g. PButton) in isolation
```

## Architectural Layers

```
┌─────────────────────────────────────────────────────────┐
│                        GUI Layer                         │
│   MainWindow │ TabContainer │ Sidebar │ UIController     │
├─────────────────────────────────────────────────────────┤
│                     Command Layer                        │
│   CommandExecutor │ 50+ Command classes │ Undo/Redo      │
├─────────────────────────────────────────────────────────┤
│                     Service Layer                        │
│ ConfigManager │ ThemeManager │ TaskScheduler │ FitSvc    │
│ DataImport │ DataManagers │ NoteRender │ NoteSearch │    │
│ AutosaveService │ SessionManager │ TransformEngine │...  │
├───────────────────────────┬─────────────────────────────┤
│        Models             │       Storage               │
│  Project │ Items │ Events │  ProjectDataManager + ZIPs  │
├───────────────────────────┴─────────────────────────────┤
│                     Analysis Layer                       │
│  AnalysisEngine │ DescriptiveEngine │ PreprocessingEngine│
│  │ StatsEngine │ SignalEngine (derivative, integral,     │
│  smooth, interp, stats, signal processing)               │
└─────────────────────────────────────────────────────────┘
```

## Core Communication Patterns

**GUI → Backend:** User actions create and execute Command objects via `CommandExecutor`. Long-running computations are dispatched asynchronously to background threads via `TaskScheduler`.

**Backend → GUI:** State changes emit events on the `EventBus`. GUI components subscribe and react.

**Dependency Injection:** All services are registered in and accessed through the central `AppContext` container passed to commands, views, and controllers.

## Key Design Patterns

| Pattern | Where Used |
|---------|-----------|
| Command | Every user action; enables undo/redo |
| Pub/Sub (EventBus) | Decoupled state-change notifications |
| MVC | Models (items), Views (tabs/panels), Commands (controllers) |
| Facade | `AppContext` (services), `UIController` (dialogs) |
| Template Method | `WidgetExtension` lifecycle (`_init_ui` → `_apply_theme`) |
| Strategy | `AnalysisEngine` (runtime algorithm selection) |
| Factory | `ItemDataManagerFactory` (per-type serializers) |
| Visitor | `models/project/visitors/` (traversal over project item trees) |

## Detailed Architecture Documents

- [Overview and Data Flow](arch/01-overview.md)
- [Project Model and Items](arch/02-project-model.md)
- [Command System and Undo/Redo](arch/03-command-system.md)
- [Event System](arch/04-event-system.md)
- [GUI Layer](arch/05-gui-layer.md)
- [Data Persistence](arch/06-data-persistence.md)
- [Analysis and Curve Fitting](arch/07-analysis-engine.md)
- [State Management and AppContext](arch/08-state-management.md)
- [Architectural Issues](arch/09-architectural-issues.md)

## High-Level Flow Diagram

See [high-level-flow.drawio](arch/high-level-flow.drawio) for a visual overview of data flow between layers.
