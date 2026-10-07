# PandaPlot - User Guide

A comprehensive guide to using the PandaPlot application for data visualization, analysis, and project management.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Interface Overview](#interface-overview)
3. [Project Management](#project-management)
4. [Working with Data](#working-with-data)
5. [Creating Plots](#creating-plots)
6. [Data Analysis](#data-analysis)
7. [Data Transformation](#data-transformation)
8. [Customization & Settings](#customization--settings)
9. [Tips & Best Practices](#tips--best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Installation & System Requirements

PandaPlot requires Python 3.12 or newer. Environment and dependencies are managed via `uv`:

```bash
# Clone the repository and navigate to the project directory
cd pandaplot

# Install dependencies and setup environment
uv sync
```

### First Launch

To run PandaPlot, execute the main entry module from the root directory:

```bash
uv run python -m pandaplot.app
```

On first launch, PandaPlot initializes with a clean workspace displaying the Welcome screen. From here, you can create a new project, open a recently saved `.pplot` file, or explore sample datasets.

### Your First Project

1. Click **New Project** on the Welcome tab or select **File > New**.
2. Provide a name for your project.
3. Import a dataset via **Data > Import Data...**.
4. Double-click the imported dataset in the **Project View** panel to open it in a tabular spreadsheet view.
5. Save your project using **File > Save** (`Ctrl+S`).

---

## Interface Overview

PandaPlot features a modern, intuitive PySide6 desktop interface divided into three primary functional areas:

```
┌────────────────────────────────────────────────────────────────────────┐
│ Main Menu Bar (File, Edit, View, Tools, Help)                         │
├──────────────┬─────────────────────────────────────────────────────────┤
│ Collapsible  │ Tabbed Workspace Area                                   │
│ Sidebar      │                                                         │
│ ┌──────────┐ │ ┌─────────────────────────────────────────────────────┐ │
│ │ Icons    │ │ │ Active Tab (Dataset / Chart / Note / Welcome)       │ │
│ │ & Panel  │ │ │                                                     │ │
│ │ View     │ │ │                                                     │ │
│ └──────────┘ │ └─────────────────────────────────────────────────────┘ │
├──────────────┴─────────────────────────────────────────────────────────┤
│ Status Bar                                                             │
└────────────────────────────────────────────────────────────────────────┘
```

### Main Menu Bar
- **File**: Create, open, save, import/export data, and exit.
- **Edit**: Undo (`Ctrl+Z`), Redo (`Ctrl+Y`), and project editing operations.
- **View**: Toggle sidebar visibility, switch theme (Light/Dark), zoom, and layout options.
- **Tools**: Access mathematical analysis, curve fitting, signal analysis, and formula transformation tools.
- **Help**: Open the Welcome tab, examples, and About information.

### Collapsible Sidebar
Located on the left, the sidebar uses icon tabs to switch contextual control panels:
- **Project Tree**: Displays the hierarchical tree of datasets, charts, notes, and folders.
- **Dataset Info**: Shows dimensions, column statistics, and data types for the active dataset.
- **Chart Properties**: Customizes active chart titles, axis labels, gridlines, legends, and series styling.
- **Analysis**: Provides numerical calculus, smoothing, and interpolation controls.
- **Signal Processing**: Provides FFT, peak detection, and filtering options.
- **Curve Fitting**: Interactively configures linear, polynomial, exponential, power, and custom model fits.
- **Transform**: Offers mathematical formula evaluation across dataset columns.

### Tabbed Workspace
The primary workspace displays open documents as tabs:
- **Dataset Tab**: Spreadsheet editor for viewing and editing tabular numeric and string data.
- **Chart Tab**: Matplotlib-powered interactive graphics with real-time preview and export options.
- **Note Tab**: Markdown notebook editor with LaTeX formula rendering support.
- **Welcome Tab**: Quick-start dashboard for recent projects and actions.

### Status Bar
Displays contextual messages, current operation status, background task progress spinners, and active project information.

---

## Project Management

PandaPlot organizes all working assets into self-contained project files (`.pplot`).

### Project Hierarchy & File Format
A `.pplot` file is a ZIP archive containing a project index and files for its items:
- `project.json`: Defines item hierarchy, item types, and paths to item files.
- Dataset items store their tabular data as CSV and metadata as JSON. Metadata includes column IDs, roles, and dtype information used to restore types on load.
- Chart, note, and folder items store their data and settings as JSON files.

### Organizing Items
- **Creating Folders**: Click the **New Folder** button in the Project View toolbar or right-click to add nested subfolders.
- **Renaming Items**: Select an item in the Project View and press `F2`, or right-click and select **Rename**.
- **Deleting Items**: Right-click an item and select **Delete**. All item deletions are fully undoable (`Ctrl+Z`).

### Auto-Save & Session Recovery
PandaPlot supports optional auto-saving and automatic session state preservation across restarts. If enabled in Settings, project changes are automatically flushed to disk upon major operations.

---

## Working with Data

### Data Import
PandaPlot supports multiple data formats:

1. **CSV Import**:
   - Navigate to **Data > Import Data...**.
   - Select CSV parameters (delimiter, header row, encoding) in the preview dialog.
   - Click **Import** to generate a new Dataset item in the project.

2. **Excel Multi-Sheet Import Wizard**:
   - Select **Data > Import Data...**.
   - Browse worksheets, select individual or multiple sheets to import simultaneously.
   - Preview column names, types, and sheet contents before completing import.

### Tabular Spreadsheet Editor
Double-clicking a Dataset opens the spreadsheet view powered by `QTableView`:
- **Cell Editing**: Double-click any cell or press `Enter` to modify values.
- **Adding / Deleting Rows**: Use toolbar buttons to append rows or delete selected rows.
- **Adding / Deleting Columns**: Append new columns with custom names and types, or remove selected columns.
- **Data Types (dtypes)**: Convert columns between integer, floating-point, text, and datetime types via right-click column header context menus.

### Exporting Data
To export a dataset, open it in the Dataset tab and click **Export Data**.

---

## Creating Plots

### Chart Creation Wizard
To create a plot from any dataset:
1. Select a dataset in the Project View or active Dataset tab.
2. Click **New Chart** or select **Tools > Create Plot...**.
3. The **Chart Creation Wizard** guides you through:
   - Choosing plot category and layout.
   - Mapping X and Y axes columns from available datasets.
   - Setting initial plot title and axis labels.

### Supported Series Types
Charts can contain these series types, depending on the chart and selected data:
- **Line**: Connects values in order.
- **Scatter**: Shows individual data points.
- **Bar**: Compares values with bars.
- **Stacked Bar**: Stacks bar values at each X position.
- **Histogram**: Shows the frequency distribution of one values column.
- **Density**: Shows a kernel density estimate for one values column.
- **Box**: Summarizes a distribution with quartiles, median, and outliers.
- **Pie**: Shows values as wedges, with optional category labels.
- **Vector**: Shows two-dimensional vector fields.
- **Color Map**: Colors points by a third data column.
- **Heatmap**: Displays values on a two-dimensional grid.
- **3D Scatter**: Plots data points in three dimensions.
- **3D Line**: Connects data points in three dimensions.
- **3D Surface**: Shows a surface in three dimensions.
- **3D Wireframe**: Shows a wireframe in three dimensions.
- **3D Bar**: Shows values as three-dimensional bars.
- **3D Triangulated Surface**: Shows a triangulated surface in three dimensions.
- **3D Vector**: Shows a three-dimensional vector field.

### Plot Customization & Styling
Open the **Chart Properties** sidebar panel while viewing a plot tab to adjust:
- **Series Style**: Custom colors, line thickness (1-5px), line styles (solid, dashed, dotted), and markers (circle, square, triangle, none).
- **Axes & Labels**: Edit plot title, X-axis label, Y-axis label, and font parameters.
- **Grid & Legend**: Toggle major/minor grid lines and position legends (top-right, top-left, bottom, hidden).
- **Exporting Charts**: Right-click the chart canvas or click **Export Chart** to save publication-quality images in PNG, SVG, or PDF formats.

---

## Data Analysis

PandaPlot includes a powerful scientific computing engine powered by `scipy`, `numpy`, and `statsmodels`.

### Mathematical Operations

Calculations are computed asynchronously in background threads via the `TaskScheduler`. Results are appended as new columns to the target dataset, preserving original raw data.

#### Derivatives
- Calculates numerical derivatives $dy/dx$ using standard second-order central finite differences (`numpy.gradient`).
- Handles unequally spaced $x$-coordinates.

#### Integration
- Computes cumulative numerical integrals $Y(x) = \int_{x_0}^x y(t)\,dt$ using cumulative trapezoidal integration (`scipy.integrate.cumulative_trapezoid`).

#### Smoothing
- Removes noise from experimental data using Savitzky-Golay filtering (`scipy.signal.savgol_filter`).
- Configurable parameters: polynomial order (default: 2 or 3) and window length (odd integer).

#### Interpolation
- Resamples or interpolates datasets to uniform grids or higher resolutions using cubic spline interpolation (`scipy.interpolate.CubicSpline`).

### Curve Fitting
Interactive curve fitting is available through the **Fit Panel** sidebar when viewing a Chart tab:
1. **Model Selection**: Choose from predefined mathematical functions:
   - **Linear**: $y = a \cdot x + b$
   - **Quadratic**: $y = a \cdot x^2 + b \cdot x + c$
   - **Exponential**: $y = a \cdot e^{b \cdot x}$
   - **Power**: $y = a \cdot x^b$
   - **Logarithmic**: $y = a \cdot \ln(x) + b$
   - **Custom Model**: Enter custom mathematical expressions with user-defined parameters.
2. **Execution**: Uses `scipy.optimize.curve_fit` (Levenberg-Marquardt algorithm) to optimize parameter values.
3. **Fit Results**: Displays optimized parameter estimates, standard errors ($\sigma$), covariance matrix, and coefficient of determination ($R^2$).
4. **Overlay**: Real-time overlay of the fitted function curve onto the active chart canvas.

#### Walkthrough: fit a straight line

1. Start PandaPlot and import `examples/fit-test-data/f_x_4.2x_minus_2.3.csv` with **File > Import CSV...**. It has `x` and `f(x)` columns.
2. Open the imported dataset, choose **Create Chart**, and create a **Scatter** or **Line** chart using `x` for X and `f(x)` for Y.
3. With the chart open, select **Curve Fitting** in the sidebar. In **Chart Series**, choose the series, then set **Fit Type** to **Linear (y = ax + b)** and click **Perform Fit**.
4. Read **Fit Results**. The parameter estimates give the fitted values of `a` and `b`; their standard errors show how uncertain those estimates are. **R²** closer to 1 means the fitted line explains more of the variation in the data. A good fit has points close to the line and a high R²; a lower R² or a visible pattern in the residual differences suggests a poor fit or a model that does not describe the data well.
5. To try another equation, set **Fit Type** to **Custom Function**. In **Custom Function**, enter an expression such as `a*x + b` in **Function**, list `a, b` in **Parameters**, and click **Perform Fit**. Use **Define parameters values** to provide starting or fixed values when needed.

### Signal Processing
Access the **Signal Panel** for frequency-domain and peak detection tools:
- **Fast Fourier Transform (FFT)**: Computes real FFT power spectral density distributions.
- **Peak Detection**: Identifies local maxima/minima using height, prominence, and distance thresholds (`scipy.signal.find_peaks`).
- **Filtering**: Applies Butterworth low-pass, high-pass, band-pass, and band-stop digital filters (`scipy.signal.butter` and `filtfilt`).

### Statistical Analysis
View descriptive and inferential statistics for dataset columns:
- **Descriptive Statistics**: Count, mean, standard deviation, minimum, maximum, median, 25%/75% quartiles, skewness, and kurtosis.
- **Statistical Testing**: Normality tests (Shapiro-Wilk, D'Agostino-Pearson) and hypothesis tests ($t$-test, ANOVA).

### Repeated-Measurement Summary
Open a dataset and click **Analyze Measurements**, or right-click a dataset in the **Project View** and select **Analyze Measurements...**, to create grouped statistics for an experiment:
1. Review the suggested **Controlled** (group keys), **Fixed** (constant context), **Measured** (numeric values to summarize), or **Unused** role for each column. Suggestions use column names and observed values, and can be changed before continuing.
2. Review the grouped result and any excluded values, then choose **Finish** to create the output dataset or **Plot a Graph** to create it and continue directly to chart setup.

The output has one row per controlled-value group and measured variable, with the valid count, mean, sample standard deviation, and standard error of the mean. If multiple measured columns are replicates of one quantity (for example, `Velocity1` through `Velocity5`), they receive a shared **Measured variable** suggestion; that name is editable. Rows missing a controlled value are excluded from grouping; missing or non-numeric measured values are excluded only for their own variable. Fixed columns must have one observed value; differing values or a column with no observed values block generation. Missing fixed values are reported when the observed values agree. Column roles and measured-variable group names are saved with the source dataset and follow columns across renames.

---

## Data Transformation

The **Transform Panel** allows creation of derived columns using mathematical formulas evaluated across dataset columns.

### Formula Evaluator
For a column transformation, select a source column and write a Python expression using `x` for that column's values. For example, use `np.sqrt(x)` for square roots, `x.rolling(3).mean()` for a rolling average over three rows, or `pd.to_datetime(x)` to convert values to dates. The Transform panel supplies selected NumPy and pandas names for expressions; this is not a general-purpose Python interface. Column transformations can append a new column or replace the selected column, with Undo/Redo support.

---

## Customization & Settings

Access global preferences from **View > Theme** or **Tools > Settings**:

### Theme Manager
- **Light Theme**: High-contrast, clean aesthetic suitable for daytime work and publication exports.
- **Dark Theme**: Eye-friendly dark mode for low-light environments.
- Theme switching updates Qt application stylesheets and Matplotlib chart color palettes seamlessly without requiring restart.

### Application Configuration
User preferences are stored in `~/.pandaplot/config.json`:
- `theme`: Active theme (`light` or `dark`).
- `window_geometry`: Preserved window size, placement, and tab arrangements.
- `recent_projects`: History list of recently accessed `.pplot` files.
- `auto_save`: Enable/disable background auto-saving on project changes.

---

## Tips & Best Practices

1. **Non-Destructive Workflows**: Analysis operations (derivatives, smoothing, transforms) never overwrite input data unless explicitly requested; they create new columns for easy comparison.
2. **Keyboard Shortcuts**:
   - `Ctrl+S`: Save
   - `Ctrl+Z`: Undo last action
   - `Ctrl+Y`: Redo last action
   - `F2`: Rename selected item
3. **Organizing Projects**: Use Folders in the Project View to group raw data, computed derivatives, and summary charts for complex experiments.

---

## Troubleshooting

### Common Issues and Solutions

1. **Importing CSV Errors (Unparseable standard format)**:
   - *Cause*: Mismatched delimiter (e.g. semicolon vs comma) or multi-line header rows.
   - *Solution*: Adjust delimiter and header row settings in the CSV Import preview dialog.

2. **Curve Fit Fails to Converge**:
   - *Cause*: Poor initial parameter guesses or zero/negative values in logarithmic/power models.
   - *Solution*: Provide realistic initial guesses in the Fit Panel or transform data (e.g. shift $x > 0$).

3. **Chart canvas not updating**:
   - *Cause*: Data series refers to a deleted column or dataset.
   - *Solution*: Open Chart Properties and verify that the active series maps to valid dataset columns.

### Getting Help
1. **Built-in Help**: Access keyboard shortcut guides from the shortcuts listed in this guide.
2. **Tooltips**: Hover over control panel inputs and toolbar buttons for brief usage context.
3. **Documentation**: Refer to `docs/ARCHITECTURE.md` and `docs/USER_GUIDE.md` in the source repository.
4. **Examples**: Explore sample files provided in the `examples/` directory.

### Reporting Issues
When reporting problems, include:
- **Steps to Reproduce**: Detailed steps that led to the issue
- **Data Information**: Description of data being used (file size, format, column types)
- **System Information**: Operating system (Linux/macOS/Windows) and Python version
- **Error Messages**: Complete tracebacks or error dialog details

---

This user guide provides comprehensive coverage of the PandaPlot application. For technical details and extension development, refer to the Architecture documentation and API reference.
