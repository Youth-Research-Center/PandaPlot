"""Help topics for the analysis operations (derivative, integral, arc length, smoothing, interpolation).

The text describes what ``AnalysisEngine`` and the two analysis panels do. The
mappings send every member of the analysis enums to the topic that explains it.
"""

from pandaplot.analysis.analysis_types import AnalysisType, DerivativeMethod, InterpolationMethod, SmoothingMethod
from pandaplot.services.help.content.panel_defaults import (
    INTERPOLATION_POINTS_CHART,
    INTERPOLATION_POINTS_DATASET,
    ROLLING_WINDOW_CHART,
    ROLLING_WINDOW_DATASET,
    SAVGOL_POLYNOMIAL_ORDER,
    SAVGOL_WINDOW_LENGTH,
)
from pandaplot.services.help.help_types import PANEL_TOPIC_ANALYSIS, PANEL_TOPIC_CHART_ANALYSIS, HelpCategory, HelpTopic

ANALYSIS_TOPIC_IDS: dict[AnalysisType, str] = {
    AnalysisType.DERIVATIVE: "analysis.derivative",
    AnalysisType.INTEGRAL: "analysis.integral",
    AnalysisType.ARC_LENGTH: "analysis.arc_length",
    AnalysisType.SMOOTHING: "analysis.smoothing",
    AnalysisType.INTERPOLATION: "analysis.interpolation",
}

DERIVATIVE_TOPIC_IDS: dict[DerivativeMethod, str] = {
    DerivativeMethod.CENTRAL: "analysis.derivative_methods",
    DerivativeMethod.FORWARD: "analysis.derivative_methods",
    DerivativeMethod.BACKWARD: "analysis.derivative_methods",
}

SMOOTHING_TOPIC_IDS: dict[SmoothingMethod, str] = {
    SmoothingMethod.SAVGOL: "analysis.smoothing_savgol",
    SmoothingMethod.ROLLING_MEAN: "analysis.smoothing_rolling_mean",
    SmoothingMethod.LOWESS: "analysis.smoothing_lowess",
}

INTERPOLATION_TOPIC_IDS: dict[InterpolationMethod, str] = {
    InterpolationMethod.LINEAR: "analysis.interpolation_methods",
    InterpolationMethod.CUBIC: "analysis.interpolation_methods",
    InterpolationMethod.QUADRATIC: "analysis.interpolation_methods",
    InterpolationMethod.NEAREST: "analysis.interpolation_methods",
}

_PANELS = (PANEL_TOPIC_ANALYSIS, PANEL_TOPIC_CHART_ANALYSIS)

_PREVIEW_STEP = (
    "Click Preview to check the result, then Apply. In the Analysis Operations panel the preview shows summary statistics; "
    "in the Chart Analysis panel it shows the number of points and the first rows."
)


