# Sub-Issue 4 Design Specification: Layer Management UI, Tab Editor, and Project Tree Integration

**Parent Issue:** [#148 - Add a sketching tab (freehand/shape drawing canvas item)](https://github.com/Youth-Research-Center/PandaPlot/issues/148)
**Milestone:** 11. Sketching Canvas
**Labels:** `area: chart-types`, `effort: m`, `enhancement`, `priority: medium`

---

## 1. Goal & Objectives

Assemble the complete `SketchTab` view widget, register `Sketch` with `TabFactory` and project tree UI, and build a feature-rich `LayerManagerPanel` sidebar widget allowing users to manage layer stack order, visibility, locking, opacity, and layer creation/deletion.

---

## 2. GUI Integration & Architecture

```
pandaplot/gui/components/tabs/sketch/
├── sketch_tab.py               # Main tab view combining canvas, toolbars & panels
└── layer_manager_panel.py      # Layer hierarchy management sidebar panel
```

### 2.1 `SketchTab` View Composition
- Top: Drawing Tools & Property Bar.
- Center: `SketchCanvas` QGraphicsView.
- Right Sidebar (Collapsible): `LayerManagerPanel`.

### 2.2 Tab Registration (`pandaplot/app.py`, `_create_tab_factory`, alongside the other `factory.register(ItemClass, loader)` calls around line 68-71)
```python
factory.register(Sketch, lambda app_ctx, item, parent: SketchTab(app_ctx, item, parent))
```
(matches the existing `factory.register(Chart, _load_chart_tab)` style — a small `_load_sketch_tab` helper following the other tabs' naming is fine too.)

### 2.3 Project Tree Context Menu & Icon
- Add **"New Sketch"** option to project tree context menu (`ProjectTree` / `ProjectViewPanel`), following the existing `Note`/`Chart`/`Image` "New ..." actions.
- There is no separate icon-asset registry (`app_icon.py` only builds the single window/about-dialog panda icon, unrelated to item types). Item-type icons in the tree are plain emoji prefixes on the label text (see `pandaplot/gui/components/sidebar/project/project_tree_manager.py` and `item_name_delegate.py`, which strips/restores the prefix during inline rename). Add a new prefix for `Sketch` there, e.g. `✏️` or `🖊️`, following the pattern of the existing `📁`/`📝`/`📊` prefixes.

---

## 3. Layer Manager Panel (`layer_manager_panel.py`)

### 3.1 UI Elements

- **Layer List**: Reorderable list item widgets showing:
  - Layer name (editable on double click).
  - Visibility toggle icon (Eye open / Eye closed).
  - Lock toggle icon (Padlock locked / Padlock unlocked).
  - Active layer highlight badge.
- **Layer Controls Toolbar**:
  - `+ Add Layer` button.
  - `- Delete Layer` button (disabled if only 1 layer remains).
  - `▲ Move Layer Up` / `▼ Move Layer Down` reordering buttons.
  - Opacity slider for active layer (`0%` to `100%`).

### 3.2 Layer Mechanics & Z-Index Rendering
- Canvas z-value mapping: Layer index directly dictates `zValue` range in `QGraphicsScene` (e.g. `layer_index * 1000 + element_index`).
- Hidden layers (`visible=False`): Associated `QGraphicsItem` group set to `setVisible(False)`.
- Locked layers (`locked=True`): Associated `QGraphicsItem` items set `GraphicsItemFlag.ItemIsSelectable` and `ItemIsMovable` to `False`.
- All layer add/remove/reorder/visibility/lock actions go through `Command` subclasses (e.g. `AddLayerCommand`, `ReorderLayerCommand`), consistent with Sub-Issue 3's element commands, so they're undoable.

---

## 4. Verification & Testing Plan

1. **Tab Factory Integration Test**:
   - Verify `TabFactory.create_tab()` returns a valid `SketchTab` for a `Sketch` item.
2. **Layer Manager UI Unit & Integration Tests**:
   - Test adding a layer creates a new `SketchLayer` in the model and updates the scene, and that it's undoable.
   - Test layer reordering updates z-indexes of graphics elements.
   - Test toggling lock/visibility dynamically enables/disables graphics interaction.
3. **Project Tree Action Tests**:
   - Verify clicking "New Sketch" creates a `Sketch` item in the project model and tree view with the correct label prefix.
