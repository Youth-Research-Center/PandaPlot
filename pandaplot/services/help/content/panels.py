"""Help topics for the analysis sidebar panels.

One "how to use this panel" topic per panel that has a "?" button. The steps
follow the panel's on-screen labels and buttons; the related links point at the
operation topics the panel offers.
"""

from pandaplot.analysis.preprocessing_types import PreprocessingMethod
from pandaplot.analysis.signal.signal_types import SignalAnalysisType
from pandaplot.analysis.stats_types import StatTestType
from pandaplot.models.chart.chart_type_spec import CHART_TYPE_SPECS
from pandaplot.services.help.content.panel_defaults import (
    DESCRIPTIVE_SIGNIFICANT_DIGITS,
    FIT_POINTS,
    SAMPLING_RATE_DATASET,
    SIGNIFICANCE_ALPHA,
)
from pandaplot.services.help.help_types import (
    FIT_TOPIC_CUSTOM,
    FIT_TOPIC_OVERVIEW,
    PANEL_TOPIC_ANALYSIS,
    PANEL_TOPIC_CHART_ANALYSIS,
    PANEL_TOPIC_CHART_SIGNAL,
    PANEL_TOPIC_CHART_TRANSFORM,
    PANEL_TOPIC_DESCRIPTIVE,
    PANEL_TOPIC_FIT,
    PANEL_TOPIC_PREPROCESSING,
    PANEL_TOPIC_SIGNAL,
    PANEL_TOPIC_STATISTICS,
    PANEL_TOPIC_TRANSFORM,
    HelpCategory,
    HelpTopic,
)

_ANALYSIS_RELATED: tuple[str, ...] = (
    "analysis.derivative",
    "analysis.integral",
    "analysis.arc_length",
    "analysis.smoothing",
    "analysis.interpolation",
)
_STATS_RELATED: tuple[str, ...] = tuple(f"stats.{test_type.value}" for test_type in StatTestType)
_PREPROCESSING_RELATED: tuple[str, ...] = tuple(f"preprocessing.{method.value}" for method in PreprocessingMethod)
_SIGNAL_RELATED: tuple[str, ...] = tuple(f"signal.{analysis_type.value}" for analysis_type in SignalAnalysisType)
_NO_FIT_CHART_TYPES: str = ", ".join(spec.display_name for spec in CHART_TYPE_SPECS.values() if not spec.allows_fit)


