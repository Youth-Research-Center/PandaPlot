"""Tests for StyleTab's Color Map card (Colormap/Heatmap chart types).

This is the fix for PR #156's review comments: changing to a Colormap/
Heatmap series must correctly hide the Line/Marker cards (previously
broken) via the same spec-driven mechanism _update_target_cards_visibility
already uses for Vector -- not a new hardcoded chart-type check.
"""
import sys

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.marker_style import MarkerStyle
from pandaplot.models.chart.series_style import ColormapSeriesStyle, HeatmapSeriesStyle, ScatterSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import DataSeries


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def _tab():
    # Qt only reports isVisible() truthfully for a widget whose top-level
    # ancestor has actually been shown (see test_style_tab_vector.py's same
    # pattern) -- without this, isVisible() is always False regardless of
    # setVisible() calls.
    tab = StyleTab(app_context=None)
    tab.show()
    return tab


def test_heatmap_gridding_card_shown_for_heatmap_series_marker_line_fill_hidden():
    tab = _tab()
    series = DataSeries(
        dataset_id="ds1", series_type=SeriesType.HEATMAP, style=HeatmapSeriesStyle(),
    )
    tab.set_chart_type(ChartType.HEATMAP)
    tab.set_selected("series", series)

    assert tab.heatmap_gridding_card.isVisible() is True
    assert tab.heatmap_gridding_control.isVisible() is True
    # Heatmap's marker_mode is "unsupported" -- Marker/Line/Fill all hidden.
    assert tab.marker_card.isVisible() is False
    assert tab.line_card.isVisible() is False
    assert tab.fill_card.isVisible() is False


def test_heatmap_gridding_card_hidden_for_colormap_series_marker_stays_visible():
    """Colormap needs no gridding (SeriesTypeSpec.supports_gridding is
    False for it) -- the card doesn't show at all, unlike Heatmap. Marker
    card stays visible (marker_mode == "required" for Colormap); line/fill
    cards stay hidden -- the fix for PR #156's review comments about broken
    line/marker controls on these series types."""
    tab = _tab()
    series = DataSeries(
        dataset_id="ds1", series_type=SeriesType.COLORMAP, style=ColormapSeriesStyle(),
    )
    tab.set_chart_type(ChartType.COLORMAP)
    tab.set_selected("series", series)

    assert tab.heatmap_gridding_card.isVisible() is False
    assert tab.marker_card.isVisible() is True
    assert tab.line_card.isVisible() is False
    assert tab.fill_card.isVisible() is False
    assert tab.marker_match_line_toggle.isVisible() is True


def test_markers_cannot_be_disabled_for_scatter_or_colormap():
    """Scatter/Colormap have marker_mode == "required" -- markers are the
    ONLY thing they draw, so the on/off toggle that lets an optional-marker
    series (Line) turn markers off entirely must not be offered for them."""
    tab = _tab()
    for series_type, style, chart_type in (
        (SeriesType.SCATTER, ScatterSeriesStyle(), ChartType.SCATTER),
        (SeriesType.COLORMAP, ColormapSeriesStyle(), ChartType.COLORMAP),
    ):
        series = DataSeries(dataset_id="ds1", series_type=series_type, style=style)
        tab.set_chart_type(chart_type)
        tab.set_selected("series", series)

        assert tab.markers_enabled_toggle.isVisible() is False, series_type
        # Shape/size/edge-width remain fully available regardless.
        assert tab.marker_shape_control.isVisible() is True, series_type
        assert tab.marker_size_slider.isVisible() is True, series_type
        assert tab.marker_edge_width_slider.isVisible() is True, series_type


def test_markers_enabled_toggle_still_shown_for_line_series():
    """Sanity check: Line's marker_mode is "optional" -- the on/off toggle
    must still be offered there, unlike Scatter/Colormap."""
    tab = _tab()
    series = DataSeries(dataset_id="ds1", series_type=SeriesType.LINE)
    tab.set_chart_type(ChartType.LINE)
    tab.set_selected("series", series)

    assert tab.markers_enabled_toggle.isVisible() is True


def test_marker_match_toggle_relabeled_for_colormap():
    """The shared "Match line"/"Match point color" toggle row is relabeled
    per target: Colormap's fill varies per point (matched via
    edgecolors="face" in the renderer), which is a materially different
    thing to match than Line's single style.color."""
    tab = _tab()
    line_series = DataSeries(dataset_id="ds1", series_type=SeriesType.LINE)
    tab.set_chart_type(ChartType.LINE)
    tab.set_selected("series", line_series)
    assert tab.marker_match_line_label.text() == "Match line:"

    colormap_series = DataSeries(
        dataset_id="ds1", series_type=SeriesType.COLORMAP, style=ColormapSeriesStyle(),
    )
    tab.set_chart_type(ChartType.COLORMAP)
    tab.set_selected("series", colormap_series)
    assert tab.marker_match_line_label.text() == "Match point color:"


