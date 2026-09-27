# Analysis Engine and Curve Fitting

## Analysis Engine (`analysis/analysis_engine.py`)

`AnalysisEngine` provides mathematical operations on dataset columns using scipy. All operations take column data as NumPy arrays and return an `AnalysisResult` containing the computed values and metadata.

### Supported Operations

| Operation | Algorithm | scipy API |
|-----------|-----------|-----------|
| Derivative | Finite differences | `numpy.gradient` |
| Integral | Cumulative trapezoid | `scipy.integrate.cumulative_trapezoid` |
| Smoothing | Savitzky-Golay filter | `scipy.signal.savgol_filter` |
| Interpolation | Cubic spline | `scipy.interpolate.CubicSpline` |

### AnalysisResult

```
AnalysisResult
├── values: np.ndarray       # Computed output column
├── operation: str           # Human-readable operation name
├── input_columns: list[str] # Source columns used
├── parameters: dict         # Operation parameters (window size, etc.)
└── statistics: dict         # Min, max, mean, std of result
```

### AnalysisCommand Integration

`AnalysisCommand.execute()`:
1. Retrieves x and y columns from the target Dataset as NumPy arrays
2. Calls the appropriate `AnalysisEngine` method
3. Appends the result as a new column to the DataFrame
4. Emits `AnalysisEvents.ANALYSIS_COMPLETED` and `DatasetOperationEvents.DATASET_COLUMN_ADDED`

The original columns are unchanged. Undo removes the added column.

## Curve Fitting (`services/fit/`)

### FitService

Wraps `scipy.optimize.curve_fit` with predefined model functions:

| Fit Type | Function | Parameters |
|----------|----------|-----------|
| `LINEAR` | `a·x + b` | a, b |
| `QUADRATIC` | `a·x² + b·x + c` | a, b, c |
| `EXPONENTIAL` | `a·e^(b·x)` | a, b |
| `POWER` | `a·x^b` | a, b |
| `LOGARITHMIC` | `a·ln(x) + b` | a, b |
| `CUSTOM` | User-supplied expression | variable |

```
FitService.perform_fit(chart, series_index, fit_config)
├── Extract x, y from Dataset columns referenced by DataSeries
├── Select model function by FitType
├── scipy.optimize.curve_fit(func, x, y, p0=initial_guess)
│   → popt (parameters), pcov (covariance matrix)
├── Compute standard errors: sqrt(diag(pcov))
├── Compute R²: 1 - SS_res / SS_tot
└── Return FitResult(x_fit, y_fit, parameters, errors, r_squared, fit_type)
```

A fit is stored as a `SeriesType.FIT` `DataSeries` (folded into `chart.data_series` alongside every other series type, #304), not a separate model -- `chart.fit_data` is a read-only, filtered view over `data_series` for callers that only need "the fits". Its curve is a one-time snapshot in `precomputed_x_data`/`precomputed_y_data` rather than a live column reference, and its fit-only metadata (`fit_type`/`fit_params`/`fit_stats`/confidence band) lives on `DataSeries.style` (a `FitStyle`).

### Fit Rendering

`ChartTab` → `ChartRenderEngine` dispatches a FIT-type series through the same `SERIES_RENDERERS` table as every other series type (`series_renderers/fit.py`):
1. Plot `precomputed_x_data`/`precomputed_y_data` as a dashed line
2. Overlay the confidence band, if configured
3. Display equation and R² in the chart legend

### ApplyFitCommand

```
ApplyFitCommand.execute()
├── FitService.perform_fit(...)
├── chart.add_fit_series(x_data=x_fit, y_data=y_fit, style=FitStyle(...))
└── EventBus.emit(ChartEvents.CHART_UPDATED, {"chart_id": ..., "update_type": "fit_added"})

ApplyFitCommand.undo()
├── chart.remove_data_series(added_index)
└── EventBus.emit(ChartEvents.CHART_UPDATED, {"chart_id": ..., "update_type": "fit_removed"})
```

## TransformColumnCommand (`commands/project/dataset/`)

Separate from `AnalysisCommand`, this command evaluates arbitrary user-supplied formulas over existing columns:

```python
# Example: create velocity column from position and time
formula = "df['position'].diff() / df['time'].diff()"
TransformColumnCommand(dataset_id, new_col_name="velocity", formula=formula)
```

The formula is evaluated with `pandas.eval()` or `python eval()` in a restricted namespace containing only the current DataFrame as `df`. Result is appended as a new column.
