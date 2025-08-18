# TASK-007 Implementation Plan: Remove Qt Signals Dependency and Use Event Bus

## Overview

This document outlines the implementation strategy for TASK-007: systematically removing direct Qt signal/slot dependencies in favor of the central EventBus system. The goal is to decouple UI components, reduce brittle point-to-point wiring, and enable easier future refactors (e.g., multi‑project, background tasks, plugin/UI modularization).

## Objectives

1. Replace all custom PySide6 Signal usages (inter-component communication) with EventBus events.
2. Preserve internal widget-level Qt signals that are inherent to Qt controls (e.g., button.clicked) – only remove cross-component custom signals.
3. Standardize event naming and payload structure using existing `event_types` hierarchy (additions where necessary).
4. Provide migration shims to minimize risky big-bang changes (incremental rollout).
5. Ensure parity: no feature regressions (opening tabs, applying transforms, chart updates, settings, etc.).
6. Add tests covering new event-based flows where unit tests exist for prior signal-based behavior (or create new minimal tests).

## Current Signal Inventory (Custom)

(From code grep) – representative list to convert:
- settings_dialog.SettingsDialog: `settings_changed`
- chart_properties_panel.ChartPropertiesPanel: `colorChanged`, `chart_created`, `chart_updated`, `preview_requested`
- conditional_panel_manager.ConditionalPanelManager: `panel_visibility_changed`
- icon_bar.IconBar: `panel_requested`, `settings_requested`
- fit_panel.FitPanel: `fit_completed`, `fit_applied`
- note_tab.NoteTab: `content_changed`, `note_renamed`, (secondary: `tab_close_requested`, `title_changed`)
- generic tab components: tab/tab_bar `tab_close_requested`
- transform_controller.TransformController: `transform_completed`, `transform_failed`, `preview_ready`
- project_view_panel.ProjectViewPanel: `note_open_requested`, `dataset_open_requested`, plus (in main window references) chart related open/create requests.

## Target Event Mapping

| Category | Old Signal | New Event Type | Payload Keys |
|----------|------------|----------------|--------------|
| Settings | settings_changed | settings.changed | settings (dict), scope ("application"|"project") |
| UI Panels | panel_requested | ui.panel.requested | panel_name |
| UI Panels | settings_requested | ui.settings.requested | none |
| UI Panels | panel_visibility_changed | ui.panel.visibility_changed | panel_name, is_visible |
| Tabs | tab_close_requested | ui.tab.close_requested | tab_id / index |
| Tabs | title_changed | ui.tab.title_changed | tab_id, title |
| Notes | content_changed | note.content.changed | note_id, content (maybe diff later) |
| Notes | note_renamed | note.renamed | note_id, old_name, new_name |
| Datasets/Transform | transform_completed | dataset.transform.completed | dataset_id, column_name, result_meta |
| Datasets/Transform | transform_failed | dataset.transform.failed | dataset_id, error_message |
| Datasets/Transform | preview_ready | dataset.transform.preview_ready | dataset_id, preview_data |
| Charts | chart_created | chart.created | chart_id, source_dataset_id, config |
| Charts | chart_updated | chart.updated | chart_id, changes |
| Charts | preview_requested | chart.preview.requested | chart_temp_config |
| Charts | colorChanged | chart.color.changed | chart_id, color |
| Fit | fit_completed | analysis.fit.completed | dataset_id, params, stats |
| Fit | fit_applied | analysis.fit.applied | dataset_id, params |
| Project View | note_open_requested | project.item.note_open_requested | note_id, note_name |
| Project View | dataset_open_requested | project.item.dataset_open_requested | dataset_id, dataset_name |
| Project View | chart_open_requested | project.item.chart_open_requested | chart_id |
| Project View | chart_create_requested | project.item.chart_create_requested | dataset_id, chart_config |
| Project View | plot_tab_requested | project.item.plot_tab_requested | dataset_id |

Add new event constants in `event_types` if not present.

## Phased Migration Approach

### Phase 0: Preparation
- [ ] Add/extend event type constants in `pandaplot/models/events/event_types.py` (non-breaking).
- [ ] Introduce helper adapter: `SignalToEventAdapter` (temporarily connect old signals to event emissions for incremental refactor).
- [ ] Add logging category for deprecation warnings when an old signal path is used.

### Phase 1: Core Infrastructure
- [ ] Implement `SignalToEventAdapter` in `pandaplot/models/events/adapters.py` (new file):
  - Accept (signal, event_type, payload_builder lambda)
  - Connect once; on signal emit -> build payload -> `event_bus.emit(event_type, payload)`
  - Track adapters for removal later.
