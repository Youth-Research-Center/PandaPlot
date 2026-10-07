"""Shared allows_fit guard for fit-related chart commands."""

import logging

from pandaplot.commands.base_command import CommandResult
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.chart.chart_type_spec import CHART_TYPE_SPECS
from pandaplot.models.project.items.chart import Chart


def reject_if_fit_disallowed(
    chart: Chart, *, logger: logging.Logger, ui_controller: UIController,
    action: str, dialog_title: str, on_disallowed: CommandResult,
) -> CommandResult | None:
    """Log a warning and show the standard "fits aren't available" dialog
    if `chart`'s type doesn't allow fits, returning `on_disallowed`;
    otherwise return None so the caller proceeds.

    Shared by ApplyFitCommand and ConvertSeriesToFitCommand's execute()/
    redo(), which both reject with the same dialog title/message per
    command but a different CommandResult depending on the call site
    (FAILURE from execute(), ABORTED from redo() -- see each redo()'s own
    docstring for why ABORTED matters there).
    """
    if chart.allows_fit:
        return None
    display_name = CHART_TYPE_SPECS[chart.chart_type].display_name
    logger.warning(
        "%s: chart '%s' is a %s chart, which doesn't allow fits",
        action, chart.id, display_name,
    )
    ui_controller.show_error_message(
        dialog_title, f"Fits aren't available on {display_name} charts."
    )
    return on_disallowed
