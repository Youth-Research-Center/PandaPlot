# Sub-Issue 1 Design Specification: Sketch Data Model, Layer Architecture, and Project Persistence

**Parent Issue:** [#148 - Add a sketching tab (freehand/shape drawing canvas item)](https://github.com/Youth-Research-Center/PandaPlot/issues/148)
**Milestone:** 11. Sketching Canvas
**Labels:** `area: chart-types`, `effort: m`, `enhancement`, `priority: medium`

---

## 1. Goal & Objectives

Establish the foundational data domain model for the `Sketch` item, its layer hierarchy, element primitives, and its serialization/deserialization logic for persistence inside `.pplot` project zip archives.

---

## 2. Model Design Architecture

### 2.1 Class Hierarchy

```
pandaplot/models/project/items/
├── sketch.py
│   ├── Sketch (inherits Item, pandaplot/models/project/items/item.py)
│   ├── SketchLayer
│   └── elements/
│       ├── sketch_element.py (Base abstract class)
│       ├── freehand_element.py
│       ├── line_element.py
│       ├── rectangle_element.py
│       ├── ellipse_element.py
│       └── text_element.py
```

`Sketch` is a plain `Item`, not an `ItemCollection` — it holds layers/elements as nested value data (via `to_dict`/`from_dict`), the same way `Chart` holds its series config, not as child `Item`s in the project tree. `ItemCollection` (used by `Folder`, `ImageGallery`) is for items that contain *other project-tree items*, which doesn't apply here.

### 2.2 Classes & Attributes

#### `Sketch` (`pandaplot/models/project/items/sketch.py`)
Inherits from `Item`. Following the `Chart`/`Image` convention, overrides `to_dict()`/`from_dict()` to add its own fields on top of `Item`'s (`id`, `name`, `parent_id`, `created_at`, `modified_at`, `metadata`):
- `layers: list[SketchLayer]`: Ordered list of layers (index 0 is bottom-most, last index is top-most).
- `active_layer_id: str`: ID of currently active drawing layer.
- `canvas_width: float` / `canvas_height: float`: Canvas dimensions (default: 1920x1080).
- `background_color: str`: Hex background color (default: `"#FFFFFF"`).

#### `SketchLayer`
- `id: str`: UUID identifier.
- `name: str`: Layer name (e.g. `"Layer 1"`).
- `visible: bool`: Visibility flag (default: `True`).
- `locked: bool`: Lock flag preventing modifications (default: `False`).
- `opacity: float`: Layer opacity between `0.0` and `1.0` (default: `1.0`).
- `elements: list[SketchElement]`: Ordered list of elements within this layer.

#### `SketchElement` (Abstract Base Class)
- `id: str`: UUID identifier.
- `type: str`: Element discriminator string (`"freehand"`, `"line"`, `"rectangle"`, `"ellipse"`, `"text"`) used for polymorphic `from_dict` dispatch (see 2.3).
- `x: float`, `y: float`: Anchor position in canvas coordinate space.
- `rotation: float`: Rotation angle in degrees.
- `stroke_color: str`: Stroke color in hex/RGBA string (e.g. `"#000000"`).
- `stroke_width: float`: Stroke line width (default: `2.0`).
- `stroke_style: str`: `"solid"`, `"dashed"`, `"dotted"`, `"dash_dot"`.
- `fill_color: str`: Fill color in hex/RGBA string or `"none"`.

#### Concrete Element Types

1. **`FreehandElement`**:
   - `points: list[tuple[float, float]]`: List of `(x, y)` relative or canvas coordinates forming the path.

2. **`LineElement`**:
   - `x1: float, y1: float`: Start coordinate.
   - `x2: float, y2: float`: End coordinate.

3. **`RectangleElement`**:
   - `width: float`: Width of rectangle.
   - `height: float`: Height of rectangle.
   - `corner_radius: float`: Radius for rounded corners (default `0.0`).

4. **`EllipseElement`**:
   - `rx: float`: X-radius or width.
   - `ry: float`: Y-radius or height.

5. **`TextElement`**:
   - `text: str`: Text content string.
   - `font_family: str`: Font family (default: `"Sans-Serif"`).
   - `font_size: int`: Font size in points (default: `14`).
   - `is_bold: bool`, `is_italic: bool`: Formatting flags.
   - `alignment: str`: `"left"`, `"center"`, `"right"`.

### 2.3 Polymorphic element (de)serialization

`SketchElement.from_dict()` needs a `type` -> subclass lookup so `SketchLayer.from_dict()` can reconstruct the right concrete class per element. Keep this as a small local `dict[str, type[SketchElement]]` in `sketch_element.py` (populated by the five concrete modules) rather than reusing `ItemDataManagerFactory` — that factory dispatches project-tree item *types*, not element sub-records within one item's own JSON. Sub-Issue 5's proposed `SketchComponentRegistry` (see that spec's scope note) is where this seam should eventually move if/when domain extensions add element types; don't build that registry here.

---

## 3. Storage & Persistence (`pandaplot/storage/sketch_data_manager.py`)

### 3.1 `ItemDataManager` base class (actual API)

There is no `IItemDataManager` interface in the codebase (that name doesn't appear anywhere). The real base class is `ItemDataManager(ABC, Generic[TItem])` (`pandaplot/storage/item_data_manager.py`):

```python
class ItemDataManager(ABC, Generic[TItem]):
    @abstractmethod
    def save(self, item: TItem, zip_file: ZipFile, path_in_zip: str) -> None: ...

    @abstractmethod
    def load(self, item_class: type[TItem], zip_file: ZipFile, path_in_zip: str, schema_version: int) -> TItem: ...
```

`Sketch` has no binary blob to store (unlike `Image`), so it should follow `ChartDataManager`'s pattern exactly — one JSON file at `{path_in_zip}.json`, built from `item.to_dict()` / `item_class.from_dict()` — rather than `ImageDataManager`'s metadata+blob split:

```python
class SketchDataManager(ItemDataManager[Sketch]):
    def save(self, item: Sketch, zip_file: ZipFile, path_in_zip: str) -> None:
        zip_file.writestr(f"{path_in_zip}.json", json.dumps(item.to_dict(), indent=2))

    def load(self, item_class: type[Sketch], zip_file: ZipFile, path_in_zip: str, schema_version: int) -> Sketch:
        data = json.loads(zip_file.read(f"{path_in_zip}.json").decode("utf-8"))
        data = migrate_sketch(data, schema_version)  # pandaplot/models/migrations/per_item/sketch.py
        return item_class.from_dict(data)
```

`path_in_zip` is supplied by the caller (`ProjectDataManager`), not derived from the item's own id inside the manager — don't hardcode a `sketch_{id}.json` filename convention inside `SketchDataManager` itself.

Example `to_dict()` output:

```json
{
  "id": "c30985da-7e3e-4d51-92e1-4566c3a01724",
  "name": "Circuit Sketch",
  "parent_id": null,
  "created_at": "2026-09-06T10:00:00",
  "modified_at": "2026-09-06T10:00:00",
  "metadata": {},
  "canvas_width": 1920.0,
  "canvas_height": 1080.0,
  "background_color": "#FFFFFF",
  "active_layer_id": "layer-uuid-1",
  "layers": [
    {
      "id": "layer-uuid-1",
      "name": "Background Grid",
      "visible": true,
      "locked": false,
      "opacity": 1.0,
      "elements": [
        {
          "id": "elem-uuid-1",
          "type": "rectangle",
          "x": 100.0,
          "y": 100.0,
          "width": 200.0,
          "height": 150.0,
          "rotation": 0.0,
          "stroke_color": "#000000",
          "stroke_width": 2.0,
          "stroke_style": "solid",
          "fill_color": "none"
        },
        {
          "id": "elem-uuid-2",
          "type": "freehand",
          "x": 0.0,
          "y": 0.0,
          "rotation": 0.0,
          "stroke_color": "#FF0000",
          "stroke_width": 3.0,
          "stroke_style": "solid",
          "fill_color": "none",
          "points": [[10.0, 10.0], [15.0, 12.0], [20.0, 25.0]]
        }
      ]
    }
  ]
}
```

### 3.2 Storage Registration (`pandaplot/app.py`, where all other item types are wired up — see `_create_item_data_manager_factory` around line 36-42)

```python
factory.register("sketch", Sketch, SketchDataManager(), "sketch")
```

(the 4th argument is the type's own name, matching every existing registration — `"image"`, `"chart"`, `"note"` etc. — not a generic `"json"`.)

Also register the tab loader in `_create_tab_factory` (same file, ~line 68-71), covered in Sub-Issue 4.

---

## 4. Verification & Testing Plan

1. **Unit Tests (`tests/models/project/items/test_sketch.py`)**:
   - Verify creation of `Sketch`, default layer initialization, adding/removing layers.
   - Verify `to_dict()`/`from_dict()` round-trip for all five element types, including the `type`-dispatch in `SketchElement.from_dict()`.
   - Verify integrity of element ordering in layers.
2. **Storage Persistence Unit Tests (`tests/storage/test_sketch_data_manager.py`)**:
   - Save `Sketch` into a real `ZipFile` (temp file), following the existing pattern in `tests/storage/test_chart_data_manager.py`.
   - Load back and verify deep equality of sketch properties, layers, and elements.
3. **Factory Registration Test**:
   - Ensure `ItemDataManagerFactory` resolves `"sketch"` correctly (manager, item class, extension).
4. **Migration stub test**:
   - `migrate_sketch(data, schema_version=1)` is a no-op passthrough for the initial version; add the test now so later schema changes have a place to add coverage.
