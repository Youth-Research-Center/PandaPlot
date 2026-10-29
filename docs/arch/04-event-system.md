# Event System

## EventBus (`models/events/event_bus.py`)

The `EventBus` provides decoupled publish/subscribe communication between the backend (commands, services) and the GUI. Components never hold direct references to each other; they communicate exclusively through events.

```
EventBus
├── subscribe(event_type, callback)          # Exact-match subscription
├── subscribe_pattern(pattern, callback)     # Wildcard subscription (e.g. "dataset.*")
├── unsubscribe(event_type, callback)
├── emit(event_type, data: dict)
│   ├── Notify all exact-match subscribers
│   ├── Notify all pattern subscribers that match
│   └── Walk EventHierarchy to emit parent events
└── clear()                                  # Used in tests / project close
```

### Hierarchical Emission

When a specific event is emitted, parent events in the hierarchy are also emitted automatically. This lets coarse-grained subscribers react to broad categories without knowing every sub-event.

```
dataset.column_added
  → dataset.structure_changed
      → dataset.changed
          → project.changed
```

The hierarchy is defined in `EventHierarchy.HIERARCHY_MAP` inside `event_types.py`.

## Event Categories (`models/events/event_types.py`)

| Category | Example Events |
|----------|---------------|
| `AppEvents` | `app.started`, `app.closing` |
| `ConfigEvents` | `config.loaded`, `config.updated`, `config.saved`, `config.reset` |
| `ThemeEvents` | `theme.changed` |
| `ProjectEvents` | `project.created`, `project.loaded`, `project.saved`, `project.closed`, `project.changed`, `project.item_added`, `project.item_removed`, `project.item_renamed` |
| `DatasetEvents` | `dataset.created`, `dataset.deleted`, `dataset.changed` |
| `DatasetOperationEvents` | `dataset.column_added`, `dataset.column_deleted`, `dataset.column_dtype_changed`, `dataset.row_added`, `dataset.row_deleted`, `dataset.cell_edited`, `dataset.structure_changed` |
| `ChartEvents` | `chart.created`, `chart.deleted`, `chart.series_added`, `chart.series_removed`, `chart.properties_changed` |
| `AnalysisEvents` | `analysis.completed`, `analysis.failed` |
| `FitEvents` | `fit.applied`, `fit.removed` |
| `NoteEvents` | `note.created`, `note.content_changed` |
| `SketchEvents` | `sketch.changed` (payload `sketch_id`; any change to a sketch's layers or elements; does not bubble to `project.changed`, whose subscribers only care about the tree and window title) |
| `UIEvents` | `ui.tab_opened`, `ui.tab_closed`, `ui.panel_changed` |

## Subscription Lifecycle (WidgetExtension)

GUI components extend `WidgetExtension`, which manages subscription lifetimes automatically:

```python
class DatasetTab(WidgetExtension):
    def setup_event_subscriptions(self):
        # All subscriptions tracked; auto-removed on widget destroy
        self.subscribe_to_event(DatasetEvents.DATASET_CHANGED, self.on_dataset_changed)
        self.subscribe_to_event(DatasetOperationEvents.DATASET_COLUMN_ADDED, self.on_column_added)

    def on_dataset_changed(self, data: dict):
        dataset_id = data["dataset_id"]
        if dataset_id == self.dataset_id:
            self.refresh_table()
```

## Pattern Subscriptions

Components can subscribe to all events in a category using glob-style patterns:

```python
# Receive any event whose name starts with "dataset."
self.event_bus.subscribe_pattern("dataset.*", self.on_any_dataset_event)

# Receive any project event
self.event_bus.subscribe_pattern("project.*", self.on_project_changed)
```

## Event Data Conventions

All event data is a plain `dict`. Common keys:

| Key | Present in |
|-----|-----------|
| `project_id` | ProjectEvents |
| `item_id` | project.item_added / removed |
| `dataset_id` | DatasetEvents, DatasetOperationEvents |
| `chart_id` | ChartEvents |
| `column_name` | column add/delete/dtype events |
| `row_indices` | row add/delete events |
| `fit_type` | FitEvents |
