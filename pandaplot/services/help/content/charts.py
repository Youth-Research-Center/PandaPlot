"""Hand-written help topics for charts.

Creating a chart (the wizard), choosing a type, and using the chart tab and every tab of the Chart Properties panel. The labels follow what
the screens show. Which chart types support error bars or Swap X/Y is read from ``CHART_TYPE_SPECS`` and ``SWAPPABLE_CHART_TYPES``, so the
text cannot drift from the code. The per-type topics live in ``chart_types.py``.
"""

from pandaplot.models.chart.chart_type_spec import CHART_TYPE_SPECS
from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS
from pandaplot.models.project.items.chart import SWAPPABLE_CHART_TYPES
from pandaplot.services.help.content.chart_types import CHART_TYPE_TOPIC_IDS, error_bar_series_names
from pandaplot.services.help.help_types import (
    CHART_TOPIC_AXES,
    CHART_TOPIC_CHOOSE_TYPE,
    CHART_TOPIC_CREATE,
    CHART_TOPIC_ERROR_BARS,
    CHART_TOPIC_LEGEND,
    CHART_TOPIC_MATH_TEXT,
    CHART_TOPIC_SAVE_IMAGE,
    CHART_TOPIC_SERIES,
    CHART_TOPIC_STYLE,
    CHART_TOPIC_VIEW,
    CHART_TOPIC_WIZARD_DATA,
    PANEL_TOPIC_CHART_PROPERTIES,
    HelpCategory,
    HelpTopic,
)

_ALL_TYPE_TOPICS: tuple[str, ...] = tuple(CHART_TYPE_TOPIC_IDS.values())
_ERROR_BAR_CHART_TYPES: str = ", ".join(spec.display_name for spec in CHART_TYPE_SPECS.values() if spec.supports_error_bars)


def _join_names(names: list[str], last_word: str) -> str:
    """Join names as "A, B and C" (or "A, B or C" with ``last_word="or"``)."""
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} {last_word} {names[-1]}"


_ERROR_BAR_SERIES_VALUES: frozenset[str] = frozenset(series_type.value for series_type, spec in SERIES_TYPE_SPECS.items() if spec.supports_error_bars)
_ERROR_BAR_SERIES_TYPES: str = _join_names(
    [spec.display_name for chart_type, spec in CHART_TYPE_SPECS.items() if chart_type.value in _ERROR_BAR_SERIES_VALUES], "and"
)
_ERROR_BAR_OVERLAY_CHART_TYPES: str = _join_names(
    [spec.display_name for spec in CHART_TYPE_SPECS.values() if not spec.supports_error_bars and error_bar_series_names(spec)], "or"
)
_SWAP_CHART_TYPES: str = ", ".join(CHART_TYPE_SPECS[chart_type].display_name for chart_type in CHART_TYPE_SPECS if chart_type in SWAPPABLE_CHART_TYPES)