def test_marker_fill_color_hidden_for_colormap_series_edge_color_toggle_controlled():
    """render_colormap_series always drives fill color from z_data through
    the colormap (c=series_data.z_data) -- style.marker.marker_color is
    never read, so the "Color:" row must be hidden outright rather than
    shown as a control that silently does nothing. Edge color IS read
    (edgecolors=marker_edge_color or "face") -- its row's visibility
    follows the "Match point color" toggle: hidden while matching (nothing
    to configure -- it's derived per-point), shown to pick a literal value
    once unchecked. Shape/size always apply and stay visible regardless."""
    tab = _tab()
    series = DataSeries(
        dataset_id="ds1", series_type=SeriesType.COLORMAP, style=ColormapSeriesStyle(),
    )
    tab.set_chart_type(ChartType.COLORMAP)
    tab.set_selected("series", series)

    assert tab.marker_card.isVisible() is True
    assert tab.marker_color_row.isVisible() is False
    assert tab.marker_color_label.isVisible() is False
    assert tab.marker_shape_control.isVisible() is True
    assert tab.marker_size_slider.isVisible() is True

    # Fresh ColormapSeriesStyle() has marker_edge_color == "" (MarkerStyle's
    # default) -- "Match point color" starts checked, edge row starts hidden.
    assert tab.marker_match_line_toggle.isChecked() is True
    assert tab.marker_edge_color_row.isVisible() is False
    assert tab.marker_edge_color_label.isVisible() is False

    # Unchecking reveals the row so a literal edge color can be picked.
    tab.marker_match_line_toggle.setChecked(checked=False)
    assert tab.marker_edge_color_row.isVisible() is True
    assert tab.marker_edge_color_label.isVisible() is True


def test_apply_series_style_writes_explicit_colormap_edge_color_when_not_matching():
    tab = _tab()
    series = DataSeries(
        dataset_id="ds1", series_type=SeriesType.COLORMAP, style=ColormapSeriesStyle(),
    )
    tab.set_chart_type(ChartType.COLORMAP)
    tab.set_selected("series", series)

    tab.marker_match_line_toggle.setChecked(checked=False)
    tab.marker_edge_color_row.setCurrentColor("#ff00ff")
    tab.apply_series_style_to(series)

    assert series.style.marker.marker_edge_color == "#ff00ff"


def test_apply_series_style_clears_colormap_edge_color_when_matching():
    tab = _tab()
    series = DataSeries(
        dataset_id="ds1", series_type=SeriesType.COLORMAP,
        style=ColormapSeriesStyle(marker=MarkerStyle(marker_edge_color="#ff00ff")),
    )
    tab.set_chart_type(ChartType.COLORMAP)
    tab.set_selected("series", series)
    assert tab.marker_match_line_toggle.isChecked() is False  # loaded from the non-empty edge color

    tab.marker_match_line_toggle.setChecked(checked=True)
    tab.apply_series_style_to(series)

    assert series.style.marker.marker_edge_color == ""


def test_marker_fill_color_visible_for_a_plain_line_series_target():
    """Sanity check that the new hide-for-z-driven-series behavior doesn't
    regress the ordinary case: a Line series' marker fill color must still
    be shown once markers are enabled."""
    tab = _tab()
    series = DataSeries(dataset_id="ds1", series_type=SeriesType.LINE)
    tab.set_chart_type(ChartType.LINE)
    tab.set_selected("series", series)
    tab.markers_enabled_toggle.setChecked(checked=True)
    tab.marker_match_line_toggle.setChecked(checked=False)
    tab._update_marker_controls_enabled()

    assert tab.marker_color_row.isVisible() is True
    assert tab.marker_color_label.isVisible() is True


def test_heatmap_gridding_card_hidden_for_a_line_series_target():
    tab = _tab()
    series = DataSeries(dataset_id="ds1")
    tab.set_chart_type(ChartType.LINE)
    tab.set_selected("series", series)

    assert tab.heatmap_gridding_card.isVisible() is False


def test_heatmap_gridding_resolution_hidden_for_exact_grid_mode_shown_for_binned():
    tab = _tab()
    series = DataSeries(
        dataset_id="ds1", series_type=SeriesType.HEATMAP,
        style=HeatmapSeriesStyle(heatmap_gridding="grid"),
    )
    tab.set_chart_type(ChartType.HEATMAP)
    tab.set_selected("series", series)

    assert tab.heatmap_resolution_spin.isVisible() is False

    tab.heatmap_gridding_control.setCurrentIndex(tab.heatmap_gridding_control.findData("binned"))

    assert tab.heatmap_resolution_spin.isVisible() is True


