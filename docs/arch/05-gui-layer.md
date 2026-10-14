# GUI Layer

## Overview

The GUI is built with PySide6 (Qt6). All widgets extend `WidgetExtension`, which provides a standardized lifecycle and automatic EventBus subscription management.

## Main Window (`gui/main_window.py`)

```
PandaMainWindow (QMainWindow)
├── MenuBar                    # File, Edit, View, Tools, Help menus
├── QSplitter (horizontal)
│   ├── CollapsibleSidebar     # Left panel with icon tabs
│   └── TabContainer           # Right panel workspace
└── StatusBar
```

## WidgetExtension (`gui/core/widget_extension.py`)

Base class for all GUI components. Defines the initialization lifecycle:

```
_initialize()
  ├── _init_ui()                # Build widget tree (abstract, override this)
  ├── _apply_theme()            # Apply current theme colors/fonts
  └── setup_event_subscriptions()  # Register EventBus callbacks

# On destroy:
  └── Auto-unsubscribes all registered event callbacks
```

## CollapsibleSidebar (`gui/components/sidebar/`)

Icon-based left panel switcher. Each icon maps to a panel:

| Icon | Panel | Shown when |
|------|-------|-----------|
| Project tree | `ProjectViewPanel` | Always |
| Dataset info | `DatasetPanel` | Dataset item selected |
| Chart props | `ChartPropertiesPanel` | Chart item selected |
| Analysis | `AnalysisPanel` | Dataset or chart active |
| Signal | `SignalPanel` | Dataset active |
| Curve fit | `FitPanel` | Chart with series active |
| Transform | `TransformPanel` | Dataset active |

`ConditionalPanelManager` listens to `UIEvents` and `ProjectEvents` to show/hide the correct panel automatically based on active workspace context and selection.

### SidebarPanel (`gui/components/sidebar/panels/sidebar_panel.py`)

Base class (extends `PWidget`) all sidebar panels use for a consistent shell: a title pinned at the top via `_set_title()`, and a content area added via `_set_content(widget, scrollable=...)` — wrapped in a `QScrollArea` when `scrollable=True`, added directly otherwise (used by `ChartPropertiesPanel`, which scrolls per-tab instead, and `ProjectViewPanel`, whose tree scrolls natively).

### ProjectViewPanel

Hierarchical tree view of all project items. Subscribes to:
- `project.item_added` → inserts tree node
- `project.item_removed` → removes tree node
- `project.item_renamed` → updates label

Double-clicking an item opens it in a tab.

## TabContainer (`gui/components/tabs/`)

Manages the workspace tabbed area:

```
TabContainer
├── CustomTabWidget             # QTabWidget with close buttons
├── WelcomeTab                  # Shown when no project is open
├── DatasetTab                  # Spreadsheet editor for a Dataset
├── ChartTab                    # Matplotlib chart canvas
└── NoteTab                     # Markdown note editor
```

### DatasetTab

- Displays `pandas.DataFrame` in a `QTableView` with lazy loading for large datasets
- Subscribes to all `DatasetOperationEvents` to refresh individual cells/columns rather than rebuilding the full table
- Toolbar actions map directly to dataset commands (add/delete rows, add/delete columns, transform)

### ChartTab

- Embeds a `FigureCanvasQTAgg` (matplotlib → Qt bridge)
- `ChartRenderEngine` converts the `Chart` model into a `matplotlib.Figure`:
  1. Create figure and axes
  2. For each `DataSeries`: fetch columns from Dataset, call `ax.plot()` / `ax.scatter()` / etc.
  3. For each `SeriesType.FIT` DataSeries: plot its precomputed x/y curve data, overlay
  4. Apply `ChartConfiguration` (title, labels, legend, grid)
- Subscribes to `ChartEvents` to re-render on any chart change

### NoteTab

- Plain text editor with optional markdown preview split
- Subscribes to `NoteEvents` to sync content

## UIController (`gui/controllers/`)

Facade over all Qt dialog types. GUI components call `UIController` instead of constructing dialogs directly:

```python
# File dialogs
path = ui_controller.show_open_project_dialog()
path = ui_controller.show_save_project_dialog()
path = ui_controller.show_import_csv_dialog()

# Message dialogs
ui_controller.show_error("Something went wrong", detail)
ui_controller.show_warning("Are you sure?")
confirmed = ui_controller.show_question("Save before closing?")

# Input dialogs
name = ui_controller.show_text_input("Enter column name")
value = ui_controller.show_number_input("Enter threshold", default=0.0)
```

