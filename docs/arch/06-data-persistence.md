# Data Persistence

## File Format

Projects are stored as `.pplot` files, which are standard ZIP archives:

```
project.pplot  (ZIP)
├── project.json              # Project hierarchy and item metadata
├── chart_{id}.json           # One file per Chart item
├── dataset_{id}.parquet      # One file per Dataset (columnar, compressed)
├── note_{id}.json            # One file per Note item
└── folder_{id}.json          # One file per Folder item
```

Datasets are stored as Parquet (via PyArrow) because it preserves dtypes and is compact for numeric data. The format falls back to HDF5 for datasets that cannot be represented in Parquet.

## Storage Layer Classes (`storage/`)

### ProjectDataManager

Top-level coordinator for save and load operations.

```
ProjectDataManager
├── save(project, filepath)
│   ├── Open/create ZIP at filepath
│   ├── Serialize project.json (item IDs, names, hierarchy, timestamps)
│   └── For each item: delegate to ItemDataManagerFactory
└── load(filepath)
    ├── Open ZIP at filepath
    ├── Parse project.json → item hierarchy skeleton
    └── For each item: reconstruct via ItemDataManagerFactory
```

### ItemDataManagerFactory

Selects the correct per-type manager based on `item.item_type`:

| Item Type | Manager |
|-----------|---------|
| `Dataset` | `DatasetDataManager` |
| `Chart` | `ChartDataManager` |
| `Note` | `NoteDataManager` |
| `Folder` | `FolderDataManager` |
| `Sketch` | `SketchDataManager` |

### Per-Type Managers

**DatasetDataManager**
- `save(zip_file, dataset)` → writes `dataset_{id}.parquet` into ZIP
- `load(zip_file, item_meta)` → reads Parquet → constructs `Dataset` with DataFrame

**ChartDataManager**
- `save(zip_file, chart)` → serializes chart JSON (type, config, series refs, fit data)
- `load(zip_file, item_meta)` → reconstructs `Chart` from JSON

**SketchDataManager**
- `save(sketch, zip_file, path_in_zip)` → writes the whole sketch (layers and elements) as one `{path_in_zip}.json`
- `load(...)` → runs `migrate_sketch()` (`models/migrations/per_item/sketch.py`) on the raw dict, then `Sketch.from_dict()`
- Sketches were added at `schema_version` 5, which also keeps older builds from opening projects that contain them

**NoteDataManager / FolderDataManager**
- Simple JSON serialization of their respective fields

## project.json Structure

```json
{
  "id": "uuid",
  "name": "My Project",
  "created_at": "2025-01-01T00:00:00",
  "updated_at": "2025-01-01T12:00:00",
  "items": [
    {
      "id": "uuid",
      "item_type": "dataset",
      "name": "measurements.csv",
      "parent_id": null
    },
    {
      "id": "uuid",
      "item_type": "chart",
      "name": "Velocity vs Time",
      "parent_id": null
    },
    {
      "id": "uuid",
      "item_type": "folder",
      "name": "Raw Data",
      "parent_id": null
    }
  ]
}
```

`parent_id: null` means the item is a direct child of the root collection. A non-null `parent_id` places the item inside a Folder.

## Application Configuration

Separate from project files, user preferences are stored in:

```
~/.pandaplot/config.json
```

Managed by `ConfigManager` (`services/config/`):

| Setting | Description |
|---------|-------------|
| `theme` | `"light"` or `"dark"` |
| `window_geometry` | Saved window size and position |
| `recent_projects` | List of recently opened file paths |
| `auto_save` | Boolean — save on every command execution |

`ConfigManager` emits `ConfigEvents` on load, update, and save, so other services (e.g. `ThemeManager`) can react to configuration changes.

### Config Resilience

- A `.json.bak` backup is written before each save
- On load failure, `ConfigManager` falls back to defaults and logs the error
- Validation rules guard against corrupt or out-of-range values
