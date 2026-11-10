"""Shared "series/fit" combo-box population for chart-series-scoped panels.

Used by ChartAnalysisPanel and (#268) ChartTransformPanel: both offer the
same set of eligible sources -- line/scatter data series and fitted curves,
excluding series types with no meaningful ordered (x, y) curve (bar/hist/
vector/colormap/heatmap/3-D) -- and want the same combo item shape.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox

from pandaplot.gui.resources.item_icons import item_icon_name
from pandaplot.gui.resources.themed_icons import themed_icon
from pandaplot.models.chart.chart_type_spec import get_chart_type_spec, quick_plot_compatible
from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.project import Project
from pandaplot.models.state.app_context import AppContext
from pandaplot.utils.item_display_options import disambiguated_display_options

# Item data role holding the bundled icon name of a combo item, so `retint_combo_icons` can re-render the icon after a theme change.
ICON_NAME_ROLE = Qt.ItemDataRole.UserRole + 1
SERIES_ICON_NAME = item_icon_name("chart")
FIT_ICON_NAME = "waveform"
NEW_CHART_ICON_NAME = "plus"


def _add_icon_item(combo: QComboBox, app_context: AppContext, icon_name: str, text: str, data: object) -> None:
    """Append an item with a themed bundled icon and remember the icon name for `retint_combo_icons`."""
    combo.addItem(themed_icon(app_context, icon_name), text, data)
    combo.setItemData(combo.count() - 1, icon_name, ICON_NAME_ROLE)


def retint_combo_icons(combo: QComboBox, app_context: AppContext) -> None:
    """Re-render the icons of the items that `populate_*` gave an icon, for the current theme."""
    for row in range(combo.count()):
        icon_name = combo.itemData(row, ICON_NAME_ROLE)
        if icon_name is not None:
            combo.setItemIcon(row, themed_icon(app_context, icon_name))


def populate_series_fit_sources(combo: QComboBox, chart: Chart | None, *, app_context: AppContext) -> tuple[bool, bool]:
    """(Re)fill `combo` with the chart's eligible series/fit entries.

    Each item's data is the entry's real ``chart.data_series`` index --
    the same index for a plain series or a fit (fits live inline in that
    list, #304), so there's no separate "kind" tag to keep in sync with it
    (#419). Returns ``(has_sources, any_series_excluded)`` so the caller
    can set its own hint text/enabled state.
    """
    combo.blockSignals(True)  # noqa: FBT003 - Qt method rejects keyword args
    combo.clear()
    any_series_excluded = False
    if chart is not None:
        for i, series in enumerate(chart.data_series):
            if series.is_fit:
                # Listed by the fit pass below instead -- not "excluded".
                continue
            if not SERIES_TYPE_SPECS[series.series_type].supports_curve_analysis:
                any_series_excluded = True
                continue
            label = series.label or f"Series {i + 1}"
            _add_icon_item(combo, app_context, SERIES_ICON_NAME, label, i)
        fit_number = 0
        for i, series in enumerate(chart.data_series):
            if not series.is_fit:
                continue
            fit_number += 1
            label = series.label or f"Fit {fit_number}"
            _add_icon_item(combo, app_context, FIT_ICON_NAME, f"{label}  (fit)", i)
    combo.blockSignals(False)  # noqa: FBT003 - Qt method rejects keyword args
    return combo.count() > 0, any_series_excluded


def find_series_fit_combo_index(combo: QComboBox, index: int) -> int:
    """Row in `combo` (as populated by :func:`populate_series_fit_sources`)
    whose item data is ``index``, or -1 if there isn't one (e.g. the
    chart-canvas click was on a series type excluded from this combo, like
    bar/hist/vector/colormap/heatmap/3-D).
    """
    for i in range(combo.count()):
        if combo.itemData(i) == index:
            return i
    return -1


def populate_chart_target_combo(combo: QComboBox, project: "Project | None", *, app_context: AppContext) -> None:
    """(Re)fill `combo` with the "Plot result" destination choices:
    "New chart" (plus icon, data=None, always first and selected by default) followed
    by every chart in the project whose type allows a plotted analysis
    result (quick_plot_compatible) -- including the chart the analyzed
    series came from, now just one entry among others rather than an
    implicit default. Labels are disambiguated (folder-suffixed) when two
    compatible charts share a name, via disambiguated_display_options.
    """
    combo.blockSignals(True)  # noqa: FBT003 - Qt method rejects keyword args
    combo.clear()
    # The plus icon distinguishes this as an action (create a chart), not the name of
    # an existing chart called "New chart" -- easy to misread as the latter
    # sitting plainly alongside real chart names below it.
    _add_icon_item(combo, app_context, NEW_CHART_ICON_NAME, "New chart", None)
    if project is not None:
        compatible_charts = [
            item for item in project.get_all_items()
            if isinstance(item, Chart) and quick_plot_compatible(get_chart_type_spec(item.chart_type))
        ]
        for chart_id, display_name in disambiguated_display_options(compatible_charts, project):
            combo.addItem(display_name, chart_id)
    combo.setCurrentIndex(0)
    combo.blockSignals(False)  # noqa: FBT003 - Qt method rejects keyword args


def refresh_chart_target_combo_preserving_selection(combo: QComboBox, project: "Project | None", *, app_context: AppContext) -> None:
    """Like populate_chart_target_combo(), but keeps the current selection
    if it's still a valid entry afterward, instead of always resetting to
    "New chart". Use this for a refresh triggered by an unrelated
    background change (a different chart renamed/retyped/removed/added
    elsewhere) rather than the user's own chart/source context changing --
    populate_chart_target_combo() is still what _populate_sources() uses
    for the latter, where resetting to "New chart" is the documented,
    deliberate behavior (see the design spec).
    """
    previous = combo.currentData()
    populate_chart_target_combo(combo, project, app_context=app_context)
    if previous is not None:
        index = combo.findData(previous)
        if index >= 0:
            combo.setCurrentIndex(index)


def series_source_hint(*, has_sources: bool, any_series_excluded: bool) -> str:
    """Hint label text for the outcome of populate_series_fit_sources()."""
    if not has_sources:
        if any_series_excluded:
            # Operation-neutral wording: shared by ChartAnalysisPanel and
            # ChartTransformPanel, so it can't say "analysis" specifically.
            return (
                "This chart's series (bar/hist/vector/colormap/heatmap/3-D) "
                "aren't supported here -- add a line, scatter, or fit."
            )
        return "This chart has no data series or fits yet."
    if any_series_excluded:
        return "Line/scatter series and fitted curves of this chart -- other series types aren't shown."
    return "Data series and fitted curves of this chart."
