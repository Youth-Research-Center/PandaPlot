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
│ Main Menu Bar (File, Edit, Data, Chart, Settings, Help)               │
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
- **File**: Create, open, close and save projects (New, Open, Recent, Close, Save, Save As...), and exit.
- **Edit**: Undo (`Ctrl+Z`) and Redo (`Ctrl+Y`).
- **Data**: Import data and images, add a dataset, add rows or columns, and create new notes and sketches.
- **Chart**: **Create New** opens the Chart Creation Wizard.
- **Settings**: **Preferences...** opens the settings dialog, including the theme.
- **Help**: Open Help Topics (`F1`), the Welcome tab, the example project, and About information.

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
- **Chart Tab**: Matplotlib-powered interactive graphics with real-time preview and a toolbar for zooming, panning and saving the chart as an image.
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
2. Open the wizard with **Chart > Create New**, the **Create Chart** button on a dataset tab (columns selected in the table are filled in for you), or right-click a dataset in the Project View and choose **Create Chart**. The Welcome tab's **4. Create Visualizations** button also leads to **Create Chart**.
3. The **Chart Creation Wizard** guides you through three steps (**Type**, **Data**, **Labels**):
   - Choosing the chart type: pick a category (Line & Scatter, Bar & Pie, Distribution, Fields & Grids or 3-D) from the dropdown, then a type from that category's list. The chart's **Category** and **Type** selectors in the properties panel work the same way.
   - Choosing the dataset and columns for each series (use **+ Add series** for more than one).
   - Setting the title, subtitle and axis labels, and turning the legend and grid lines on or off.
4. Click **Create Chart**. The chart opens in its own tab.

Each wizard step has a **?** button at the bottom left, and `F1` does the same: both open the Help window on that step. The Help window stays usable while the wizard is open.

### Supported Series Types
Charts can contain these series types, depending on the chart and selected data:
- **Line**: Connects values in order.
- **Scatter**: Shows individual data points.
- **Bar**: Compares values with bars. Bar series that share X values are drawn on top of each other; use Stacked Bar to compare groups.
- **Stacked Bar**: Stacks bar values at each X position.
- **Histogram**: Shows the frequency distribution of one values column.
- **Density**: Shows a kernel density estimate for one values column.
- **Box**: Summarizes a distribution with quartiles, median, and outliers.
- **Pie**: Shows values as wedges, with optional category labels.
- **Vector**: Shows two-dimensional vector fields. Arrows are coloured by the Color-by column only when you choose a colormap under **Color by magnitude:** on the Style tab.
- **Color Map**: Colors points by a third data column.
- **Heatmap**: Displays values on a two-dimensional grid.
- **3D Scatter**: Plots data points in three dimensions.
- **3D Line**: Connects data points in three dimensions.
- **3D Surface**: Shows a surface in three dimensions.
- **3D Wireframe**: Shows a wireframe in three dimensions.
- **3D Bar**: Shows values as three-dimensional bars.
- **3D Triangulated Surface**: Shows a triangulated surface in three dimensions.
- **3D Vector**: Shows a three-dimensional vector field. Colouring by the Color-by column also needs a colormap under **Color by magnitude:** on the Style tab.

### Plot Customization & Styling
Click the line-chart icon in the sidebar (tooltip "Chart Properties panel") while viewing a chart tab. Its tabs are:
- **Chart**: Title, subtitle, category, chart type and, for histograms, the number of bins.
- **Data**: The chart's series. Add, remove, reorder and configure them, including their dataset and columns.
- **Style**: Fonts, colors, backgrounds, and the look of the chart and its series. Choose **Chart** in the drop-down at the top for the chart's **Size** and **DPI**.
- **Axes**: Each axis's label, range, scale, ticks and grid.
- **Legend**: Show or hide the legend and set its position, font and background.

Edits on the Chart, Style, Axes and Legend tabs appear on the chart immediately. The footer at the bottom of the panel shows **Modified** once you have edited something: click **Apply** to keep the changes as one undo step (**Edit > Undo**), or **Revert** to go back to how the chart was when you opened it or last applied. Edits to a series' dataset, columns, label or Y axis on the Data tab only mark the panel **Modified** and show on the chart when you click **Apply**. Apply or Revert before switching to any other tab (a dataset or note tab as well); otherwise the changes can no longer be reverted and have no undo step. Adding, removing and reordering series on the Data tab take effect at once, and each is its own undo step. **+ Add series** copies the selected series, so a chart with no series cannot get its first series there: create the chart with the wizard.

