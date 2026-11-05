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

Each label is the item type's emoji prefix plus the name (e.g. `✏️ Diagram` for a sketch). The prefixes live in one map, `utils/item_labels.py` (`ITEM_TYPE_PREFIXES`); build labels with `item_label(item_type, name)` and remove the prefix with `strip_item_prefix(label)`, never by slicing, because some prefixes are two characters (an emoji plus a variation selector).

## TabContainer (`gui/components/tabs/`)

Manages the workspace tabbed area:

```
TabContainer
├── CustomTabWidget             # QTabWidget with close buttons
├── WelcomeTab                  # Shown when no project is open
├── DatasetTab                  # Spreadsheet editor for a Dataset
├── ChartTab                    # Matplotlib chart canvas
├── NoteTab                     # Markdown note editor
└── SketchTab                   # Qt Graphics View sketch canvas
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

### SketchTab

- Hosts a `SketchCanvas` (below) for one `Sketch`, created from the tree's "Add Sketch" or the Data menu's "New Sketch" (`CreateSketchCommand`)
- Toolbar: one checkable button per tool (exclusive `QActionGroup`, single-key shortcuts V/P/L/R/E/T limited to the tab with `WidgetWithChildrenShortcut`), "Fit", the zoom level, and a status label for messages from the canvas (e.g. why drawing is refused)
- Fits the whole canvas into view the first time it is shown
- A `LayerManagerPanel` sits beside the canvas in a `QSplitter`; the toolbar's checkable "Layers" button shows or hides it (the splitter can't collapse it, so the button's state stays right)

### LayerManagerPanel (`gui/components/tabs/sketch/layer_manager_panel.py`)

- Lists the layers top first. The current row is the active layer (`SetActiveSketchLayerCommand`); each row (`LayerRow`) has checkable visibility and lock buttons with painted eye and lock icons. Double-click, F2 or Enter renames the active layer through `UIController.get_text_input()`
- Buttons add a layer above the active one, delete it (disabled for the last layer and for a locked one, with a tooltip saying why), and move it up or down. Every change goes through the layer commands above, so it is undoable
- Opacity slider: dragging only previews (`opacity_previewed` -> `SketchCanvas.preview_layer_opacity()`), and releasing commits one `SetSketchLayerPropertiesCommand`; keyboard steps and clicks on the groove commit at once
- Refreshes on `sketch.changed`. Rows are rebuilt only when layers are added, removed or reordered; otherwise each row is updated in place, so a toggle is never deleted while its own click is being handled

### Sketch canvas (`gui/components/tabs/sketch/`)

The only Qt Graphics View (`QGraphicsScene`/`QGraphicsView`) surface in the app; every other drawing surface is matplotlib. It is used because sketches need direct manipulation (hit-testing, dragging, resize handles, live strokes) that matplotlib does not provide.

- `SketchCanvas` (a `PGraphicsView`, so it owns its event subscriptions) draws a `Sketch` and never changes it: `rebuild()` replaces the scene with a fresh drawing of the model, so the model stays the single source of truth. It rebuilds on `sketch.changed` for its own sketch, so drawing, undo and redo all redraw the same way.
- It takes its frame colours from the theme's design tokens (`border_panel` around the paper, `border_control` for its edge) and re-applies them on theme change. The window background colour can't be used: in the light theme it is the same white as a default sketch, which hides where the canvas ends.
- The scene holds a paper rectangle of the canvas size (z = -1) and one invisible parent item per layer. A layer's z-value is its index, and each element's z-value is its index within the layer. Children stack only among siblings, so this gives the model's order with no limit on elements per layer. Layer visibility and opacity are set on the parent and apply to every child.
- `graphics_items.build_graphics_item()` turns an element into a `QGraphicsItem` through `GRAPHICS_ITEM_BUILDERS` (element class to builder). The item is placed at the element's anchor and rotated around it, so its local coordinates are the element's relative geometry. Text sizes are pixel sizes, so a sketch lays out the same on every platform.
- Scroll bars are always off: scroll bars that appear and vanish as the zoom changes resize the viewport during `fit_to_canvas()` and push the canvas off-centre.
- GUI tests that build text items need a `QApplication`; use pytest-qt's `qapp` fixture even when no widget is shown.

#### Tools and interaction (`tools/`)

- The canvas sends left-button press/move/release, in scene coordinates, to the active tool of its `ToolManager` (`ToolMode` -> tool class in `TOOL_CLASSES`). Pan (space+drag or middle-drag) and Ctrl+wheel zoom (10%-1000%, around the pointer) are handled by the canvas before any tool sees the event.
- Tools never change the model while dragging. They show work in progress through canvas previews (`show_preview()` for a new element, `preview_elements()` for changed copies of existing ones, `show_rubber_band()`), then commit one command on release, so each gesture is one undo step. Escape cancels a gesture and `rebuild()` restores the model's drawing.
- Drawing tools add to the active layer with `AddSketchElementCommand`, using `ToolManager.style` (`NewElementStyle`) for new elements. A locked or hidden active layer refuses drawing and the canvas emits `status_message`.
- The pen simplifies the pointer path (Ramer-Douglas-Peucker, 1.5 screen pixels) and stores the remaining points; the curve through them is drawn smooth (see the model's `curves.py`).
- `SelectTool`: click, Shift-click and rubber-band selection; drag to move and drag a handle to resize (Shift on a corner keeps proportions), both committed as one `TransformSketchElementsCommand`; Delete/Backspace runs `DeleteSketchElementsCommand`. Only elements on visible, unlocked layers can be picked (`is_interactive()`).
- The selection is a list of element ids on the canvas, so it survives `rebuild()`; elements that were deleted or whose layer became hidden or locked are dropped from it.
- `geometry.py` does the maths: hit-testing with a tolerance of a few screen pixels (an outline-only shape is hit on its edge, not inside, so it doesn't hide what lies within it), element bounds without the pen width, and how each element type scales when its box is resized. Resize handles are hidden while a selected element is rotated, because the box maths assumes unrotated elements.

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
