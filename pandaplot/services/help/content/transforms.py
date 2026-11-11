"""Help topics for transforms, expressions and formula columns.

The list of names an expression can use and the ready-made "Insert function"
entries are read from the expression engine when ``topics()`` is called, so
the help always matches what the transform panels accept.
"""

from pandaplot.services.help.help_types import (
    PANEL_TOPIC_CHART_TRANSFORM,
    PANEL_TOPIC_PREPROCESSING,
    PANEL_TOPIC_TRANSFORM,
    HelpCategory,
    HelpTopic,
)
from pandaplot.services.transform.expression_engine import allowed_expression_names, get_transformation_templates

TOPIC_PANEL = "transforms.panel"
TOPIC_EXPRESSIONS = "transforms.expressions"
TOPIC_NAMES = "transforms.names"
TOPIC_INSERT_FUNCTION = "transforms.insert_function"
TOPIC_FORMULA_COLUMNS = "transforms.formula_columns"
TOPIC_CHART_TRANSFORM = "transforms.chart_transform"


def topics() -> list[HelpTopic]:
    """Return the help topics of this module.

    Returns:
        The topics, in display order.
    """
    names = ", ".join((*allowed_expression_names(), "math"))
    templates = tuple(
        (f"{category} > {entry['name']}", f"{entry['code']}  ({entry['description']})")
        for category, entries in get_transformation_templates().items()
        for entry in entries
    )
    return [
        HelpTopic(
            id=TOPIC_PANEL,
            title="Transform a column",
            category=HelpCategory.TRANSFORMS,
            summary="Makes a new column in a dataset by applying an expression to an existing column, for example doubling every value or taking its square root.",
            steps=(
                'Open the dataset and click the wrench icon in the sidebar (its tooltip reads "Transform Operations panel").',
                "Select the column to transform in Source Columns.",
                "Type a name for the result in New Column.",
                "Write an expression in Transform Function, using x for the selected column. For example: np.sqrt(x)",
                "Click Preview to check the first rows, then Apply.",
            ),
            explanation=(
                "The expression is calculated for the whole column at once, and the result becomes a new column at the end of the dataset. "
                'Your original column is not changed unless you tick "Replace existing column" and give the new column the same name as an existing one.\n\n'
                "If you select more than one source column, only the first one is used as x. "
                'The list marks it with "→ x" and marks the others "(not used)".\n\n'
                "Apply cannot be clicked until a source column, a new column name and an expression are filled in. "
                "If the expression has a mistake, the message appears in the preview box. "
                "A transform can be undone with Edit > Undo.\n\n"
                "The Type list in the panel only changes the example text in the function box. It does not change how the expression is calculated."
            ),
            parameters=(
                ("Source Columns", "The column the expression reads. Only the first selected column is used."),
                ("New Column", "The name of the result column. Filled in as <column>_transformed when you pick a column and the box is empty."),
                ("Replace existing column", "Overwrite a column that already has the New Column name instead of refusing."),
                ("Save as formula column", 'Remember the expression on the new column so it can be recomputed. See "Formula columns".'),
                ("Preview", "Shows sample results without changing the dataset. The rows list next to it sets 5, 10 or 20 rows."),
            ),
            example="Source column: temperature_c. Expression: x * 9 / 5 + 32. New Column: temperature_f.",
            keywords=("transform", "new column", "calculate", "derived column", "apply function", "column math"),
            related=(TOPIC_EXPRESSIONS, TOPIC_NAMES, TOPIC_INSERT_FUNCTION, TOPIC_FORMULA_COLUMNS, PANEL_TOPIC_TRANSFORM, PANEL_TOPIC_PREPROCESSING),
        ),
        HelpTopic(
            id=TOPIC_EXPRESSIONS,
            title="Writing an expression",
            category=HelpCategory.TRANSFORMS,
            summary="An expression is a short calculation, written like a formula in a spreadsheet, that gives one value for every row.",
            explanation=(
                "In the Transform panel, x is the whole selected column. value, column and data mean the same thing, "
                "and cols['name'] gives the column by the name it had when you wrote the expression. "
                "In the Chart Transform panel, x and y are the series' x and y values.\n\n"
                "You can use the usual operators (+ - * / ** %) and comparisons. "
                "Functions from NumPy (np) and pandas (pd) are available, and so are the methods of a column, "
                "such as x.mean(), x.std(), x.rank(), x.cumsum(), x.rolling(3).mean(), x.shift(1), x.str.upper() and x.dt.year.\n\n"
                "The result must be a column of values with one value per row. A single number is repeated on every row.\n\n"
                "An expression is one calculation, not a program. Assignments, import statements, names that start with an underscore, "
                "and anything that reads or writes files are refused, and PandaPlot tells you why. "
                'Use f-strings such as f"{x}" instead of .format() to build text.\n\n'
                'Click the ? button next to "Insert function" to show the names you can use, or open "Names you can use in an expression".'
            ),
            example=(
                "x * 2                        double every value\n"
                "(x - x.mean()) / x.std()     z-score of the column\n"
                "np.sqrt(x)                   square root\n"
                "x.rolling(3).mean()          3-point moving average\n"
                "np.where(x > 0, x, 0)        keep positive values, replace the rest with 0"
            ),
            keywords=("expression", "formula", "function", "syntax", "variables", "x", "cols", "numpy", "pandas", "z-score", "moving average", "rolling"),
            related=(TOPIC_NAMES, TOPIC_INSERT_FUNCTION, TOPIC_PANEL, TOPIC_CHART_TRANSFORM),
        ),
        HelpTopic(
            id=TOPIC_NAMES,
            title="Names you can use in an expression",
            category=HelpCategory.TRANSFORMS,
            summary="The functions and modules an expression can call. Anything not on this list is refused.",
            explanation=(
                f"Names: {names}\n\n"
                "np is NumPy and pd is pandas, so np.sqrt(x), np.log(x) and pd.to_datetime(x) all work. "
                "Some of their functions are also available without the prefix, for example sqrt(x) and to_datetime(x). "
                "The rest of the list are everyday Python helpers such as abs, min, max, sum, len and round.\n\n"
                "x, y, value, column, data and cols are not in this list because they are the data of the transform itself. "
                "In the Preview of the Transform panel only x is known, so write x there. "
                "The methods of a column, such as x.mean() or x.str.upper(), are also always available.\n\n"
                "math (for example math.pi) works when you click Apply in the Transform panel and when a formula column is recomputed. "
                "It does not work in the Preview of the Transform panel or in the Chart Transform panel, so np.pi is the safer choice."
            ),
            keywords=("names", "functions", "allowed", "available", "np", "pd", "numpy", "pandas", "math", "builtin", "reference"),
            related=(TOPIC_EXPRESSIONS, TOPIC_INSERT_FUNCTION, TOPIC_PANEL),
        ),
        HelpTopic(
            id=TOPIC_INSERT_FUNCTION,
            title="Insert function menu",
            category=HelpCategory.TRANSFORMS,
            summary="Ready-made expressions you can insert into the function box instead of typing them.",
            steps=(
                'Click "Insert function" above the function box.',
                "Open a category and click an entry.",
                "The expression is inserted at the cursor, or fills the box if it is empty. Edit it to suit your data.",
            ),
            explanation=(
                "The Transform and Chart Transform panels share the same menu. "
                "In the Chart Transform panel the x in the inserted expression is replaced by the axis you chose as the Target, "
                "so with Target set to Y, x * 2 is inserted as y * 2."
            ),
            parameters=templates,
            keywords=("insert function", "templates", "ready-made", "examples", "z-score", "normalize", "uppercase", "year", "rank", "rolling mean"),
            related=(TOPIC_EXPRESSIONS, TOPIC_NAMES, TOPIC_PANEL, TOPIC_CHART_TRANSFORM),
        ),
        HelpTopic(
            id=TOPIC_FORMULA_COLUMNS,
            title="Formula columns",
            category=HelpCategory.TRANSFORMS,
            summary="A formula column remembers the expression that made it, so it can be recomputed later or kept up to date automatically.",
            steps=(
                "In the Transform panel, choose the source column and write the expression as usual.",
                'Tick "Save as formula column".',
                'Optional: tick "Live (recompute when sources change)" so the column updates by itself.',
                "Click Apply. The column header now shows an fx marker (fx live for a live column).",
            ),
            explanation=(
                "A normal transformed column keeps the values it was given. A formula column also stores its expression and its source column, "
                "and the expression is saved with the project.\n\n"
                'A plain formula column keeps its values until you recompute it. Right-click its column header and choose "Recompute formula column(s)". '
                "Hold the mouse over the header to see its expression.\n\n"
                "A live formula column recomputes whenever its source column changes, for example when you edit a cell or add rows. "
                "Because its values come from the formula, a live column is read-only. Edit its source column instead, and undo works as usual.\n\n"
                "The source is remembered by the column itself, so renaming the source column does not break the formula. "
                "A formula that would depend on itself, directly or through other formula columns, is refused.\n\n"
                'If you later apply a normal transform (without "Save as formula column") over the same column using "Replace existing column", '
                "it becomes a normal column again."
            ),
            parameters=(
                ("Save as formula column", "Store the expression on the new column so it can be recomputed."),
                ("Live (recompute when sources change)", "Recompute automatically whenever a source column changes. Makes the column read-only."),
                ("Recompute formula column(s)", "Column header right-click menu entry. Recalculates a plain formula column from its current sources."),
            ),
            example="Source column: length. Expression: x ** 2. With Live ticked, changing a value in length changes the matching value in the formula column.",
            keywords=("formula column", "live formula", "recompute", "fx", "spreadsheet", "dependent column", "automatic update"),
            related=(TOPIC_PANEL, TOPIC_EXPRESSIONS, PANEL_TOPIC_TRANSFORM),
        ),
        HelpTopic(
            id=TOPIC_CHART_TRANSFORM,
            title="Transform a chart series",
            category=HelpCategory.TRANSFORMS,
            summary="Changes the x or y values of a series on a chart with an expression and adds the result to the chart as a new series.",
            steps=(
                'Open the chart and click the wrench icon in the sidebar (its tooltip reads "Chart Transform panel").',
                "Choose the series or fitted curve to Transform.",
                "Under Target, choose Y or X for the values the expression will replace.",
                "Write the expression using x and y. For example: np.log10(y)",
                "Click Preview, then Apply.",
            ),
            explanation=(
                "Both x and y are always available in the expression. The Target decides which one is replaced by the result; the other stays as it is.\n\n"
                'Apply creates a new dataset with the unchanged axis and the transformed one (its heading ends in "(transformed)") '
                "and adds a series that uses it to the chart. The original series is not changed. "
                "When the source is a data series, the new series copies its type and style.\n\n"
                "The result must have exactly one value for every point of the series."
            ),
            parameters=(
                ("Transform", "The series or fitted curve to transform."),
                ("Replace", "Whether the result replaces the Y values or the X values."),
                ("Dataset name", "Name of the new dataset. Left empty, a name is suggested from the series."),
            ),
            example="Target Y, expression np.log10(y): the new series has the same x values and the base-10 logarithm of the y values.",
            keywords=("chart transform", "series transform", "log", "rescale", "normalize x", "axis values"),
            related=(TOPIC_EXPRESSIONS, TOPIC_NAMES, TOPIC_INSERT_FUNCTION, PANEL_TOPIC_CHART_TRANSFORM, TOPIC_PANEL),
        ),
    ]
