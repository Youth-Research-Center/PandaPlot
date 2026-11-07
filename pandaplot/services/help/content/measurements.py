"""Help topics for the Analyze Measurements wizard."""

from pandaplot.services.help.help_types import PANEL_TOPIC_DESCRIPTIVE, HelpCategory, HelpTopic

TOPIC_ANALYZE = "measurements.analyze"


def topics() -> list[HelpTopic]:
    """Return the help topics of this module.

    Returns:
        The topics, in display order.
    """
    return [
        HelpTopic(
            id=TOPIC_ANALYZE,
            title="Analyze Measurements",
            category=HelpCategory.MEASUREMENTS,
            summary=(
                "Turns a table of repeated measurements into a summary: for every setting you controlled, "
                "the number of measurements, their mean, standard deviation and standard error."
            ),
            steps=(
                ('Open the dataset and click the "Analyze Measurements" button below the table. '
                'You can also right-click the dataset in the Project Explorer and choose "Analyze Measurements...".'),
                ('On the "Assign column roles" page, give every column a Role: Unused, Controlled, Fixed or Measured. '
                "PandaPlot suggests roles from the column names and values, so check them."),
                "For each Measured column, check the name in Measured variable. Columns with the same name are treated as repeats of one quantity.",
                "Click Next. This is possible once there is at least one Controlled column, at least one Measured column and every Measured column has a name.",
                'On the "Review summary" page, read the message about excluded values, check the table, and edit the Result dataset name if you like.',
                'Click Finish to add the summary as a new dataset. "Plot a Graph" adds it in the same way and then opens the chart wizard for it.',
            ),
            explanation=(
                "A typical experiment sets one quantity on purpose, repeats the measurement several times, and records the results. "
                "The wizard needs to know which columns are which.\n\n"
                "Controlled columns are the settings you chose or varied on purpose, such as concentration or time. "
                "Rows with the same controlled values form one group.\n\n"
                "Fixed columns are things that were kept the same for the whole experiment, such as the temperature. "
                "They must have a single value in the data. If a Fixed column has two or more different values, "
                "the wizard tells you and asks you to correct the data or choose another role. "
                "A Fixed column with no values at all is refused too, because its constant value cannot be checked. "
                "Some missing values in a Fixed column are allowed and are only counted.\n\n"
                "Measured columns hold the numbers you measured. If your repeats are in separate columns, such as trial_1, trial_2 and trial_3, "
                "give them the same Measured variable name (PandaPlot suggests one when the names differ only by a number at the end) "
                "and they are summarised together.\n\n"
                "The summary has one row for each group and each measured variable. Its columns are the Controlled columns, "
                "then the Fixed columns, then Measured variable, Count, Mean, Standard deviation and Standard error. "
                "Standard deviation and standard error need at least two values; otherwise they are left empty.\n\n"
                "Rows with a missing Controlled value are left out. Missing, non-numeric and infinite measured values are left out of the statistics. "
                "The Review summary page tells you how many were excluded.\n\n"
                "Your original dataset keeps its data. The roles you chose are saved with it, so the wizard remembers them next time. "
                'The summary is a new dataset in the same folder, named "<dataset> - Measurement Summary" unless you change it. '
                "You can undo the analysis with Edit > Undo."
            ),
            parameters=(
                ("Controlled", "A setting you chose or varied on purpose. Rows with the same controlled values are grouped."),
                ("Fixed", "A value kept the same throughout. Must have only one observed value."),
                ("Measured", "A numeric measurement to summarise."),
                ("Unused", "The column is ignored."),
                ("Measured variable", "The name of the quantity a Measured column records. The same name on several columns pools them as repeats."),
                ("Result dataset name", "Name of the new summary dataset."),
                ("Plot a Graph", "Finish and then open the chart wizard for the summary dataset."),
            ),
            formula=(
                "Mean = (x₁ + x₂ + … + xₙ) / n\n"
                "Standard deviation = √( Σ (xᵢ - mean)² / (n - 1) )\n"
                "Standard error = standard deviation / √n"
            ),
            example=(
                "A table has the columns dose, trial_1, trial_2 and trial_3. Set dose to Controlled and the trial columns to Measured "
                'with the Measured variable "response". The summary has one row per dose with the count, mean, '
                "standard deviation and standard error of the three trials."
            ),
            keywords=(
                "measurements", "replicates", "repeated measurements", "error bars", "standard error", "standard deviation",
                "mean", "group by", "summary table", "controlled variable", "measured variable", "experiment",
            ),
            related=(PANEL_TOPIC_DESCRIPTIVE, "descriptive.overview"),
        ),
    ]