def topics() -> list[HelpTopic]:
    """Return the help topics of this module.

    Returns:
        The topics, in display order.
    """
    return [
        HelpTopic(
            id=ANALYSIS_TOPIC_IDS[AnalysisType.DERIVATIVE],
            title="Derivative",
            category=HelpCategory.ANALYSIS,
            summary="Calculates how fast Y changes as X changes, at every point of your data (the slope of the curve).",
            steps=(
                "In the Analysis Operations panel (dataset tab) or the Chart Analysis panel (chart tab), choose Derivative as the type.",
                "Choose a Method: Central difference, Forward difference or Backward difference.",
                "Choose the X and Y columns (dataset tab) or the series (chart tab), and the range of rows or points to use.",
                _PREVIEW_STEP,
            ),
            explanation=(
                "The derivative is the slope of Y plotted against X. Its unit is the unit of Y per unit of X: "
                "if Y is distance in metres and X is time in seconds, the derivative is a speed in metres per second.\n\n"
                "PandaPlot estimates the slope from the differences between neighbouring points. "
                "The result has one value for each point in the range, so it lines up with your data. "
                "It needs at least two points. Your X values should be in order and should not repeat, "
                "because the calculation divides by the change in X.\n\n"
                "Differences between neighbouring points amplify noise. If the result is very jagged, smooth the data first."
            ),
            parameters=(
                ("Method", 'How the slope at each point is estimated. See "Derivative methods".'),
                ("Start Row / End Row", "Dataset tab: the part of the data to use. Rows are numbered from 1 and both ends are included."),
                ("Start index / End index", "Chart tab: the part of the series to use. Points are numbered from 0 and both ends are included."),
            ),
            formula="dy/dx ≈ (y₂ - y₁) / (x₂ - x₁)",
            example=(
                "Y = position in metres recorded every second (X). A derivative of 2.5 at a point means the object was moving at about "
                "2.5 metres per second there."
            ),
            keywords=("differentiate", "differentiation", "slope", "gradient", "rate of change", "dy/dx", "velocity"),
            related=("analysis.derivative_methods", "analysis.smoothing", "analysis.integral", *_PANELS),
        ),
        HelpTopic(
            id="analysis.derivative_methods",
            title="Derivative methods",
            category=HelpCategory.ANALYSIS,
            summary="Central, forward and backward differences are three ways to estimate the slope at a point from its neighbours.",
            explanation=(
                "Central difference (the default) looks at the points on both sides of each point. "
                "It is usually the best choice for points in the middle of the data. "
                "At the first and last point it can only use one neighbour.\n\n"
                "Forward difference uses the slope between a point and the next one. "
                "The last point has no next neighbour, so it repeats the slope of the previous step.\n\n"
                "Backward difference uses the slope between a point and the previous one. "
                "The first point has no previous neighbour, so it repeats the slope of the next step.\n\n"
                "For smooth data all three give similar answers away from the ends."
            ),
            parameters=(
                ("Central difference", "Slope from the points on both sides of each point."),
                ("Forward difference", "Slope between a point and the next point."),
                ("Backward difference", "Slope between a point and the previous point."),
            ),
            keywords=("central", "forward", "backward", "finite difference", "numerical derivative", "differentiate"),
            related=(ANALYSIS_TOPIC_IDS[AnalysisType.DERIVATIVE],),
        ),
        HelpTopic(
            id=ANALYSIS_TOPIC_IDS[AnalysisType.INTEGRAL],
            title="Integral",
            category=HelpCategory.ANALYSIS,
            summary="Calculates the area under your curve, adding it up point by point from the start of the range.",
            steps=(
                "In the Analysis Operations panel (dataset tab) or the Chart Analysis panel (chart tab), choose Integral as the type.",
                "Choose the X and Y columns (dataset tab) or the series (chart tab), and the range of rows or points to use.",
                _PREVIEW_STEP,
            ),
            explanation=(
                "PandaPlot uses the trapezoidal rule: the area between each pair of neighbouring points is treated as a trapezoid, "
                "and the areas are added up. The method is fixed, so the panel has no options for it.\n\n"
                "The result is a running total. It is 0 at the first point of the range, and its last value is the total area under the curve. "
                "Its unit is the unit of Y multiplied by the unit of X: velocity in metres per second integrated over seconds gives metres.\n\n"
                "In the Analysis Operations panel the preview shows Total Integral, Final Value and Mean Rate. "
                "The mean rate is the total area divided by the width of the X range, which is the average height of the curve."
            ),
            formula="∫ y dx ≈ Σ (xᵢ₊₁ - xᵢ) · (yᵢ + yᵢ₊₁) / 2",
            example="Y = speed in metres per second recorded over time X in seconds. The last value of the integral is the distance travelled in metres.",
            keywords=("integrate", "integration", "area under curve", "area under the curve", "auc", "trapezoid", "trapezoidal", "cumulative"),
            related=(ANALYSIS_TOPIC_IDS[AnalysisType.DERIVATIVE], ANALYSIS_TOPIC_IDS[AnalysisType.ARC_LENGTH], *_PANELS),
        ),
        HelpTopic(
            id=ANALYSIS_TOPIC_IDS[AnalysisType.ARC_LENGTH],
            title="Arc length",
            category=HelpCategory.ANALYSIS,
            summary="Measures the length of the line you would draw through your points, adding up the straight-line distance between neighbouring points.",
            steps=(
                ("In the Analysis Operations panel (dataset tab) or the Chart Analysis panel (chart tab), choose Arc Length (called "
                '"Arc length (line length)" on the chart tab) as the type.'),
                "Choose the X and Y columns (dataset tab) or the series (chart tab), and the range of rows or points to use.",
                _PREVIEW_STEP,
            ),
            explanation=(
                "For every pair of neighbouring points PandaPlot calculates the straight-line (Euclidean) distance, using both the X and the Y change. "
                "The result is a running total that starts at 0 at the first point of the range. Its last value is the total length of the line.\n\n"
                "In the Analysis Operations panel the preview shows Total Length, Mean Segment and Max Segment. "
                "X and Y should be in the same unit for the length to mean something."
            ),
            formula="length = Σ √((xᵢ₊₁ - xᵢ)² + (yᵢ₊₁ - yᵢ)²)",
            keywords=("line length", "curve length", "path length", "euclidean distance", "distance along curve", "cumulative length"),
            related=(ANALYSIS_TOPIC_IDS[AnalysisType.INTEGRAL], *_PANELS),
        ),
        HelpTopic(
            id=ANALYSIS_TOPIC_IDS[AnalysisType.SMOOTHING],
            title="Smoothing",
            category=HelpCategory.ANALYSIS,
            summary="Reduces noise in your Y values so the overall shape of the data is easier to see.",
            steps=(
                "In the Analysis Operations panel (dataset tab) or the Chart Analysis panel (chart tab), choose Smoothing as the type.",
                'Choose a Method: Savitzky-Golay, Rolling Mean ("Rolling mean" on the chart tab) or LOWESS.',
                "Set the options the method shows, such as Window Length and Polynomial Order, or Window Size.",
                "Choose the X and Y columns (dataset tab) or the series (chart tab), and the range of rows or points to use.",
                _PREVIEW_STEP,
            ),
            explanation=(
                "Smoothing replaces each Y value with a value calculated from its neighbours, so random ups and downs partly cancel out. "
                "The result has one smoothed value for every point in the range.\n\n"
                "A wider window gives a smoother curve, but it also flattens real peaks and dips, so use the smallest window that removes the noise.\n\n"
                "In the Analysis Operations panel the preview shows Original Std and Smoothed Std (the spread of the values before and after), "
                "Noise Reduction Percent (how much the spread went down) and Correlation (how closely the smoothed values follow the original ones)."
            ),
            keywords=("smooth", "denoise", "noise reduction", "filter", "moving average", "savitzky golay", "loess", "lowess", "rolling mean"),
            related=(*SMOOTHING_TOPIC_IDS.values(), ANALYSIS_TOPIC_IDS[AnalysisType.DERIVATIVE], *_PANELS),
        ),
        HelpTopic(
            id=SMOOTHING_TOPIC_IDS[SmoothingMethod.SAVGOL],
            title="Smoothing: Savitzky-Golay",
            category=HelpCategory.ANALYSIS,
            summary="Fits a small polynomial to each window of points. It smooths noise while keeping peaks and their widths better than a plain average.",
            explanation=(
                "For every point, PandaPlot fits a polynomial to the points in a window around it and uses the value of that polynomial. "
                "Because the polynomial can bend, peaks are flattened less than with a plain moving average.\n\n"
                f"Window Length is the number of points in each window. It starts at {SAVGOL_WINDOW_LENGTH.default} "
                f"and can be set from {SAVGOL_WINDOW_LENGTH.minimum} to {SAVGOL_WINDOW_LENGTH.maximum}. "
                "PandaPlot needs an odd number, so an even number is raised by one. "
                "The window cannot be longer than the number of points in the range you analyze.\n\n"
                f"Polynomial Order is the degree of the polynomial. It starts at {SAVGOL_POLYNOMIAL_ORDER.default} "
                f"and can be set from {SAVGOL_POLYNOMIAL_ORDER.minimum} to {SAVGOL_POLYNOMIAL_ORDER.maximum}. "
                "It must be smaller than the window length. A low order smooths more; a high order follows the data more closely."
            ),
            parameters=(
                (
                    "Window Length",
                    (
                        f"Number of points in each window ({SAVGOL_WINDOW_LENGTH.default} by default, "
                        f"{SAVGOL_WINDOW_LENGTH.minimum} to {SAVGOL_WINDOW_LENGTH.maximum}). Should be odd."
                    ),
                ),
                (
                    "Polynomial Order",
                    (
                        f"Degree of the polynomial fitted in each window ({SAVGOL_POLYNOMIAL_ORDER.default} by default, "
                        f"{SAVGOL_POLYNOMIAL_ORDER.minimum} to {SAVGOL_POLYNOMIAL_ORDER.maximum}). Must be less than the window length."
                    ),
                ),
            ),
            keywords=("savitzky-golay", "savitzky golay", "savgol", "sg filter", "polynomial smoothing", "smooth"),
            related=(ANALYSIS_TOPIC_IDS[AnalysisType.SMOOTHING], "analysis.smoothing_rolling_mean", "analysis.smoothing_lowess"),
        ),
        HelpTopic(
            id=SMOOTHING_TOPIC_IDS[SmoothingMethod.ROLLING_MEAN],
            title="Smoothing: Rolling mean",
            category=HelpCategory.ANALYSIS,
            summary="Replaces each value with the average of the points around it (a moving average).",
            explanation=(
                "For every point, PandaPlot averages the values in a window centred on that point. "
                "Near the start and end of the range the window is incomplete, so those points take the value of the nearest point that could be averaged.\n\n"
                f"Window Size is the number of points averaged. It starts at {ROLLING_WINDOW_DATASET.default}. "
                f"In the Analysis Operations panel it can be set from {ROLLING_WINDOW_DATASET.minimum} to {ROLLING_WINDOW_DATASET.maximum}, "
                f"in the Chart Analysis panel from {ROLLING_WINDOW_CHART.minimum} to {ROLLING_WINDOW_CHART.maximum}. "
                "A larger window gives a smoother curve but also blurs sharp peaks."
            ),
            parameters=(("Window Size", f"Number of points averaged around each point ({ROLLING_WINDOW_DATASET.default} by default)."),),
            keywords=("rolling mean", "moving average", "running average", "sliding window", "average", "smooth"),
            related=(ANALYSIS_TOPIC_IDS[AnalysisType.SMOOTHING], "analysis.smoothing_savgol", "analysis.smoothing_lowess"),
        ),
        HelpTopic(
            id=SMOOTHING_TOPIC_IDS[SmoothingMethod.LOWESS],
            title="Smoothing: LOWESS",
            category=HelpCategory.ANALYSIS,
            summary="Fits a straight line to the nearest points around each point, giving closer points more weight (also called LOESS).",
            explanation=(
                "LOWESS stands for locally weighted scatterplot smoothing. "
                "For every point, PandaPlot looks at the nearest points in X, fits a line to them so that closer points count more, "
                "and uses the value of that line at the point.\n\n"
                "Each local fit uses 20% of the points in the range. This setting is not shown in the panel, so LOWESS has no options to set. "
                "It suits data with a gently changing trend."
            ),
            keywords=("lowess", "loess", "locally weighted", "local regression", "scatterplot smoothing", "smooth"),
            related=(ANALYSIS_TOPIC_IDS[AnalysisType.SMOOTHING], "analysis.smoothing_savgol", "analysis.smoothing_rolling_mean"),
        ),
        HelpTopic(
            id=ANALYSIS_TOPIC_IDS[AnalysisType.INTERPOLATION],
            title="Interpolation",
            category=HelpCategory.ANALYSIS,
            summary="Estimates Y values at new, evenly spaced X positions between your measured points.",
            steps=(
                "In the Analysis Operations panel (dataset tab) or the Chart Analysis panel (chart tab), choose Interpolation as the type.",
                "Choose a Method: Linear, Cubic, Quadratic or Nearest.",
                "Set Points, the number of new values to calculate.",
                "Choose the X and Y columns (dataset tab) or the series (chart tab), and the range of rows or points to use.",
                _PREVIEW_STEP,
            ),
            explanation=(
                "PandaPlot creates Points new X positions, evenly spaced from the smallest to the largest X in the range, "
                "and calculates a Y value at each one by passing a curve through your measured points. "
                "Use it to fill gaps, to resample unevenly spaced data, or to draw a smooth curve through the points.\n\n"
                f"Points starts at {INTERPOLATION_POINTS_DATASET.default} in the Analysis Operations panel "
                f"({INTERPOLATION_POINTS_DATASET.minimum} to {INTERPOLATION_POINTS_DATASET.maximum}) and at {INTERPOLATION_POINTS_CHART.default} "
                f"in the Chart Analysis panel ({INTERPOLATION_POINTS_CHART.minimum} to {INTERPOLATION_POINTS_CHART.maximum}).\n\n"
                "The result has its own X positions, which are not the same as your original rows. "
                "On the chart tab the new dataset contains both the new X values and the interpolated Y values. "
                "In the Analysis Operations panel only the Y values are stored: they are written into the new column from the first row of the dataset "
                "downwards, whatever Data Range you chose, and any rows below them stay empty. "
                "Points must not be larger than the number of rows in the dataset, otherwise Apply fails."
            ),
            parameters=(
                ("Method", 'How the curve between points is drawn. See "Interpolation methods".'),
                ("Points", "How many new values to calculate. In the Analysis Operations panel it must not exceed the number of rows in the dataset."),
            ),
            keywords=("interpolate", "resample", "fill gaps", "upsample", "spline", "estimate between points"),
            related=("analysis.interpolation_methods", *_PANELS),
        ),
        HelpTopic(
            id="analysis.interpolation_methods",
            title="Interpolation methods",
            category=HelpCategory.ANALYSIS,
            summary="Linear, cubic, quadratic and nearest are different ways to estimate values between your measured points.",
            explanation=(
                "Linear joins neighbouring points with straight lines. It never overshoots your data.\n\n"
                "Cubic fits a smooth curve (a cubic spline) through all the points. It looks smooth but can overshoot between points. "
                "With fewer than four points PandaPlot uses linear instead.\n\n"
                "Quadratic fits smooth piecewise parabolas through the points.\n\n"
                "Nearest gives each new position the Y value of the closest measured point, so the result is a staircase."
            ),
            parameters=(
                ("Linear", "Straight lines between neighbouring points."),
                ("Cubic", "A smooth cubic spline through the points. Needs at least four points, otherwise linear is used."),
                ("Quadratic", "A smooth curve made of parabolas."),
                ("Nearest", "The Y value of the closest measured point."),
            ),
            keywords=("linear", "cubic", "quadratic", "nearest", "spline", "interpolate"),
            related=(ANALYSIS_TOPIC_IDS[AnalysisType.INTERPOLATION],),
        ),
    ]