- [ ] Update `AppContext` (if needed) to expose a method `register_signal_adapter` for central tracking (optional cleanup on shutdown).

### Phase 2: Read-Only Consumers
Convert components that only listen (no emission): replace signal connections with event subscriptions.
- Main window tab opening logic: replace `project_view_panel.*_requested.connect(...)` with event subscriptions.
- Conditional panel manager triggers (subscribe to `ui.tab.changed` or dataset selection events already present) – ensure correct mapping.

### Phase 3: Dual-Path Emission
For each emitting component:
1. Keep existing Signal attribute (for now).
2. Add event emission in the same method that fires the original signal OR via adapter.
3. Mark signal as deprecated in docstring.
4. Add unit tests for new events.

Components in this phase: ProjectViewPanel, IconBar, NoteTab, TransformController, ChartPropertiesPanel, FitPanel, SettingsDialog.

### Phase 4: Consumer Switch-Off
- Remove direct signal connections in all consumers relying on adapters.
- Replace with `subscribe_to_event` calls (using `EventBusComponentMixin`).
- Ensure payload compatibility; adjust handlers to accept `event_data` dict.

### Phase 5: Signal Removal
- Remove Signal declarations and adapter scaffolding once all references are event-based.
- Update tests to remove any signal-specific mocks.
- Run grep to ensure no remaining `.connect(` usages with these custom signals (except intrinsic Qt widget signals).

### Phase 6: Cleanup & Documentation
- Update `ARCHITECTURE.md` with new communication pattern section.
- Add migration note referencing removal of custom signals.
- Add a developer guide snippet to `CONTRIBUTING.md` describing event naming conventions.

## Event Naming Conventions
- Hierarchical, dot-delimited, nouns first then action (past tense for completed operations, present/progressive for in-progress or requested):
  - requested → an action request initiated by UI intent
  - created/updated/completed/failed → result states
  - changed → generic state mutation

## Data Payload Guidelines
- Always include id fields (`*_id`).
- Include `original_event` automatically from EventBus hierarchy logic.
- Provide minimal shape; heavy structures (e.g., full dataset) avoided.
- For large objects (preview data) ensure they are lightweight (e.g., summary or first N rows) – future optimization task if needed.

## Required Additions to event_types
Add enumerations/constants, grouping by domain (example skeleton):
- SettingsEvents
- UIEvents additions (panel.*, tab.*, settings.requested)
- NoteEvents
- DatasetTransformEvents
- ChartEvents
- FitEvents
- ProjectItemRequestEvents

## Testing Strategy

Unit Tests:
- Event emitted when former signal action occurs (e.g., opening note triggers `project.item.note_open_requested`).
- Transform success/fail events.
- Note rename and content change events.
- Chart create/update events.

Integration Tests:
- Simulate project tree item double-click → verify tab created via event.
- Simulate settings apply → verify `settings.changed` event and consumer reaction (mock subscriber).

Regression / Safety:
- During dual-path phase: ensure both legacy signal and event paths fire exactly once (no duplicates).
- After removal: ensure no attribute errors (access to removed signals) – run tests & grep.

## Metrics of Success
1. ✅ Zero remaining custom Signal declarations for cross-component communication.
2. ✅ All inter-component interactions observable on EventBus.
3. ✅ No increase in test failure count; new tests pass.
4. ✅ Architecture docs updated; contributors guided on event usage.
5. ✅ Logging shows deprecation warnings only during interim phases (removed after Phase 5).

## Risks & Mitigations
- Risk: Unintended duplicate handling (signal + event) → Mitigate with temporary guard flags in handlers if needed.
- Risk: Performance overhead from broader event propagation → Mitigate by specific event types (avoid overusing wildcards in subscribers).
- Risk: Ordering expectations from synchronous signal chaining → Document synchronous nature of EventBus emit (current implementation is synchronous); if async needed later wrap handlers.

## Rollback Strategy
- Keep a feature branch per phase; if issues arise revert to last stable phase where both systems co-exist.
- Adapters allow reverting components individually.

## Future Enhancements (Post-Task)
- Add async dispatch / queue for heavy handlers.
- Introduce structured schema validation for event payloads (pydantic or lightweight custom validators).
- Add profiling hooks to measure handler execution time.

## Actionable Next Steps (Immediate)
1. Create adapters module and extend `event_types` with new constants (Phase 0/1).
2. Implement dual-path for ProjectViewPanel and main window tab actions first (highest usage frequency).
3. Add initial unit tests for new events before removing signals.

---
Prepared for TASK-007 execution.  
