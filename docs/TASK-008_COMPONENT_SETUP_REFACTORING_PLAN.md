# TASK-008 Implementation Plan: Component Setup Refactoring

## Overview

TASK-008 aims to remove UI component setup and orchestration responsibilities from `PandaMainWindow` (and other monolithic locations) into dedicated builder / coordinator layers. This reduces coupling, clarifies responsibilities, and prepares the UI architecture for future modularization (multi‑project, plugin panels, dynamic feature toggling). It complements TASK-007 (event bus migration) by ensuring creation & wiring are event‑driven instead of signal/property interleaving inside the main window.

## Current State Analysis

### Centralized, Overloaded Main Window (`pandaplot/gui/main_window.py`)
Responsibilities currently mixed inside `PandaMainWindow`:
- Instantiates side panels (transform, analysis, chart properties, fit panel) in dedicated `setup_*` methods.
- Owns conditional panel manager registration logic.
- Wires project view panel signals directly to tab container methods.
- Creates and shows settings dialog directly.
- Subscribes to domain events (transform applied, tab changed) and performs contextual logic for panels & dataset tabs.
- Contains TODO markers indicating misplaced logic.

### Pain Points
- Hard to unit test panel creation logic in isolation.
- Adding a new panel requires editing main window code (violates OCP).
- Direct references to concrete panel classes increase coupling.
- Settings dialog logic belongs in a controller/service layer.
- Tab interactions & project view actions should flow through commands or events.

## Objectives
1. Extract component creation & registration into a dedicated UI assembly layer (`UIComponentRegistry` or `UIBootstrapper`).
2. Decouple tab/container operations from project tree signals (use events defined in TASK-007 mapping).
3. Move per-feature setup (Transform, Analysis, ChartProperties, Fit) into individual provider classes with a uniform interface.
4. Reduce main window to a thin shell: layout + host container only.
5. Improve testability by allowing provider classes to be tested independently.
6. Keep future extensibility: adding a panel = implement provider + register.

## Target Architecture

```
PandaMainWindow (shell)
  ├── UIComponentBootstrapper (orchestrates)
  │     ├── PanelProvider instances (one per dynamic panel)
  │     ├── TabIntegrationService
  │     └── SettingsUIService
  ├── Sidebar (CollapsibleSidebar)
  ├── TabContainer
  └── EventBus (coordination backbone)
```

### Key New Modules
- `pandaplot/gui/bootstrap/ui_bootstrapper.py` – High-level orchestrator.
- `pandaplot/gui/bootstrap/panel_provider_base.py` – Abstract base for panel providers.
- `pandaplot/gui/bootstrap/providers/` – Concrete providers: TransformPanelProvider, AnalysisPanelProvider, ChartPropertiesPanelProvider, FitPanelProvider.
- `pandaplot/gui/services/tab_integration_service.py` – Subscribes to project item open requests & opens tabs.
- `pandaplot/gui/services/settings_ui_service.py` – Handles settings dialog show/apply (publishes events instead of direct callback to main window).

## Refactoring Phases

### Phase 1: Foundations (Non-breaking)
- [ ] Introduce provider base + bootstrapper skeleton (no usage yet).
- [ ] Add `SettingsUIService` calling existing `SettingsDialog` but emitting `ui.settings.requested` & `settings.changed` events (align TASK-007 naming).
- [ ] Add `TabIntegrationService` subscribing to project item open events.

### Phase 2: Parallel Construction
- [ ] Implement concrete panel providers; each encapsulates:
  - create_panel(app_context) -> QWidget
  - panel_id, icon, visibility_condition (callable taking TabContainer/app_context)
  - priority
  - optional event subscriptions for dynamic behavior
- [ ] Bootstrapper builds providers, registers with sidebar + conditional manager.
- [ ] Keep legacy setup methods temporarily; enable dual path behind a feature flag constant (e.g., `USE_BOOTSTRAP = True`).