def topics() -> list[HelpTopic]:
    """Return the help topics of this module.

    Returns:
        The topics, in display order.
    """
    return [
        HelpTopic(
            id=PANEL_TOPIC_TRANSFORM,
            title="Transform panel",
            category=HelpCategory.PANELS,
            summary="Create a new column from a dataset column by writing a short expression, such as x * 2 or np.sqrt(x).",
            steps=(
                'Open a dataset tab and click the 🔧 icon in the sidebar (its tooltip reads "Transform Operations panel").',
                "Check the Active Dataset box at the top shows the dataset you want to work on.",
                ("Under Column Selection, click a column in Source Columns. If you select several, only the first one is used as x; "
                'the list marks it with "→ x" and the others with "(not used)".'),
                "Type a name in New Column. PandaPlot suggests <column>_transformed for you.",
                ('Under Transform Function, type an expression, or choose a ready-made one from "ƒ  Insert function ▾". '
                "Click the ? button to see the names you can use."),
                'Optional: tick "Replace existing column" to overwrite a column that already has the new name.',
                ('Optional: tick "Save as formula column" to remember the expression on the new column. '
                'Then "Live (recompute when sources change)" appears; tick it if the column should update by itself.'),
                "Click Preview to see sample results. Use the rows list next to it to show 5, 10 or 20 rows.",
                ("Click Apply. The new column is added to the dataset and the panel is cleared. "
                "Apply stays greyed out until a source column, a new column name and an expression are filled in."),
            ),
            explanation=(
                "The Type list (Custom Function, Math Operations, String Operations, Date/Time Operations, Statistical Operations) "
                "only changes the example text shown in the function box. It does not change how your expression is calculated.\n\n"
                "Clear resets every field in the panel. You can undo a transform with Edit > Undo."
            ),
            keywords=("transform", "new column", "formula", "expression", "calculate column", "derived column", "function"),
            related=(
                "transforms.panel",
                "transforms.expressions",
                "transforms.names",
                "transforms.formula_columns",
                PANEL_TOPIC_CHART_TRANSFORM,
            ),
        ),
        HelpTopic(
            id=PANEL_TOPIC_PREPROCESSING,
            title="Preprocessing panel",
            category=HelpCategory.PANELS,
            summary="Rescale one or more numeric columns, for example to compare columns measured in different units.",
            steps=(
                'Open a dataset tab and click the ⚖️ icon in the sidebar (its tooltip reads "Preprocessing panel").',
                "Under Transformation, choose a Method. A short description and its formula appear below the list.",
                "Under Columns, select one or more numeric columns (Ctrl-click or Shift-click for several).",
                ('For "Min-Max scale" only, set Output min and Output max under Parameters (0 and 1 by default). '
                "Output max must be greater than Output min."),
                ('Under Result, tick "Replace source columns in place" to overwrite the selected columns. '
                "Otherwise new columns are added, named after the source column and the method (for example price_zscore). "
                "The line under the checkbox shows the names that will be used."),
                "Click Preview to see the result without changing the dataset.",
                "Click Apply to write the result into the dataset.",
            ),
            explanation=(
                "Clear deselects the columns, switches the method back to the first one and empties the preview. "
                "Preprocessing can be undone with Edit > Undo."
            ),
            keywords=("preprocessing", "normalize", "normalise", "scale", "rescale", "standardize", "z-score"),
            related=_PREPROCESSING_RELATED,
        ),
        HelpTopic(
            id=PANEL_TOPIC_ANALYSIS,
            title="Analysis Operations panel (dataset)",
            category=HelpCategory.PANELS,
            summary="Calculate a derivative, integral, arc length, smoothed values or interpolated values from two columns and store the result as a new column.",
            steps=(
                'Open a dataset tab and click the 📊 icon in the sidebar (its tooltip reads "Analysis Operations panel").',
                "Under Analysis Type, choose Derivative, Integral, Arc Length, Smoothing or Interpolation.",
                ("Under Column Selection, choose the X Column and the Y Column. Both must be numeric. "
                "The first two columns of the dataset are selected by default."),
                ("Under Parameters, set the options for the chosen operation (for example Method, Window Length or Points). "
                "Integral and Arc Length have a fixed method and no options."),
                ("Under Data Range, set Start Row and End Row to analyze only part of the data. Rows are numbered like the rows in the table, "
                "starting at 1, and both ends are included. Next to each box the X and Y values at that row are shown."),
                ("Under Result Configuration, type the Result Column name. It is filled in as <Y column>_<operation>; change it if you like. "
                'Tick "Replace if exists" to overwrite a column with the same name.'),
                "Click Preview to see the number of result points and summary statistics.",
                "Click Apply. The calculation runs in the background and the new column is added to the dataset.",
            ),
            explanation=(
                "For Derivative, Integral, Arc Length and Smoothing, rows outside the Data Range are left empty in the new column.\n\n"
                "Interpolation works differently. Its Y values belong to new, evenly spaced X positions, so they are written into the new column "
                "from the first row of the dataset downwards, whatever the Data Range is, and any rows below them stay empty. "
                "Points must not be larger than the number of rows in the dataset, otherwise Apply fails.\n\n"
                "Clear empties the Result Column name, unticks Replace if exists, resets the Data Range to the whole dataset, "
                "empties the preview and sets the Analysis Type back to Derivative. The Parameters keep their values."
            ),
            keywords=("analysis", "derivative", "integral", "smoothing", "interpolation", "arc length", "new column"),
            related=(*_ANALYSIS_RELATED, PANEL_TOPIC_CHART_ANALYSIS),
        ),
        HelpTopic(
            id=PANEL_TOPIC_DESCRIPTIVE,
            title="Descriptive Statistics panel",
            category=HelpCategory.PANELS,
            summary="Summarize one or more numeric columns with statistics such as the mean, median and standard deviation.",
            steps=(
                'Open a dataset tab and click the 📋 icon in the sidebar (its tooltip reads "Descriptive Statistics panel").',
                'Under Columns, select one or more numeric columns (Ctrl-click or Shift-click). "Select all" selects every column.',
                f"Under Options, set Significant digits ({DESCRIPTIVE_SIGNIFICANT_DIGITS.default} by default).",
                'Under Options, leave "Also add a written report (note)" ticked if you want a note with the results, or untick it.',
                "Click Compute to preview the statistics in the Results box. Nothing is added to the project yet.",
                "Click Add to Project to save the results as a new dataset in the project, plus the written report if it is ticked.",
            ),
            explanation="Clear empties the preview. Adding results to the project can be undone with Edit > Undo.",
            keywords=("descriptive", "summary statistics", "mean", "median", "standard deviation", "describe"),
            related=("descriptive.overview",),
        ),
        HelpTopic(
            id=PANEL_TOPIC_STATISTICS,
            title="Statistical Tests panel",
            category=HelpCategory.PANELS,
            summary="Run a hypothesis test on columns of a dataset and read the p-value, with a plain-language explanation of each test.",
            steps=(
                'Open a dataset tab and click the 🧪 icon in the sidebar (its tooltip reads "Statistical Tests panel").',
                ("Under Test, choose a test. Its description and assumptions appear below. "
                "Click the ℹ️ button for a longer explanation, the formula and an example."),
                ("Under Data Selection, choose the data. Depending on the test this is one Sample column, "
                "Column A and Column B (they must be different columns), or a list of Groups where you select two or more columns."),
                (f"Under Parameters, set Significance (α), {SIGNIFICANCE_ALPHA.default} by default. Some tests also show Expected mean (μ₀), "
                'Alternative (two-sided, less or greater) or "Assume equal variance (uncheck for Welch)".'),
                "Click Run to see the result in the Results box. Nothing is added to the project yet.",
                "Click Add to Project to save the results as a new dataset in the project.",
            ),
            explanation="Clear empties the Results box. Adding results to the project can be undone with Edit > Undo.",
            keywords=("statistics", "hypothesis test", "p-value", "significance", "t-test", "anova", "correlation"),
            related=_STATS_RELATED,
        ),
        HelpTopic(
            id=PANEL_TOPIC_SIGNAL,
            title="Signal Analysis panel (dataset)",
            category=HelpCategory.PANELS,
            summary="Analyze a numeric column as a signal, for example to find its frequencies or its peaks.",
            steps=(
                'Open a dataset tab and click the 📡 icon in the sidebar (its tooltip reads "Signal Analysis panel").',
                "Under Analysis, choose a Method. A short description appears below it.",
                "Under Input, choose the Signal column. Only numeric columns are listed.",
                ("Under Parameters, set the options the method offers. Depending on the method these can be "
                "Sampling rate, FFT size, Window, Segment size, Overlap, Minimum height, Minimum distance, Prominence and Threshold."),
                "Click Run. The calculation runs in the background and a summary appears in the Results box.",
                "Click Add to Project to save the full result as a new dataset in the project.",
            ),
            explanation=(
                f"The sampling rate is how many samples were recorded per unit of time. It is set to {SAMPLING_RATE_DATASET.default} by default, "
                "so change it to match your data.\n\n"
                "Clear empties the Results box."
            ),
            keywords=("signal", "fft", "frequency", "spectrum", "peaks", "psd", "autocorrelation"),
            related=(*_SIGNAL_RELATED, PANEL_TOPIC_CHART_SIGNAL),
        ),
        HelpTopic(
            id=PANEL_TOPIC_FIT,
            title="Curve Fitting panel",
            category=HelpCategory.PANELS,
            summary="Fit a mathematical model to a series on the current chart and add the fitted curve to the chart.",
            steps=(
                'Open a chart tab and click the 📐 icon in the sidebar (its tooltip reads "Curve Fitting panel").',
                ('Under Data Source, choose a series in Chart Series. Choose "Custom..." to pick any Dataset, X Column and Y Column in the project instead. '
                "Data Points shows how many points will be used."),
                "Under Fit Configuration, choose a Category and then a Model.",
                ("For the custom function, enter the Function (for example a*x**2 + b*x + c) and list its Parameters (for example a, b, c). "
                'The Functions button inserts function names. In "Define parameters values" you can give some parameters a fixed value (for example b=2.1, c=1); '
                "those are held constant and the others are fitted."),
                f"Set Fit Points, the number of points used to draw the curve ({FIT_POINTS.default} by default).",
                'Tick "Show Confidence Bands" if you want a band around the curve. "Calculate R²" is ticked by default.',
                ("Fit Range is Auto by default and uses the range of the data. Untick Auto to type a Min and a Max, for example to extend the curve past your data. "
                "Max must be greater than Min."),
                "Click Perform Fit. The parameters, their errors and the equation appear in Fit Results and under Equation.",
                "Click Apply to add the fitted curve to the chart. A report note and a dataset of the fitted values are also added to the project.",
            ),
            explanation=(
                f"Apply is only available after a fit has been performed. On charts that cannot show a fit ({_NO_FIT_CHART_TYPES}) "
                "both Perform Fit and Apply are greyed out and the panel says that curve fits are not available there.\n\n"
                "Clear Results discards the current fit without changing the chart."
            ),
            keywords=("fit", "curve fitting", "regression", "model", "trendline", "best fit"),
            related=(FIT_TOPIC_OVERVIEW, FIT_TOPIC_CUSTOM),
        ),
        HelpTopic(
            id=PANEL_TOPIC_CHART_ANALYSIS,
            title="Chart Analysis panel",
            category=HelpCategory.PANELS,
            summary="Calculate a derivative, integral, arc length, smoothed curve or interpolated curve for a series of the current chart.",
            steps=(
                'Open a chart tab and click the 🧮 icon in the sidebar (its tooltip reads "Chart Analysis panel").',
                "Under Series, choose what to Analyze: a data series or a fitted curve of this chart.",
                "Under Operation, choose the Type: Derivative, Integral, Arc length (line length), Smoothing or Interpolation.",
                ("Under Parameters, set the options for the chosen operation (for example Method, Window length or Points). "
                "Integral and Arc length have a fixed method and no options."),
                ("Under Segment (index range), set Start index and End index to analyze only part of the series. The first point is index 0 and both ends are included. "
                "Next to each box the x and y values at that point are shown."),
                ("Under Result, type a Dataset name or leave it empty to use the suggested name. "
                'Keep "Plot result" ticked to draw the result, and choose in "Plot on:" whether it goes on a new chart or an existing one.'),
                "Click Preview to see how many points the result has and the first values.",
                'Click Apply. A new dataset with the X values and the result is added to the project, and plotted if "Plot result" is ticked.',
            ),
            explanation="Clear empties the dataset name, resets the segment and the operation, and clears the preview.",
            keywords=("chart analysis", "derivative", "integral", "smoothing", "interpolation", "arc length", "series"),
            related=(*_ANALYSIS_RELATED, PANEL_TOPIC_ANALYSIS),
        ),
        HelpTopic(
            id=PANEL_TOPIC_CHART_SIGNAL,
            title="Chart Signal Analysis panel",
            category=HelpCategory.PANELS,
            summary="Analyze a series of the current chart as a signal, for example to find its frequencies or its peaks.",
            steps=(
                'Open a chart tab and click the 📡 icon in the sidebar (its tooltip reads "Chart Signal Analysis panel").',
                "Under Series, choose what to Analyze: a data series or a fitted curve of this chart.",
                "Under Method, choose the analysis. A short description appears below it.",
                "Under Segment (index range), set Start index and End index to analyze only part of the series. The first point is index 0 and both ends are included.",
                ("Under Parameters, set the options the method offers. If there is a Sampling rate, it is filled in from the spacing of the x values "
                "in the segment (1 divided by the typical spacing) and is filled in again whenever you change the series, the method or the segment, "
                "replacing a value you typed. Set it last, and change it if it is not right."),
                "Click Run. The calculation runs in the background and a summary appears in the Results box.",
                'Keep "Plot result" ticked to draw the result, and choose in "Plot on:" whether it goes on a new chart or an existing one.',
                'Click Add to Project to save the result as a new dataset, and plot it if "Plot result" is ticked.',
            ),
            explanation="Clear empties the Results box.",
            keywords=("chart signal", "fft", "frequency", "spectrum", "peaks", "series"),
            related=(*_SIGNAL_RELATED, PANEL_TOPIC_SIGNAL),
        ),
        HelpTopic(
            id=PANEL_TOPIC_CHART_TRANSFORM,
            title="Chart Transform panel",
            category=HelpCategory.PANELS,
            summary="Change the x or y values of a chart series with an expression and add the result to the chart as a new series.",
            steps=(
                'Open a chart tab and click the 🔧 icon in the sidebar (its tooltip reads "Chart Transform panel").',
                "Under Series, choose which series or fitted curve to Transform.",
                "Under Target, choose whether the result replaces Y or X. The other axis stays as it is.",
                ('Under Transform Expression, type an expression using x and y, or choose a ready-made one from "ƒ  Insert function ▾". '
                "Click the ? button to see the names you can use."),
                "Under Result, type a Dataset name or leave it empty to use the suggested name.",
                "Click Preview to see the number of points and the first values.",
                "Click Apply. A new dataset is added to the project and a new series using it is added to the chart.",
            ),
            explanation=(
                "The expression must give one value for every point of the series. "
                "Both x and y are available whichever axis you replace.\n\n"
                "Clear empties the name and the expression and resets the Target to Y."
            ),
            keywords=("chart transform", "expression", "rescale axis", "transform series", "log scale data"),
            related=(
                "transforms.chart_transform",
                "transforms.expressions",
                "transforms.names",
                PANEL_TOPIC_TRANSFORM,
            ),
        ),
    ]