The `UIController` stores the `parent_widget` reference so all dialogs are properly modal.

## Theme System (`services/theme/`)

`ThemeManager` supports light and dark themes:

1. `ThemeManager.set_theme(ThemeMode.DARK)` → persists preference, emits `ThemeEvents.THEME_CHANGED`
2. All `WidgetExtension` subclasses receive the event and call `_apply_theme()`
3. `_apply_theme()` reads the current theme from `ThemeManager` and updates Qt stylesheets

Shared controls are styled once, in `ThemeManager.build_stylesheet()`, from the design tokens rather than per dialog or panel. Dropdowns are the example: create them with `DropDownComboBox` (or `ValueComboBox`, which extends it) and do not write a `QComboBox` rule in a widget or dialog stylesheet. The app-wide rule gives the field, caret, hover/focus and disabled states and the popup list, and `DropDownComboBox` makes the list open below the field (macOS otherwise opens a native menu over it).

## Background Tasks & Busy Operations (`services/qtasks/` & `gui/components/common/`)

Long-running operations (large CSV imports, analysis, signal processing, fitting on big datasets) run via `TaskScheduler`:

```
TaskScheduler
└── QThreadPool
    └── Worker (QRunnable)
        ├── run()             # Executes computation off the main Qt thread
        ├── signals.result    # Emitted on success
        └── signals.error     # Emitted on exception
```

During asynchronous tasks, panels display a `BusySpinner` widget to give visual progress feedback without blocking the UI or Qt event loop.

## Numeric Inputs (`gui/components/common/number_input.py`)

Number fields are `DecimalInput` (float) or `IntegerInput` (int), never `QDoubleSpinBox` / `QSpinBox`. They keep the spin-box API (`setRange`, `setDecimals`, `setSingleStep`, `setSuffix`, `setSpecialValueText`, `setValue`, `value`, `valueChanged`), including its keyboard tracking: `value()` follows what is typed as soon as it is a complete number in range, which matters on macOS where clicking a push button does not move focus out of the field.

What differs from a spin box:

- `-` / `+` step buttons (omit with `steppers=False` where a slider already moves the value); only the text field takes Tab focus, and Up/Down, Page Up/Down and Shift step from the keyboard.
- The wheel only edits the value while the field has focus; otherwise the event is ignored so the enclosing scroll area scrolls.
- `.` and `,` are both decimal separators, at most `decimals` digits can be typed, and the unit is a separate label instead of text in the field.

The frame draws the border and is styled by `ThemeManager` (`QFrame[numberInput="true"]`, driven by `focused` / `invalid` dynamic properties); the inner line edit sets its own flat stylesheet so a dialog-level `QLineEdit` rule cannot draw a second box inside it.

## Sidebar Panel Styling (`gui/components/sidebar/panels/`)

Panels do not carry their own copy of the panel stylesheet. `SidebarPanel` sets the `sidebarPanel` dynamic property, and `ThemeManager` (`_sidebar_panel_rules`) styles everything under it once, from the design tokens: panel background, `QGroupBox` and its title, the title bar (`#sidebarPanelTitle`), result text areas (`QTextEdit` / `QPlainTextEdit`), line edits and list widgets. A panel only styles what is specific to it, and most no longer override `_apply_theme()` at all.

Per-widget colours are semantic hooks rather than stylesheets (`gui/components/common/label_role.py`):

| Hook | Use |
|---|---|
| `set_label_role(label, "hint")` | secondary helper text |
| `set_label_role(label, "warning")` / `"error"` | something to be careful about / a problem |
| `set_label_role(label, "code")` | monospace boxed value, e.g. a fitted equation |
| `set_error_state(text_area, error=...)` | show a result or preview text area's content as an error |

Do not write `color: red` or a hex colour in a panel: the hooks follow the theme.

Layout is shared too: build the content widget's layout with `SidebarPanel._new_content_layout(content)` (same margin and section spacing in every panel) and rows of label/field pairs with `PanelFormLayout` (left-aligned labels, fields that fill the row, combo boxes that can shrink so a long dataset name cannot widen the panel). `SidebarPanel._set_content` also makes every combo box already in the content compact.

Adding a rule that depends on a stylesheet selector like `QWidget[sidebarPanel="true"] QLabel { color: ... }` would out-rank the label roles (higher specificity), so label colours are only set through the `role` property.