def test_heatmap_gridding_resolution_hidden_for_triangulated_mode():
    """"Triangulated" bypasses gridding entirely (tripcolor/tricontour/
    tricontourf operate on the raw points), so it has no resolution to
    configure either -- same as "grid"."""
    tab = _tab()
    series = DataSeries(
        dataset_id="ds1", series_type=SeriesType.HEATMAP,
        style=HeatmapSeriesStyle(heatmap_gridding="triangulated"),
    )
    tab.set_chart_type(ChartType.HEATMAP)
    tab.set_selected("series", series)

    assert tab.heatmap_resolution_spin.isVisible() is False


def test_heatmap_contour_controls_hidden_for_mesh_mode():
    tab = _tab()
    series = DataSeries(
        dataset_id="ds1", series_type=SeriesType.HEATMAP,
        style=HeatmapSeriesStyle(render_mode="mesh"),
    )
    tab.set_chart_type(ChartType.HEATMAP)
    tab.set_selected("series", series)

    assert tab.heatmap_contour_levels_spin.isVisible() is False
    assert tab.heatmap_contour_line_labels_toggle.isVisible() is False
    assert tab.heatmap_contour_line_width_slider.isVisible() is False


def test_heatmap_contour_levels_shown_but_line_labels_hidden_for_filled_only():
    """No lines are drawn for a lines-less filled contour, so there's
    nothing for "line labels" to label, and no line to set a width on."""
    tab = _tab()
    series = DataSeries(
        dataset_id="ds1", series_type=SeriesType.HEATMAP,
        style=HeatmapSeriesStyle(render_mode="contour_filled"),
    )
    tab.set_chart_type(ChartType.HEATMAP)
    tab.set_selected("series", series)

    assert tab.heatmap_contour_levels_spin.isVisible() is True
    assert tab.heatmap_contour_line_labels_toggle.isVisible() is False
    assert tab.heatmap_contour_line_width_slider.isVisible() is False


def test_heatmap_contour_line_labels_shown_when_lines_are_drawn():
    tab = _tab()
    series = DataSeries(
        dataset_id="ds1", series_type=SeriesType.HEATMAP,
        style=HeatmapSeriesStyle(render_mode="contour_lines"),
    )
    tab.set_chart_type(ChartType.HEATMAP)
    tab.set_selected("series", series)

    assert tab.heatmap_contour_line_labels_toggle.isVisible() is True
    assert tab.heatmap_contour_line_width_slider.isVisible() is True

    tab.heatmap_render_mode_control.setCurrentIndex(
        tab.heatmap_render_mode_control.findData("contour_filled_lines"))
    assert tab.heatmap_contour_line_labels_toggle.isVisible() is True
    assert tab.heatmap_contour_line_width_slider.isVisible() is True


def test_apply_and_load_heatmap_contour_fields_round_trip():
    tab = _tab()
    series = DataSeries(
        dataset_id="ds1", series_type=SeriesType.HEATMAP, style=HeatmapSeriesStyle(),
    )
    tab.set_chart_type(ChartType.HEATMAP)
    tab.set_selected("series", series)

    tab.heatmap_gridding_control.setCurrentIndex(tab.heatmap_gridding_control.findData("triangulated"))
    tab.heatmap_render_mode_control.setCurrentIndex(
        tab.heatmap_render_mode_control.findData("contour_filled_lines"))
    tab.heatmap_contour_levels_spin.setValue(20)
    tab.heatmap_contour_line_labels_toggle.setChecked(checked=True)
    tab.heatmap_contour_line_width_slider.setValue(4.5)

    tab.apply_series_style_to(series)

    assert series.style.heatmap_gridding == "triangulated"
    assert series.style.render_mode == "contour_filled_lines"
    assert series.style.contour_levels == 20
    assert series.style.contour_line_labels is True
    assert series.style.contour_line_width == 4.5

    tab2 = _tab()
    tab2.set_chart_type(ChartType.HEATMAP)
    tab2.set_selected("series", series)

    assert tab2.heatmap_gridding_control.currentValue() == "triangulated"
    assert tab2.heatmap_render_mode_control.currentValue() == "contour_filled_lines"
    assert tab2.heatmap_contour_levels_spin.value() == 20
    assert tab2.heatmap_contour_line_labels_toggle.isChecked() is True
    assert tab2.heatmap_contour_line_width_slider.value() == 4.5


def test_apply_and_load_series_style_round_trip_colormap_marker_fields():
    """Colormap keeps its Marker card populated/applied (marker_mode ==
    "required") -- this is unaffected by Color Map config moving to
    chart-level."""
    tab = _tab()
    series = DataSeries(
        dataset_id="ds1", series_type=SeriesType.COLORMAP, style=ColormapSeriesStyle(),
    )
    tab.set_chart_type(ChartType.COLORMAP)
    tab.set_selected("series", series)

    tab.marker_size_slider.setValue(12.0)

    tab.apply_series_style_to(series)

    assert series.style.marker.marker_size == 12.0
    # ColormapSeriesStyle has no color/line-style fields -- must not be
    # spuriously created as a dynamic attribute by the fallthrough.
    assert not hasattr(series.style, "line_style")
    assert not hasattr(series.style, "colormap")