### Saving a Chart as an Image
Click the **Save** button (floppy-disk icon, tooltip "Save the figure") in the toolbar above the chart and choose a file name and format such as PNG, PDF or SVG. To set the picture size and sharpness first, use the **Size** and **DPI** cards on the Style tab (with **Chart** selected in the drop-down).

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
1. **Model Selection**: Choose a model category, then select a fit:
   - **Polynomial**: Linear, quadratic, cubic, quartic, and quintic.
   - **Exponential**: General exponential, exponential decay, and growth to a maximum.
   - **Sigmoid**: Logistic sigmoid.
   - **Peak**: Gaussian and Lorentzian peaks.
   - **Periodic**: Sine, cosine and damped sine, $y = a \cdot \sin(b \cdot x + c) + d$ (b is the angular frequency).
   - **Power & Logarithmic**: Power and logarithmic.
   - **Custom**: Enter a mathematical expression with user-defined parameters.
2. **Execution**: Uses `scipy.optimize.curve_fit` to optimize model parameters. Models with constraints use bounded least squares.
3. **Fit Results**: Displays optimized parameter estimates, standard errors ($\sigma$), covariance matrix, and coefficient of determination ($R^2$).
4. **Overlay**: Real-time overlay of the fitted function curve onto the active chart canvas.

#### Walkthrough: fit a straight line

1. Start PandaPlot and import `examples/fit-test-data/f_x_4.2x_minus_2.3.csv` with **File > Import CSV...**. It has `x` and `f(x)` columns.
2. Open the imported dataset, choose **Create Chart**, and create a **Scatter** or **Line** chart using `x` for X and `f(x)` for Y.
3. With the chart open, select **Curve Fitting** in the sidebar. In **Chart Series**, choose the series, select **Polynomial** as the category and **Linear (y = ax + b)** as the model, then click **Perform Fit**.
4. Read **Fit Results**. The parameter estimates give the fitted values of `a` and `b`; their standard errors show how uncertain those estimates are. **R²** closer to 1 means the fitted line explains more of the variation in the data. A good fit has points close to the line and a high R²; a lower R² or a visible pattern in the residual differences suggests a poor fit or a model that does not describe the data well.
5. To try another equation, set **Category** to **Custom** and **Model** to **Custom Function**. In **Custom Function**, enter an expression such as `a*x + b` in **Function**, list `a, b` in **Parameters**, and click **Perform Fit**. Use **Define parameters values** to provide fixed values when needed.

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

### Formula Columns
Check **Save as formula column** to keep the expression on the new column. The data table marks such a column with `fx` in its header, and hovering the header shows the expression. By default the values stay as computed until you run the transform again.

Also check **Live** to keep the column up to date automatically (`fx live`). Whenever a source column changes — by editing a cell, pasting, adding or removing rows, or Undo/Redo — the live column is recomputed, and so are any live columns built on it. A live column is **read-only**: you cannot type, paste, preprocess, change the type of, or write analysis results into it. To change them, edit a source column, or run the transform again without **Live** to turn the column back into ordinary data.

Formulas refer to their source columns by the names they had when the formula was created, so renaming a source column does not break a formula column. A formula that would depend on itself, directly or through other formula columns, is rejected. Formula expressions may only use arithmetic, NumPy and pandas; file access and Python internals are not available.

---

## Customization & Settings

Access global preferences from **Settings > Preferences...** (the theme is under **Theme and Colors**):

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
1. **Help Topics**: Choose **Help → Help Topics...** (`F1`; `Cmd+?` on macOS) to open the Help window. Type in the search field to filter topics, pick one from the list on the left, and follow the **Related topics** links at the bottom of each page. Topics cover every statistical test, descriptive statistics, preprocessing, the analysis operations (derivatives, integrals, smoothing, interpolation), signal analysis, every curve-fitting model, transforms and formulas, the Analyze Measurements wizard, and charts (how-to topics such as creating a chart, series, styling, axes, legend, error bars and saving an image, plus a topic for every chart type, in the **Charts** category). The window stays open while you work, and you can still use it while a dialog such as the chart wizard is open.
2. **Panel help buttons**: The analysis panels in the sidebar (Transform, Preprocessing, Analysis, Descriptive Statistics, Statistical Tests, Signal Analysis, Curve Fitting, Chart Analysis, Chart Signal Analysis, Chart Transform and Chart Properties) have a **?** button next to their title that opens the Help window on step-by-step instructions for that panel.
3. **Chart wizard help**: Every step of the Chart Creation Wizard has a **?** button at the bottom left, and `F1` opens help for the current step.
4. **Tooltips**: Hover over control panel inputs and toolbar buttons for brief usage context.
5. **Documentation**: Refer to `docs/ARCHITECTURE.md` and `docs/USER_GUIDE.md` in the source repository.
6. **Examples**: Explore sample files provided in the `examples/` directory.

### Reporting Issues
When reporting problems, include:
- **Steps to Reproduce**: Detailed steps that led to the issue
- **Data Information**: Description of data being used (file size, format, column types)
- **System Information**: Operating system (Linux/macOS/Windows) and Python version
- **Error Messages**: Complete tracebacks or error dialog details

---

This user guide provides comprehensive coverage of the PandaPlot application. For technical details and extension development, refer to the Architecture documentation and API reference.
