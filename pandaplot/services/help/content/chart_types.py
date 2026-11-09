"""Help topics derived per chart type.

The display name, category, columns (roles), curve-fit and error-bar support, swap-axes support and 3-D flag come from
``CHART_TYPE_SPECS``, ``ROLE_LABELS`` and ``SWAPPABLE_CHART_TYPES``. The description of what each chart shows, its example and its
search keywords are written here.
"""

from dataclasses import dataclass

from pandaplot.models.chart.chart_role_labels import ROLE_LABELS
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.chart_type_spec import CHART_TYPE_SPECS, ChartTypeSpec
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import SWAPPABLE_CHART_TYPES
from pandaplot.services.help.content.panel_defaults import HIST_BINS
from pandaplot.services.help.help_types import (
    CHART_TOPIC_CHOOSE_TYPE,
    CHART_TOPIC_CREATE,
    CHART_TOPIC_ERROR_BARS,
    FIT_TOPIC_OVERVIEW,
    HelpCategory,
    HelpTopic,
)

CHART_TYPE_TOPIC_IDS: dict[ChartType, str] = {chart_type: f"charts.{chart_type.value}" for chart_type in ChartType}


@dataclass(frozen=True)
class _ChartTypeText:
    """Hand-written help text for one chart type.

    Attributes:
        summary: What the chart shows and when to use it, in one or two sentences.
        explanation: Fuller plain-language description of the chart.
        example: One concrete student example.
        keywords: Extra search terms.
    """

    summary: str
    explanation: str
    example: str
    keywords: tuple[str, ...] = ()


_ROW_NUMBER_NOTE = (
    "The X column is optional. If you leave it empty, the values are plotted against the row number of the dataset."
)

_THREE_D_NOTE = "A 3-D chart needs an X, a Y and a Z column. You can add a 3D Scatter or 3D Line series on top to mark points or a path."

