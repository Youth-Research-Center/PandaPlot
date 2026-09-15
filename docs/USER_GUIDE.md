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

1. Click **New Project** on the Welcome tab or select **File > New Project** (`Ctrl+N`).
2. Provide a name for your project.
3. Import a dataset via **File > Import CSV...** or **File > Import Excel...**.
4. Double-click the imported dataset in the **Project View** panel to open it in a tabular spreadsheet view.
5. Save your project using **File > Save Project** (`Ctrl+S`).

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
- **Help**: Access user documentation, keyboard shortcut reference, and about dialog.

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
A `.pplot` file is a ZIP archive containing structured JSON and Parquet metadata:
- `project.json`: Defines item hierarchy, UUID relationships, and folder organization.
- `dataset_{id}.parquet`: High-performance binary storage for dataset DataFrames preserving exact data types.
- `chart_{id}.json`: Serialization of chart parameters, styling, data series references, and fit parameters.
- `note_{id}.json`: Markdown text and tag metadata.
- `folder_{id}.json`: Folder organization metadata.

### Organizing Items
- **Creating Folders**: Click the **New Folder** button in the Project View toolbar or right-click to add nested subfolders.
- **Renaming Items**: Select an item in the Project View and press `F2`, or right-click and select **Rename**.
- **Deleting Items**: Select an item and press `Delete`, or right-click and select **Delete**. All item deletions are fully undoable (`Ctrl+Z`).

### Auto-Save & Session Recovery
PandaPlot supports optional auto-saving and automatic session state preservation across restarts. If enabled in Settings, project changes are automatically flushed to disk upon major operations.

---

## Working with Data

### Data Import
PandaPlot supports multiple data formats:

1. **CSV Import**:
   - Navigate to **File > Import CSV...** (`Ctrl+I`).
   - Select CSV parameters (delimiter, header row, encoding) in the preview dialog.
   - Click **Import** to generate a new Dataset item in the project.

2. **Excel Multi-Sheet Import Wizard**:
   - Select **File > Import Excel...**.
   - Browse worksheets, select individual or multiple sheets to import simultaneously.
   - Preview column names, types, and sheet contents before completing import.

### Tabular Spreadsheet Editor
Double-clicking a Dataset opens the spreadsheet view powered by `QTableView`:
- **Cell Editing**: Double-click any cell or press `Enter` to modify values.
- **Adding / Deleting Rows**: Use toolbar buttons to append rows or delete selected rows.
- **Adding / Deleting Columns**: Append new columns with custom names and types, or remove selected columns.
- **Data Types (dtypes)**: Convert columns between integer, floating-point, text, and datetime types via right-click column header context menus.

### Exporting Data
Datasets can be exported at any time via **File > Export Dataset...** to standard `.csv` files or Microsoft Excel `.xlsx` workbooks.

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

### Supported Chart Types
- **Line Plot**: Visualizes continuous series data over time or continuous variables.
- **Scatter Plot**: Displays individual data points for correlation analysis.
- **Bar Chart**: Shows categorical value comparisons.
- **Histogram**: Visualizes probability distributions and data frequency.
- **Box Plot**: Summarizes five-number statistical distributions (median, quartiles, outliers).
- **Violin Plot**: Displays kernel density estimations along with box plot statistical metrics.

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

### Signal Processing
Access the **Signal Panel** for frequency-domain and peak detection tools:
- **Fast Fourier Transform (FFT)**: Computes real FFT power spectral density distributions.
- **Peak Detection**: Identifies local maxima/minima using height, prominence, and distance thresholds (`scipy.signal.find_peaks`).
- **Filtering**: Applies Butterworth low-pass, high-pass, band-pass, and band-stop digital filters (`scipy.signal.butter` and `filtfilt`).

### Statistical Analysis
View descriptive and inferential statistics for dataset columns:
- **Descriptive Statistics**: Count, mean, standard deviation, minimum, maximum, median, 25%/75% quartiles, skewness, and kurtosis.
- **Statistical Testing**: Normality tests (Shapiro-Wilk, D'Agostino-Pearson) and hypothesis tests ($t$-test, ANOVA).

---

## Data Transformation

The **Transform Panel** allows creation of derived columns using mathematical formulas evaluated across dataset columns.

### Formula Evaluator
Transformations use safe vectorized evaluation via `pandas.eval`:
- Reference existing columns by name: `Velocity = df['Distance'] / df['Time']`
- Supported mathematical operators: `+`, `-`, `*`, `/`, `**` (exponentiation), `%` (modulo)
- Supported functions: `sin`, `cos`, `tan`, `exp`, `log`, `sqrt`, `abs`
- Column transformations append new columns or replace existing columns in place with full Undo/Redo support.

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
   - `Ctrl+N`: New Project
   - `Ctrl+O`: Open Project
   - `Ctrl+S`: Save Project
   - `Ctrl+I`: Import CSV
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
1. **Built-in Help**: Access keyboard shortcut guides from **Help > Shortcuts**.
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
