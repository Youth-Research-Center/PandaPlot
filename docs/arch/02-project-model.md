# Project Model and Items

## Hierarchy

```
Project (ItemCollection)
└── items: List[Item | ItemCollection]
    ├── Dataset      (wraps pandas.DataFrame)
    ├── Chart        (DataSeries, incl. FIT-type fits + ChartConfiguration)
    ├── Note         (markdown text + tags)
    ├── Sketch       (vector drawing: ordered layers of elements)
    └── Folder       (ItemCollection — nested container)
```

The project maintains a **flat index** (`dict[str, Item]`) alongside the hierarchy for O(1) lookup by item ID.

## Base Classes

### `Item` (`models/project/items/item.py`)

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | UUID, immutable |
| `name` | `str` | User-visible label |
| `created_at` | `datetime` | Creation timestamp |
| `updated_at` | `datetime` | Last modification |
| `metadata` | `dict` | Arbitrary key-value extras |

### `ItemCollection` (`models/project/items/item.py`)

Extends `Item`. Adds:
- `items: list[Item]` — ordered children
- `add_item(item)` / `remove_item(item)` / `find_item(id)` methods

## Concrete Item Types

### Dataset (`models/project/items/dataset.py`)

```
Dataset
├── dataframe: pd.DataFrame     # The actual data
├── source_file: str | None     # Original import path
└── metadata: dict              # Column descriptions etc.
```

Datasets are the primary data source for charts and analyses.

### Chart (`models/project/items/chart.py`)

```
Chart
├── chart_type: ChartType       # LINE, SCATTER, BAR, STACKED_BAR, HIST, DENSITY, VECTOR, COLORMAP, HEATMAP, PIE, SCATTER3D, LINE3D, SURFACE, WIREFRAME, BAR3D, TRISURF, VECTOR3D, BOX
├── config: ChartConfiguration  # title, axis labels, legend, grid
└── data_series: list[DataSeries]  # Plot order = z-order; fits are FIT-type entries in this list

DataSeries
├── dataset_id: str             # Reference to a Dataset (for a fit: the source dataset)
├── x_column_id / y_column_id   # Stable column ids (x_column / y_column: name fallback)
├── series_type: SeriesType     # LINE, SCATTER, ..., FIT
├── y_axis: YAxis               # PRIMARY or SECONDARY
├── style: SeriesStyleBase      # Per-type style class (FitStyle for FIT)
└── precomputed_x_data / precomputed_y_data  # FIT only: the fitted curve snapshot

FitStyle (style of a FIT series)
├── color / line_style / line_width, band_fill_*  # Curve and confidence-band look
├── fit_type / fit_params / fit_stats             # What was fitted, and how well
├── confidence_lower / confidence_upper           # Band arrays (+ *_column_id for manual fits)
└── is_manual: bool                               # Converted from a series (editable source)
```

Fits are the `data_series` entries whose `is_fit` is true.

### Note (`models/project/items/note.py`)

```
Note
├── content: str                # Raw markdown text
└── tags: list[str]             # User-defined tags
```

### Sketch (`models/project/items/sketch/`)

```
Sketch
├── layers: list[SketchLayer]   # Index 0 is drawn first (bottom-most); never empty
├── active_layer_id: str        # Layer new elements go on; always names an existing layer
├── canvas_width / canvas_height  # Canvas size in canvas units (default 1920 x 1080)
└── background_color: str

SketchLayer
├── name, visible, locked, opacity (0.0-1.0)
└── elements: list[SketchElement]   # Index order = drawing order within the layer

SketchElement (base)
├── x, y                        # Anchor in canvas coordinates
├── rotation                    # Degrees
└── stroke_color / stroke_width / stroke_style: StrokeStyle / fill_color (None = no fill)
```

Each element type keeps its geometry relative to its anchor, so moving an element only changes `x`/`y`:

| Type | Anchor | Geometry |
|------|--------|----------|
| `FreehandElement` | stroke origin | `points`: offsets from the anchor of the points a smooth curve passes through (centripetal Catmull-Rom, drawn as cubic Béziers; `curves.py`) |
| `LineElement` | start point | `dx`, `dy`: end point offset |
| `RectangleElement` | top-left corner | `width`, `height`, `corner_radius` |
| `EllipseElement` | centre | `rx`, `ry`: radii |
| `TextElement` | top-left corner | `text`, font fields (`font_size` in canvas pixels; part of its geometry, so resizing a label changes it), `alignment: TextAlignment` |

Layers and elements are value data of the sketch, not project-tree items, so `Sketch` is a plain `Item` rather than an `ItemCollection`. Element dicts carry a `type` string; `SketchElement.from_dict()` looks it up in the module-level `ELEMENT_TYPES` dict, so a new element type registers by adding to that dict. Elements of an unknown type are skipped on load.

Each element class lists its `GEOMETRY_FIELDS` (changed by move, resize and rotate) and its `STYLE_FIELDS`, the style fields it actually draws with: shapes and freehand strokes have stroke and fill, a line has no fill, and text has its colour (`stroke_color`) and font fields. `STYLE_VALUE_CHECKS` in `sketch_element.py` holds one value test per style field; colours are `#RGB`, `#RRGGBB` or `#AARRGGBB` strings, and `fill_color=None` means no fill.

### Folder (`models/project/items/folder.py`)

Extends `ItemCollection` — a named container that can hold any item type, enabling nested project organization.

## Project Class (`models/project/project.py`)

```
Project
├── root: ItemCollection        # Top-level container
├── _index: dict[str, Item]     # Flat lookup by ID
├── add_item(item, parent_id?)  # Adds to root or specified parent
├── remove_item(item_id)        # Removes from hierarchy + index
├── find_item(item_id)          # O(1) lookup
└── all_items()                 # Flat iterator over all items
```

## Item Lifecycle Events

| Event | Trigger |
|-------|---------|
| `project.item_added` | Any `add_item()` call |
| `project.item_removed` | Any `remove_item()` call |
| `project.item_renamed` | `RenameItemCommand` execution |
| `dataset.created` | `ImportCsvCommand` / `CreateEmptyDatasetCommand` |
| `chart.created` | `CreateChartFromWizardCommand` |
| `note.created` | Note creation command |