_CHART_TYPE_TEXT: dict[ChartType, _ChartTypeText] = {
    ChartType.LINE: _ChartTypeText(
        summary="Joins the points with a line, in the order of the rows. Use it to show how one quantity changes, for example over time.",
        explanation=(
            "Each point is drawn at (X, Y) and neighbouring points are joined by a line. Markers, line style and an area fill are "
            "set on the Style tab.\n\n" + _ROW_NUMBER_NOTE
        ),
        example="Plot the temperature of a cooling cup of tea (Y) against the time in minutes (X).",
        keywords=("plot", "graph", "line graph", "time series", "trend"),
    ),
    ChartType.SCATTER: _ChartTypeText(
        summary="Shows each (X, Y) pair as a single point. Use it to see whether two quantities are related.",
        explanation=(
            "Points are not joined, so the order of the rows does not matter. This makes it a good choice for measurements "
            "that scatter around a trend, and for curve fits.\n\n" + _ROW_NUMBER_NOTE
        ),
        example="Plot the height of each student (Y) against their arm span (X) to see if tall students have a long arm span.",
        keywords=("plot", "graph", "points", "dots", "correlation", "scatter plot", "scattergram"),
    ),
    ChartType.BAR: _ChartTypeText(
        summary="Draws one bar per row, with the height set by the Y value. Use it to compare amounts between categories.",
        explanation=(
            "The X values place and label the bars. They can be numbers, text or dates. Add one series per group to "
            "compare several groups.\n\n" + _ROW_NUMBER_NOTE
        ),
        example="Compare the number of goals scored by each team in a league (teams in X, goals in Y).",
        keywords=("bar graph", "bar chart", "column chart", "compare", "categories"),
    ),
    ChartType.STACKED_BAR: _ChartTypeText(
        summary="Stacks the bars of several series on top of each other at each X position. Use it to show how a total is made up of parts.",
        explanation=(
            "Each series adds its bar on top of the bars of the series before it. Negative values stack downwards from zero. "
            "You need at least two series to see any stacking.\n\n" + _ROW_NUMBER_NOTE
        ),
        example="Show the sales of three products in each month, stacked so that the full height is the total sales.",
        keywords=("stacked bar graph", "stacked column", "stack", "total", "parts of a whole"),
    ),
    ChartType.HIST: _ChartTypeText(
        summary="Counts how many values fall into each bin and draws a bar for each. Use it to see how one set of values is spread out.",
        explanation=(
            "Only one column is needed. The values are sorted into equal-width bins, and each bar shows how many values are in its bin. "
            "Few bins hide detail. Many bins make the shape look jagged."
        ),
        example="Plot the exam marks of a class to see whether most students scored near the middle or near the top.",
        keywords=("distribution", "frequency", "bins", "spread", "histogram plot"),
    ),
    ChartType.DENSITY: _ChartTypeText(
        summary="Draws a smooth curve that shows how one set of values is spread out. It is a smoothed histogram.",
        explanation=(
            "The curve is a kernel density estimate (KDE): every value adds a small bump, and the bumps are added up. "
            "The area under the curve is 1, so the height shows how common values are, not how many there are. "
            "The curve needs at least two different values.\n\n"
            "You can also add a Histogram series to the same chart. It is then drawn on the same scale as the curve."
        ),
        example="Plot the reaction times of 30 students as a smooth curve to see where most of the times lie.",
        keywords=("kde", "kernel density", "smoothed histogram", "distribution", "probability density"),
    ),
    ChartType.VECTOR: _ChartTypeText(
        summary="Draws an arrow at each (X, Y) position. The U and V columns set how far the arrow points sideways and up.",
        explanation=(
            "Use it to show a field, such as wind or water flow, where every position has a direction and a size. "
            "If you add the optional Color-by column (the magnitude), the arrows are coloured by it and a colour bar is shown."
        ),
        example="Show the wind at weather stations: X and Y give the position, U is the east-west speed, V is the north-south speed.",
        keywords=("quiver", "arrows", "vector field", "field", "flow", "direction"),
    ),
    ChartType.COLORMAP: _ChartTypeText(
        summary="Draws a point at each (X, Y) position and colours it by the Z value. Use it when you have a third quantity to show.",
        explanation=(
            "The points keep their own position, so the data does not need to lie on a grid. A colour bar shows which colour means "
            "which Z value. Choose the colormap and the colour range on the Axes tab, in the Color Map card.\n\n"
            "A Heatmap is different: it fills a whole grid of cells, or draws contour lines, instead of separate points."
        ),
        example="Plot the temperature measured at different (X, Y) positions on a metal plate and colour each point by its temperature.",
        keywords=("colour map", "color map", "colormap", "scatter colour", "third variable", "colorbar"),
    ),
    ChartType.HEATMAP: _ChartTypeText(
        summary="Fills a grid of cells with colour by the Z value, or draws contour lines. Use it to see how a value changes over an area.",
        explanation=(
            "The (X, Y, Z) rows are placed on a regular grid, so each cell is coloured by one Z value. Cells with no data stay empty. "
            "The Style tab can instead draw filled contours, contour lines or both, and can build the picture from scattered points "
            "by triangulating them.\n\n"
            "A Color Map chart is different: it draws a separate coloured point for every row and does not fill the space between them."
        ),
        example="Show the number of visitors by weekday (X) and hour of the day (Y), coloured by how busy it is (Z).",
        keywords=("heat map", "grid", "contour", "contour plot", "contourf", "colour map", "color map", "matrix"),
    ),
    ChartType.PIE: _ChartTypeText(
        summary="Draws one wedge per value. The size of each wedge is its share of the total. Use it to show parts of a whole.",
        explanation=(
            "The values column sets the size of the wedges. The optional labels column names the wedges. "
            "Rows that are blank or zero are skipped. A pie chart cannot show negative values, so a chart with a negative value is "
            "not drawn. The Style tab can show percentages and turn the pie into a donut."
        ),
        example="Show how a class votes on a trip: one wedge per destination, sized by the number of votes.",
        keywords=("pie chart", "pie graph", "donut", "doughnut", "share", "percentage", "wedge"),
    ),
    ChartType.SCATTER3D: _ChartTypeText(
        summary="Shows each (X, Y, Z) row as a point in 3-D space. Use it to see how three quantities are related.",
        explanation="Points are not joined. " + _THREE_D_NOTE,
        example="Plot the height, mass and age of a group of students as one point each.",
        keywords=("3d", "three dimensional", "3-d scatter", "scatter plot 3d", "point cloud"),
    ),
    ChartType.LINE3D: _ChartTypeText(
        summary="Joins (X, Y, Z) points with a line in 3-D space, in the order of the rows. Use it to show a path.",
        explanation="Use it for a path or a trajectory where the order of the rows matters. " + _THREE_D_NOTE,
        example="Plot the path of a drone from its logged (X, Y, Z) position.",
        keywords=("3d", "three dimensional", "3-d line", "path", "trajectory", "curve"),
    ),
    ChartType.SURFACE: _ChartTypeText(
        summary="Draws a smooth coloured surface over the X and Y plane, with the height set by Z. Use it to show a function of two variables.",
        explanation=(
            "The (X, Y, Z) rows are placed on a grid and joined into a surface that is coloured by its height. "
            "Grid cells without data are left as holes. " + _THREE_D_NOTE
        ),
        example="Show the height of a hill from measurements on a grid of (X, Y) positions.",
        keywords=("3d", "three dimensional", "3-d surface", "surface plot", "terrain", "function of two variables"),
    ),
    ChartType.WIREFRAME: _ChartTypeText(
        summary="Draws the grid lines of a surface in 3-D, with the height set by Z. Use it when you want to see through the surface.",
        explanation=(
            "It uses the same grid as a 3D Surface, but only the lines are drawn and the faces are left empty. "
            "Cells without data are left as holes. " + _THREE_D_NOTE
        ),
        example="Show the shape of the function z = x² + y² as a mesh of lines.",
        keywords=("3d", "three dimensional", "3-d wireframe", "mesh", "wire frame", "grid lines"),
    ),
    ChartType.BAR3D: _ChartTypeText(
        summary="Draws a 3-D bar at each (X, Y) position, rising from zero to the Z value. Use it to compare values over two categories.",
        explanation=(
            "Each row becomes one box. The width of the boxes follows the spacing between the X values and between the Y values. "
            + _THREE_D_NOTE
        ),
        example="Show the average temperature for each combination of month (X) and city (Y).",
        keywords=("3d", "three dimensional", "3-d bar", "3d bar chart", "3d histogram", "boxes"),
    ),
    ChartType.TRISURF: _ChartTypeText(
        summary="Joins scattered (X, Y, Z) points into a surface made of triangles. Use it when the points do not lie on a regular grid.",
        explanation=(
            "The points are connected into triangles, and the triangles are coloured by height. "
            "You do not need a regular grid, which makes it a good choice for measurements taken at uneven positions. " + _THREE_D_NOTE
        ),
        example="Show the depth of a lake from measurements taken at random (X, Y) positions from a boat.",
        keywords=("3d", "three dimensional", "triangulated surface", "triangles", "trisurf", "irregular", "scattered points"),
    ),
    ChartType.VECTOR3D: _ChartTypeText(
        summary="Draws an arrow at each (X, Y, Z) position. The U, V and W columns set the arrow's direction and length.",
        explanation=(
            "Use it to show a 3-D field, such as a magnetic field or air flow. All six columns are needed. "
            "The Color-by column (the magnitude) is optional. " + _THREE_D_NOTE
        ),
        example="Show the direction and strength of a magnetic field measured at points around a magnet.",
        keywords=("3d", "three dimensional", "3-d vector", "quiver", "arrows", "vector field", "field"),
    ),
    ChartType.BOX: _ChartTypeText(
        summary="Summarises one column of values as a box with whiskers. Use it to compare the spread of several groups side by side.",
        explanation=(
            "The box covers the middle half of the values, and the line inside it is the median. The whiskers reach out to the "
            "rest of the typical values. Points beyond the whiskers are outliers.\n\n"
            "Each series draws one box. To compare groups, add one series for each group, with each group's values in its own column. "
            "The series label names the box on the X axis."
        ),
        example="Compare the test marks of three classes: add one series per class and read the medians side by side.",
        keywords=("boxplot", "box plot", "box and whisker", "whisker", "quartile", "median", "outlier", "distribution"),
    ),
}


