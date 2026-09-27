# Project Model and Items

## Hierarchy

```
Project (ItemCollection)
└── items: List[Item | ItemCollection]
    ├── Dataset      (wraps pandas.DataFrame)
    ├── Chart        (DataSeries, incl. FIT-type fits + ChartConfiguration)
    ├── Note         (markdown text + tags)
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
├── chart_type: ChartType       # LINE, SCATTER, BAR, HIST, VECTOR, COLORMAP, HEATMAP, 3-D types
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

`Chart.fit_data` is a read-only convenience view that filters `data_series` to its FIT entries.

### Note (`models/project/items/note.py`)

```
Note
├── content: str                # Raw markdown text
└── tags: list[str]             # User-defined tags
```

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