### Phase 3: Switch Main Window
- [ ] Replace `create_widgets` internal panel creation with a call to bootstrapper.
- [ ] Remove direct signal `.connect` usage for project_view_panel → rely on TabIntegrationService (after TASK-007 dual emission).
- [ ] Move tab change handling logic (`on_tab_changed_event`) into either TabIntegrationService or a lightweight `PanelVisibilityCoordinator` embedded in bootstrapper.

### Phase 4: Remove Legacy Code
- [ ] Delete `setup_transform_panel`, `setup_analysis_panel`, `setup_chart_properties_panel`, `setup_fit_panel` from main window.
- [ ] Delete direct settings dialog method or delegate it fully to SettingsUIService (main window just emits `ui.settings.requested`).
- [ ] Remove redundant event subscriptions from main window after relocation.

### Phase 5: Stabilization & Cleanup
- [ ] Update tests (or add) for: panel provider registration, tab open events, settings change path.
- [ ] Update `ARCHITECTURE.md` (UI Composition section) and add guidelines in `CONTRIBUTING.md`.
- [ ] Remove `USE_BOOTSTRAP` flag after confidence (or invert to `LEGACY_UI_SETUP` fallback for one release).

## Component Provider Contract

Pseudo-interface:
```python
class PanelProvider(Protocol):
    panel_id: str
    icon: str
    priority: int
    def create(self, app_context) -> QWidget: ...
    def visibility_condition(self, tab_container) -> bool: ...
    def register_events(self, event_bus): ...  # optional
```

Registration Flow:
1. Bootstrapper instantiates all providers.
2. For each provider: create panel, add to sidebar, set initial visibility (hidden), register with ConditionalPanelManager.
3. Force evaluation after all registrations.

## Conditional Visibility Strategy
- Replace ad-hoc calls in setup methods with standardized evaluation.
- Each provider supplies pure function `visibility_condition` enabling deterministic tests.

## Event & Command Integration
- All tab open actions respond to events (`project.item.*_open_requested`).
- Settings actions respond to `ui.settings.requested` event.
- Additional panel context updates (e.g., dataset selection) may subscribe to `ui.tab.changed` or dataset events directly via provider `register_events` method.

## Testing Strategy

Unit Tests:
- Provider visibility condition returns expected boolean for sample tab states.
- Bootstrapper registers all providers (assert sidebar contains expected keys).
- SettingsUIService emits events when dialog applied.

Integration Tests:
- Emit note open event → Note tab appears.
- Emit dataset open + transform preview event → Transform panel becomes visible.

Regression Tests:
- Launch main window (headless mode if possible) ensures no exceptions.
- Ensure no direct panel creation code remains in main window (grep verification).

## Success Criteria
1. ✅ `PandaMainWindow` contains no panel-specific setup logic.
2. ✅ Adding a new panel requires only creating a provider + registration in bootstrapper.
3. ✅ Tab open & settings flows use events only (no custom cross-component signals).
4. ✅ Documentation updated; contributors understand provider pattern.
5. ✅ All tests pass; no feature regression.

## Risks & Mitigations
- Risk: Boot sequence ordering bugs (panels referencing tab container before ready) → Mitigate: bootstrapper constructs after tab container instantiation; pass dependencies explicitly.
- Risk: Visibility flicker on startup → Evaluate conditions only after all panels registered; optionally batch updates.
- Risk: Increased abstraction complexity → Provide clear docs + minimal provider surface.

## Rollback Plan
- Keep legacy setup methods behind feature flag until after verification.
- Re-enable legacy by toggling constant if critical defect discovered.

## Future Enhancements
- Dynamic provider discovery via entry points / plugin registry.
- Lazy creation (instantiate panel only when first needed to reduce startup time).
- Declarative JSON/YAML panel configuration for rapid prototyping.

## Immediate Next Steps
1. Create bootstrap & provider base modules.
2. Implement Transform & Analysis providers first (highest conditional logic usage).
3. Integrate TabIntegrationService and migrate project view open actions.
4. Add initial tests for provider registration and tab open events.

---
Prepared for TASK-008 execution.