def _role_label(role: str, spec: ChartTypeSpec) -> str:
    label = ROLE_LABELS[role]
    if role not in spec.required_roles and "(optional)" not in label:
        label += " (optional)"
    return label


def _uses_histogram_bins(spec: ChartTypeSpec) -> bool:
    """Return whether the chart type offers the histogram "Bins:" control (the rule the Chart tab uses)."""
    return SeriesType.HIST in spec.allowed_series_types


def _facts(chart_type: ChartType, spec: ChartTypeSpec) -> str:
    """Build the paragraph of facts that is derived from the chart type spec.

    Args:
        chart_type: The chart type.
        spec: Its entry in ``CHART_TYPE_SPECS``.

    Returns:
        Short sentences, one per fact.
    """
    sentences = [
        f"Listed under {spec.category.value} in the chart wizard.",
        "Columns: " + ", ".join(_role_label(role, spec) for role in spec.roles) + ".",
        "Curve fits are available." if spec.allows_fit else "Curve fits are not available on this chart type.",
        "Error bars are supported." if spec.supports_error_bars else "Error bars are not supported on this chart type.",
    ]
    if chart_type in SWAPPABLE_CHART_TYPES:
        sentences.append('The "Swap X/Y" button on the chart toolbar is available on this chart type.')
    if not spec.has_axes:
        sentences.append("This chart has no axes. Set the title, subtitle and legend on the Chart and Legend tabs.")
    if spec.is_3d:
        sentences.append(
            'Drag the chart to rotate it (the rotation is not saved). Set Elevation and Azimuth in the "3D View" card on the Axes tab '
            "to choose the viewing angle."
        )
    if _uses_histogram_bins(spec):
        sentences.append(
            f'The "Bins:" control on the Chart tab of Chart Properties sets the number of bins for histogram series. '
            f"It goes from {int(HIST_BINS.minimum)} to {int(HIST_BINS.maximum)} and starts at {int(HIST_BINS.default)}."
        )
    return " ".join(sentences)


def _topic(chart_type: ChartType, spec: ChartTypeSpec) -> HelpTopic:
    text = _CHART_TYPE_TEXT[chart_type]
    title = spec.display_name if spec.display_name.endswith("Plot") else f"{spec.display_name} chart"
    related = [CHART_TOPIC_CHOOSE_TYPE, CHART_TOPIC_CREATE]
    if spec.allows_fit:
        related.append(FIT_TOPIC_OVERVIEW)
    if spec.supports_error_bars:
        related.append(CHART_TOPIC_ERROR_BARS)
    return HelpTopic(
        id=CHART_TYPE_TOPIC_IDS[chart_type],
        title=title,
        category=HelpCategory.CHARTS,
        summary=text.summary,
        explanation=f"{text.explanation}\n\n{_facts(chart_type, spec)}",
        example=text.example,
        keywords=(*text.keywords, spec.display_name.lower(), chart_type.value),
        related=tuple(related),
    )


def topics() -> list[HelpTopic]:
    """Return the per-chart-type topics.

    Returns:
        One topic per chart type, in ``CHART_TYPE_SPECS`` order.
    """
    return [_topic(chart_type, spec) for chart_type, spec in CHART_TYPE_SPECS.items()]