def topics() -> list[HelpTopic]:
    """Return the hand-written chart topics.

    Returns:
        The topics, in display order.
    """
    return [
        HelpTopic(
            id=CHART_TOPIC_CREATE,
            title="Create a chart",
            category=HelpCategory.CHARTS,
            summary="Turn your data into a graph with the chart wizard: pick a chart type, choose the columns, then add a title and axis labels.",
            steps=(
                ('Open the wizard in any of these ways: Chart > Create New; the "Create Chart" button on a dataset tab '
                 '(columns you selected in the table are filled in for you); right-click a dataset in the project tree and choose "Create Chart"; '
                 'or click "4. Create Visualizations" on the Welcome tab and then "Create Chart". '
                 'The "Analyze Measurements" wizard also ends with a "Plot a Graph" button.'),
                ("Step 1, Type: pick a group in the category drop-down, then a chart type in the list below it. "
                 "The Preview on the right shows a sample of that type. Click Next."),
                ('Step 2, Data: under Series, choose the "Dataset:" and the columns for the series. '
                 'Next stays greyed out until every required column is chosen. Click "+ Add series" to plot more than one data set on the same chart. '
                 'See "Chart wizard: choose the data" for the details.'),
                ('Step 3, Labels: type a Title and Subtitle. For charts with axes, also type an "X-axis label" and a "Y-axis label". '
                 'The Title and axis-label fields start with suggestions; the axis labels come from your column names. The Subtitle starts empty.'),
                'Use the "Show legend" and "Show grid lines" switches. The preview on the right updates as you type.',
                'Click "Create Chart". The new chart opens in its own tab.',
                ("To go back to an earlier step, click its name in the step bar at the top (Type, Data or Labels) or click Back. "
                 "Your choices are kept unless you change the chart type."),
                ("After the chart is created, open Chart Properties (the line-chart icon in the sidebar) to change the type, series, style, "
                 "axes and legend."),
            ),
            explanation=(
                'The Labels step is the last one. Pie charts have no axes, so for a pie the axis-label fields and the "Show grid lines" switch are '
                "hidden. A title, subtitle or label can contain math such as $x^2$ (see the math topic).\n\n"
                'Not ready to choose data? Click "Create empty plot instead" on the Type or Data step to get a blank chart with no series. '
                'An empty chart shows "This chart has no data yet" with an "Add Series" button. Click it, choose a dataset and the columns '
                'the chart type needs, and click Add. You can also click "+ Add series" on the Data tab of Chart Properties.\n\n'
                'If the project has no datasets yet, the Data step is replaced by a page that says "This project has no datasets yet". '
                'Click "Import Dataset" to bring in a file and carry on, or "Create Empty Chart" for a blank chart. '
                'Click Cancel at any step to close the wizard without creating anything. '
                'Use the ? button at the bottom left of a step, or press F1 (on a Mac, Cmd+?), to open help for that step.'
            ),
            keywords=(
                "graph", "plot", "new chart", "create chart", "make a graph", "make a plot", "wizard", "visualization", "empty chart", "first series", "import",
                "title", "axis label",
            ),
            related=(
                CHART_TOPIC_MATH_TEXT, CHART_TOPIC_CHOOSE_TYPE, CHART_TOPIC_WIZARD_DATA, PANEL_TOPIC_CHART_PROPERTIES,
                CHART_TOPIC_SERIES, CHART_TOPIC_SAVE_IMAGE,
            ),
        ),
        HelpTopic(
            id=CHART_TOPIC_CHOOSE_TYPE,
            title="Choose a chart type",
            category=HelpCategory.CHARTS,
            summary="Pick the chart type that fits your question and your data. Types are grouped into five categories.",
            steps=(
                ('In the chart wizard, open the category drop-down on the Type step. The five groups are "Line & Scatter", "Bar & Pie", '
                 '"Distribution", "Fields & Grids" and "3-D".'),
                "Click a type in the list. The Preview shows a sample of it, and the help topic of each type lists the columns it needs.",
                ('To change the type of an existing chart, open Chart Properties, go to the Chart tab and use "Category:" and "Type:" '
                 "under Chart Information."),
            ),
            explanation=(
                "Which type answers your question?\n"
                "How does y change with x? Line or Scatter. "
                "Comparing amounts between groups? Bar or Stacked Bar. "
                "Parts of a whole? Pie. "
                "How are the values of one column spread out? Histogram, Density or Box Plot. "
                "Values over a grid, or arrows over a field? Heatmap, Color Map or Vector. "
                "Three numeric columns? One of the 3-D types.\n\n"
                'In Chart Properties, some types are greyed out in the "Type:" list. PandaPlot greys out a type when switching to it would change '
                "the series you already have and lose their settings. Point at a greyed-out type to see why; the tooltip reads "
                '"Switching to ... isn\'t supported from a ... chart".\n\n'
                "Several series on one chart do not all have to be the same type. A Line chart can also hold Scatter series, for example. "
                'Choose each series\' type with "Series Type:" on the Data tab.'
            ),
            keywords=(
                "chart type", "graph type", "which chart", "which graph", "plot type", "line", "scatter", "bar", "pie", "histogram", "box plot",
                "heatmap", "3d", "category", "change type", "switch type",
            ),
            related=(CHART_TOPIC_CREATE, CHART_TOPIC_WIZARD_DATA, CHART_TOPIC_SERIES, PANEL_TOPIC_CHART_PROPERTIES, *_ALL_TYPE_TOPICS),
        ),
        HelpTopic(
            id=CHART_TOPIC_WIZARD_DATA,
            title="Chart wizard: choose the data",
            category=HelpCategory.CHARTS,
            summary="Step 2 of the chart wizard. Each series card picks a dataset and the columns to plot.",
            steps=(
                'Look at the "Dataset:" drop-down on the first series card and choose the dataset.',
                ('Choose the columns. The list depends on the chart type you picked: for example "X column" and "Y column" for a Line chart, '
                 'or "Values column" for a Histogram. The first entry in each drop-down is blank.'),
                'Columns marked "(optional)" can be left blank. Next stays greyed out until each series card has a dataset and all its required columns. On Line, Scatter, Bar and Stacked Bar, "X column" is also optional even though its label does not say so.',
                'To plot another data set on the same chart, click "+ Add series" and fill in the new card.',
                ('To tidy a long list, click the down-arrow button on a card (tooltip "Collapse series") to fold it into a one-line summary. '
                 'Click the right-arrow button ("Expand series") to open it again.'),
                'To drop a series, click "Remove" on its card.',
                'On a Line, Scatter, Bar or Stacked Bar card, tick "Add error bars" to choose columns for the error bars.',
                "Click Next to go on to the Labels step.",
            ),
            explanation=(
                "The wizard shows only the columns its type uses. Line and Scatter charts use X column and Y column. "
                "Bar and Stacked Bar use the same two. Histogram, Density and Box Plot use Values column. "
                "Pie uses Values column and an optional Labels column that names each wedge. Vector adds U column and V column "
                '(the arrow components) and an optional "Color-by column (optional)". Color Map and Heatmap use X column, Y column and Z column. '
                'The 3-D types use X column, Y column and Z column, and 3D Vector adds U column, V column and W column and an optional "Color-by column (optional)".\n\n'
                "On Line, Scatter, Bar and Stacked Bar, the X column is optional. Leave it blank and the values are plotted against the row position, counting from 0.\n\n"
                'Ticking "Add error bars" shows X error (+) column and Y error (+) column, plus the "Asymmetric Error Bars" box, which adds '
                "X error (-) column and Y error (-) column. See the error bars topic for what these do. "
                'If you opened the wizard from a dataset tab with columns selected, the first series is filled in from your selection. '
                'You can also click "Create empty plot instead" to skip this step.'
            ),
            keywords=(
                "wizard", "series", "dataset", "columns", "x column", "y column", "values column", "add series", "remove series", "select data",
                "pick columns",
            ),
            related=(CHART_TOPIC_CREATE, CHART_TOPIC_CHOOSE_TYPE, CHART_TOPIC_ERROR_BARS, CHART_TOPIC_SERIES, *_ALL_TYPE_TOPICS),
        ),
        HelpTopic(
            id=CHART_TOPIC_SERIES,
            title="Add and arrange series",
            category=HelpCategory.CHARTS,
            summary="A series is one set of plotted data. Add, remove, reorder and configure series on the Data tab of Chart Properties.",
            steps=(
                ('Open a chart tab, click the line-chart icon in the sidebar (its tooltip reads "Chart Properties panel") '
                 "and open the Data tab."),
                ('Click "+ Add series" to add one. On a chart with no series it opens the Add Series dialog: choose a dataset and columns and click Add. '
                 "On a chart that already has series it adds a copy of the selected series, with the same dataset and columns, so change them "
                 "afterwards. Each add is its own undo step."),
                ('Click a series card to select it. Its settings open in that card and you can edit them. On the other cards, the right-arrow button (tooltip '
                 '"Expand series details") shows a read-only summary and the down-arrow button hides it again. On the selected card the down arrow is greyed out '
                 '(tooltip "Series details expanded").'),
                'Choose the "Dataset:" and the columns. The column boxes that appear depend on the series type.',
                ('Type a name in "Label:". This is the text shown for the series in the legend. On a Pie chart the legend lists the '
                 'wedges instead, named by the values in the "Labels Column (optional):", so change those values in the dataset to rename them.'),
                ('Use "Series Type:" to change how this series is drawn. The list shows the types the chart type allows. '
                 'Use "Y Axis:" (Y₁ left or Y₂ right) to put it on the left or the right axis.'),
                ('Use the up-arrow and down-arrow buttons on a card to change the plotting order (tooltips "Move up (draw earlier, further back)" and '
                 '"Move down (draw later, further to front)"). A series lower in the list is drawn in front.'),
                'Click the wastebasket button (tooltip "Remove") to delete a series. Removing and reordering are also single undo steps.',
            ),
            explanation=(
                "Adding, removing and reordering series on the Data tab happen at once and each is its own undo step. "
                "Other edits on the Data tab (dataset, columns, label, Y axis) only mark the panel Modified and show on the chart when you click Apply; see the "
                "Chart Properties panel topic for Apply and Revert.\n\n"
                'Some boxes appear only when they make sense. "X Column:" is hidden for Histogram, Density, Box Plot and Pie; there "Y Column:" '
                'becomes "Values Column:". "Y₂ Column (optional):" appears on Line and Scatter series: it plots a second set of values for '
                'the same X on the opposite Y axis, and its colour is set in the "Twin Y Column" card on the Style tab. '
                '"Color-by Column (optional):" is for Vector series. "Labels Column (optional):" is for Pie. '
                "In the chart wizard you can leave the X column blank (Line, Scatter, Bar, Stacked Bar) to plot against the row position. "
                "The Data tab cannot clear an X column once one is chosen.\n\n"
                "You can also click a line, point, bar or legend entry on the chart to select that series in the panel. "
                "Clicking does not select a series while the Pan or Zoom tool is active. "
                'Fits made with the "Curve Fitting" panel, or by choosing "Series Type:" > "Fit", also appear in this list.'
            ),
            keywords=(
                "series", "add series", "remove series", "delete series", "reorder", "order", "z order", "data tab", "second y axis", "y2",
                "secondary axis", "dataset", "column", "label", "legend text", "twin axis", "undo",
            ),
            related=(
                PANEL_TOPIC_CHART_PROPERTIES, CHART_TOPIC_WIZARD_DATA, CHART_TOPIC_ERROR_BARS, CHART_TOPIC_STYLE, CHART_TOPIC_LEGEND,
                CHART_TOPIC_CHOOSE_TYPE,
            ),
        ),
        HelpTopic(
            id=CHART_TOPIC_ERROR_BARS,
            title="Error bars and confidence bands",
            category=HelpCategory.CHARTS,
            summary="Show how uncertain each value is by drawing error bars from a column that holds the size of the error.",
            steps=(
                f"In the chart wizard, error bars can be added on these chart types: {_ERROR_BAR_CHART_TYPES}.",
                ('In the chart wizard, on the Data step, tick "Add error bars" on the series card, then choose "X error (+) column" '
                 'and/or "Y error (+) column".'),
                'Different sizes above and below? Tick "Asymmetric Error Bars" and also choose the (-) columns.',
                ('On an existing chart, open Chart Properties, then the Data tab, and select the series. '
                 'Choose "X Error Column:" and/or "Y Error Column:". With "Asymmetric Error Bars" ticked these become "X Error (+) Column:" '
                 'and "Y Error (+) Column:", and "X Error (-) Column:" and "Y Error (-) Column:" appear.'),
                (f"On a {_ERROR_BAR_OVERLAY_CHART_TYPES} chart, the chart's own series has no error bars, but a Line or Scatter series "
                 'added to it can: on the Data tab click "+ Add series", set its "Series Type:" to Line or Scatter, then choose its error '
                 "columns as above."),
                ('To style them, open the Style tab, choose the series in the drop-down at the top, and use the "Error Bars" card: '
                 '"Direction:" (Both, Above (+) or Below (-)), "Color:" and "Cap Size:".'),
            ),
            explanation=(
                "An error column holds one number per row: the size of the error for that point. With Asymmetric Error Bars off, one column "
                'is used and the "Direction:" setting on the Style tab decides whether the bar goes above, below or both. '
                "With it on, the (+) column gives the size above and the (-) column the size below.\n\n"
                'The "Error Bars" card on the Style tab appears only once the series has an error column. '
                f"The error columns appear on the Data tab only for {_ERROR_BAR_SERIES_TYPES} series. Other series, such as "
                'Histogram, Pie, Vector and the 3-D types, have no error bars.\n\n'
                'A fit can show a shaded confidence band. On the Data tab, first choose "Confidence Lower Column (optional):" and '
                '"Confidence Upper Column (optional):", then set "Series Type:" to "Fit" (it is greyed out on chart types without fits). '
                'The two columns stay editable on the fit afterwards. A fit with these columns gets a '
                '"Confidence Band" card on the Style tab for its colour and opacity.'
            ),
            keywords=(
                "error bar", "error bars", "errorbar", "uncertainty", "error", "asymmetric", "confidence band", "confidence interval", "caps",
                "standard deviation",
            ),
            related=(CHART_TOPIC_WIZARD_DATA, CHART_TOPIC_SERIES, CHART_TOPIC_STYLE, PANEL_TOPIC_CHART_PROPERTIES),
        ),
        HelpTopic(
            id=CHART_TOPIC_STYLE,
            title="Style a chart",
            category=HelpCategory.CHARTS,
            summary="Change colours, fonts, sizes and line, marker and fill styles on the Style tab of Chart Properties.",
            steps=(
                ('Open a chart tab, click the line-chart icon in the sidebar (its tooltip reads "Chart Properties panel") '
                 "and open the Style tab."),
                'Use the drop-down at the top to choose what to style: "Chart", "Axes", or one of your series.',
                "Change the settings in the cards that appear. The chart updates as you go.",
                'Click "Apply" to keep the changes as one undo step, or "Revert" to go back (see the Chart Properties panel topic).',
            ),
            explanation=(
                'Chart: the cards are "Font Size" (title and subtitle sizes, bold, italic, font and colours), "Padding", "Size", "DPI" and '
                '"Background" (figure and plot area, each with a "Transparent" switch).\n\n'
                'Axes: choose X, Y₁ (or Y₂ when a series uses it) and style the "Axis title", "Tick values" and "Colors" cards '
                "(spine and tick colours). Axes have no style when the chart is a Pie.\n\n"
                'A series: you see only the cards that fit its type. These can include "Line" (colour, style, width, opacity), "Markers", '
                '"Fill" (Line and Scatter), "Value Labels" (Line, Scatter, Bar and Stacked Bar; use "Label points:" to label only some points), '
                '"Error Bars", "Twin Y Column", "Density", "Box", "Pie", "Vector" and "Heatmap Rendering". '
            ),
            keywords=(
                "style", "color", "colour", "font", "line width", "marker", "fill", "background", "transparent", "opacity", "appearance",
                "format chart", "value labels", "size", "customize",
            ),
            related=(PANEL_TOPIC_CHART_PROPERTIES, CHART_TOPIC_AXES, CHART_TOPIC_LEGEND, CHART_TOPIC_SERIES, CHART_TOPIC_ERROR_BARS,
                     CHART_TOPIC_SAVE_IMAGE),
        ),
        HelpTopic(
            id=CHART_TOPIC_AXES,
            title="Axes, scales, ticks and grid",
            category=HelpCategory.CHARTS,
            summary="Set axis labels, linear or log scale, the range, tick marks and grid lines on the Axes tab of Chart Properties.",
            steps=(
                ('Open a chart tab, click the line-chart icon in the sidebar (its tooltip reads "Chart Properties panel") '
                 "and open the Axes tab."),
                'Click an axis button at the top: "X" or "Y₁". "Y₂" appears when a series uses the secondary axis, and "Z" on 3-D charts.',
                'Type the axis name in "Label:". It can contain math such as $x^2$.',
                'Choose "Linear" or "Log". With "Log" you can also choose the "Base:" (10, 2, e (natural log) or Custom...).',
                'Under "Range", the "Auto" switch picks the range from your data. Turn it off to type your own "Min:" and "Max:".',
                ('Under "Ticks", choose how the tick marks are placed ("Auto", "Count" or "Step"), the number "Format:", and the "Direction:" '
                 '(Out, In, In & Out). Turn on "Show grid" for grid lines, "Minor ticks" for the small marks and "Minor grid" for their lines.'),
            ),
            explanation=(
                "The Y axes also have a Left or Right control that puts the axis on that side of the chart. "
                'The "Copy settings to Y axis" button copies the shown Y axis settings (except its label) to the other Y axis.\n\n'
                'A "Color" button appears when a series is coloured by a value (Color Map, Heatmap, 3D Surface and 3D Triangulated Surface). '
                'It opens the "Color Map" card with "Colormap:", "Show colorbar:", "Colorbar label:" and "Auto scale:" '
                '(turn it off to set the colour "Min:" and "Max:"). On 3-D charts, the "3D View" card sets "Elevation:" and "Azimuth:", the '
                "angle the chart starts from. You can also drag a 3-D chart to rotate it, but a drag is not saved.\n\n"
                'A Pie chart has no axes. The tab then reads "This chart type has no axes to configure. Its title, subtitle and legend are set on '
                'the Chart and Legend tabs."'
            ),
            keywords=(
                "axes", "axis", "log scale", "logarithmic", "linear", "scale", "range", "limits", "min", "max", "ticks", "tick", "gridlines",
                "grid lines", "grid", "minor ticks", "axis label", "colorbar", "colormap", "elevation", "azimuth", "y2", "secondary axis",
            ),
            related=(PANEL_TOPIC_CHART_PROPERTIES, CHART_TOPIC_STYLE, CHART_TOPIC_MATH_TEXT, CHART_TOPIC_SERIES, CHART_TOPIC_VIEW),
        ),
        HelpTopic(
            id=CHART_TOPIC_LEGEND,
            title="Legend",
            category=HelpCategory.CHARTS,
            summary="Show, hide and place the legend on the Legend tab of Chart Properties.",
            steps=(
                ('Open a chart tab, click the line-chart icon in the sidebar (its tooltip reads "Chart Properties panel") '
                 "and open the Legend tab."),
                'Use the "Show legend" switch to show or hide the legend. The other legend settings are hidden while it is off.',
                ('Choose a "Position:". It can be inside the chart, such as Upper Right or Best, or outside: "Outside Right", "Outside Top" or '
                 '"Outside Bottom".'),
                ('For full control choose "Custom..." and set "X:", "Y:" and "Anchor:". '
                 'X and Y run from 0 to 1 across the plot area, with (0, 0) at the bottom left. "Anchor:" picks which point of the legend box '
                 '(a corner, the middle of an edge or the centre) is placed there.'),
                'Adjust the "Font Size:", the number of "Columns:" and the "Font family:".',
                'Use the "Frame" card to turn the frame on or off and, when it is on, to set its "Background:" colour and "Opacity:".',
            ),
            explanation=(
                'The text shown for each series comes from its "Label:" on the Data tab, so rename a series there to rename its legend entry. '
                'A Pie chart is different: its legend lists one entry per wedge, named by the values in the series\' '
                '"Labels Column (optional):", and its "Label:" is not used. To rename pie entries, edit those values in the dataset, or '
                'choose a different labels column. Without a labels column the wedges have no names to list. '
                "When you create a chart, the wizard's Labels step has a \"Show legend\" switch for the same setting.\n\n"
                "Clicking a legend entry on the chart selects that series in the panel."
            ),
            keywords=(
                "legend", "key", "legend position", "outside legend", "legend frame", "legend font", "legend columns", "hide legend", "series name",
            ),
            related=(PANEL_TOPIC_CHART_PROPERTIES, CHART_TOPIC_SERIES, CHART_TOPIC_STYLE, CHART_TOPIC_CREATE),
        ),
        HelpTopic(
            id=CHART_TOPIC_MATH_TEXT,
            title="Math in titles and labels",
            category=HelpCategory.CHARTS,
            summary="Put maths, such as powers, subscripts and Greek letters, in chart titles, subtitles and axis labels by writing it between $ signs.",
            steps=(
                "Type the text you want, and put the maths between two dollar signs. For example: $x^2$",
                ('Type it in the Title and Subtitle boxes of the chart wizard\'s Labels step, in "Title:" and "Subtitle:" on the Chart tab '
                 'of Chart Properties, or in "Label:" on the Axes tab.'),
                "Look at the chart. The maths is drawn as proper symbols.",
            ),
            explanation=(
                "The notation is matplotlib's math text, which looks like LaTeX. Some examples:\n"
                "$x^2$ gives x squared. $v_0$ gives v with a small 0 below it. $\\alpha$ gives the Greek letter alpha. "
                "$\\Delta t$ (s) gives the Greek capital delta followed by t, then the plain text (s).\n\n"
                "Text outside the dollar signs stays plain. Every $ needs a partner, and commands such as \\alpha must be spelled correctly.\n\n"
                "If the maths cannot be read, for example an unmatched $ or an unknown command, PandaPlot does not stop. "
                "All the text on the chart is then shown as you typed it, dollar signs included, until you fix the problem."
            ),
            keywords=("latex", "math", "maths", "subscript", "superscript", "greek", "symbol", "formula", "equation", "mathtext", "alpha", "delta"),
            related=(CHART_TOPIC_CREATE, CHART_TOPIC_AXES, PANEL_TOPIC_CHART_PROPERTIES, CHART_TOPIC_LEGEND),
        ),
        HelpTopic(
            id=CHART_TOPIC_VIEW,
            title="Work with the chart tab",
            category=HelpCategory.CHARTS,
            summary="What the buttons above the chart do: Refresh, Reset, Reset Zoom, Swap X/Y, and matplotlib's pan, zoom and save tools.",
            steps=(),
            explanation=(
                'Our buttons: "Refresh" reloads the data from your datasets and redraws the chart. '
                '"Reset Zoom" zooms back out to show all the data. '
                f'"Swap X/Y" exchanges the X and Y axes, including their titles, scales and ranges. It appears only for {_SWAP_CHART_TYPES} '
                "charts. When it cannot run, the line under the chart says why, but only briefly. The reasons include: there are no series yet, a series is on "
                "the secondary Y axis, a series is plotted against the row index (it has no X column), a series has no Y column, "
                "or a series is of a type that cannot be swapped. You can undo a swap with Edit > Undo.\n\n"
                '"Reset" puts all chart-level settings back to their defaults: the title (back to the chart name), subtitle, axes, legend, '
                "grid, size, DPI, fonts, backgrounds and the histogram bin count. Your series and their styles are kept, and so is the chart "
                "type. There is no confirmation, and Reset cannot be undone: Edit > Undo will not bring the old settings back. "
                "Think twice before you click it.\n\n"
                "Next to them are matplotlib's own tools. Pan and Zoom let you move around and zoom in with the mouse; "
                'use "Reset Zoom" to zoom back out. "Subplots" and "Customize" are there too, but what you change with them is not saved and is '
                "replaced the next time the chart redraws, so use the Style and Axes tabs instead. The Save button saves an image "
                "(see the save-image topic). As you move the mouse over the chart, the (x, y) readout in the toolbar shows the position.\n\n"
                "On a 3-D chart, drag the chart with the mouse to rotate it. The rotation is not saved; set Elevation and Azimuth on the Axes tab "
                "for a view that is. While Pan or Zoom is active, clicking a series does not select it."
            ),
            keywords=(
                "toolbar", "refresh", "reset", "reset zoom", "zoom", "pan", "swap axes", "swap x y", "flip axes", "undo", "restore defaults",
                "cursor", "coordinates", "rotate", "3d", "default settings",
            ),
            related=(CHART_TOPIC_AXES, CHART_TOPIC_SAVE_IMAGE, PANEL_TOPIC_CHART_PROPERTIES, CHART_TOPIC_STYLE),
        ),
        HelpTopic(
            id=CHART_TOPIC_SAVE_IMAGE,
            title="Save a chart as an image",
            category=HelpCategory.CHARTS,
            summary="Use the Save button on the chart toolbar to write the chart to a picture file such as PNG, PDF or SVG.",
            steps=(
                "Open the chart tab.",
                ('Optional: set the picture size and sharpness. In Chart Properties open the Style tab, choose "Chart" in the drop-down at the top, '
                 'and use the "Size" and "DPI" cards.'),
                'Click the Save button (the floppy-disk icon, tooltip "Save the figure") in the toolbar above the chart.',
                "In the file window, choose a folder, type a file name and pick the format, for example PNG, PDF or SVG.",
                "Click Save to write the file.",
            ),
            explanation=(
                'There is no separate export menu or dialog: the Save button on the chart toolbar is how you save a chart as an image. '
                'The "Size" card offers ready-made sizes, "Custom" (type a width and height) and "Use app default". '
                'The "DPI" card offers 100, 150 and 300 dpi, "Custom" and "Use app default". A higher DPI gives more detail and a larger file. '
                'The hint on the Size card reads "Size affects export & default fonts".\n\n'
                'To put a chart into a note, open the note, click "Artefacts" on the note toolbar, click "Insert Chart...", pick the chart, '
                'choose a "Snapshot DPI:" and click "Insert Chart". The note gets a picture of the chart as it looks at that moment. '
                'The Artefacts window has a "Refresh" button to update the picture later.'
            ),
            keywords=(
                "export", "save", "save image", "png", "pdf", "svg", "jpg", "image", "picture", "dpi", "resolution", "size", "download",
                "save figure", "report", "presentation", "note", "insert chart",
            ),
            related=(CHART_TOPIC_STYLE, CHART_TOPIC_VIEW, PANEL_TOPIC_CHART_PROPERTIES, CHART_TOPIC_CREATE),
        ),
    ]

