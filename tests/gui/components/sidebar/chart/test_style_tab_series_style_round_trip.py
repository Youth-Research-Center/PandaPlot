"""Tests for StyleTab.load_series_style()/apply_series_style_to()'s
round trip through DataSeries.style, replacing the pre-Phase-3c direct
flat-field reads/writes. Covers the 4 non-vector types' shared path plus
vector's separate branch, and the "match line color" "" -sentinel
convention that must survive the .style migration unchanged.
"""
import dataclasses
import sys

from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.marker_style import MarkerStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS
from pandaplot.models.project.items.chart import DataSeries


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _make_series(series_type, **overrides):
    """Build a DataSeries of the given type, routing any style-class field
    name in ``overrides`` into a freshly constructed typed `style=` object
    -- the flat kwargs these used to be passed as directly to DataSeries no
    longer exist post-Phase-3c-Task-4 -- and passing everything else
    (DataSeries' own fields) straight through.

    Marker fields (marker_style/marker_size/marker_color/marker_edge_color/
    marker_edge_width) and error-bar fields (error_direction/error_color/
    error_cap_size/etc.) live nested one level further, on style.marker
    (a MarkerStyle) and style.error_bars (an ErrorBarConfig) respectively
    -- routed here the same way."""
    style_cls = SERIES_TYPE_SPECS[series_type].style_cls
    style_field_names = {f.name for f in dataclasses.fields(style_cls)}
    marker_field_names = {f.name for f in dataclasses.fields(MarkerStyle)}
    error_bars_field_names = {f.name for f in dataclasses.fields(ErrorBarConfig)}

    style_kwargs = {k: v for k, v in overrides.items() if k in style_field_names}
    marker_kwargs = {k: v for k, v in overrides.items() if k in marker_field_names}
    error_bars_kwargs = {k: v for k, v in overrides.items() if k in error_bars_field_names}
    series_kwargs = {
        k: v for k, v in overrides.items()
        if k not in style_field_names
        and k not in marker_field_names
        and k not in error_bars_field_names
    }

    if marker_kwargs and "marker" in style_field_names:
        style_kwargs["marker"] = MarkerStyle(**marker_kwargs)
    if error_bars_kwargs and "error_bars" in style_field_names:
        style_kwargs["error_bars"] = ErrorBarConfig(**error_bars_kwargs)

    return DataSeries(
        dataset_id="ds1", x_column="x", y_column="y", series_type=series_type,
        style=style_cls(**style_kwargs),
        **series_kwargs,
    )


def _line_series(**overrides):
    series_type = overrides.pop("series_type", SeriesType.LINE)
    return _make_series(series_type, **overrides)


def _vector_series(**overrides):
    return _make_series(SeriesType.VECTOR, **overrides)


def test_load_then_apply_round_trips_line_series_color_and_line_style():
    _qapp()
    tab = StyleTab(app_context=None)
    tab.set_chart_type(ChartType.LINE)
    series = _line_series(color="#112233", line_style="dashed", line_width=3.0)

    tab.load_series_style(series)

    assert tab.line_color_row.currentColor() == "#112233"
    assert tab.line_width_slider.value() == 3.0

    tab.apply_series_style_to(series)

    assert series.style.color == "#112233"
    assert series.style.line_style == "dashed"
    assert series.style.line_width == 3.0


def test_load_then_apply_round_trips_marker_match_line_sentinel():
    """marker_color == "" (the "match line color" convention) must survive
    a load-then-apply cycle unchanged when the toggle isn't touched."""
    _qapp()
    tab = StyleTab(app_context=None)
    tab.set_chart_type(ChartType.LINE)
    series = _line_series(color="#445566", marker_style="circle", marker_color="")

    tab.load_series_style(series)

    assert tab.marker_match_line_toggle.isChecked() is True
    assert tab.marker_color_row.currentColor() == "#445566"  # shows the inherited color

    tab.apply_series_style_to(series)

    assert series.style.marker.marker_color == ""  # still the sentinel, not "#445566"


def test_load_then_apply_round_trips_fill_fields_for_line_series():
    _qapp()
    tab = StyleTab(app_context=None)
    tab.set_chart_type(ChartType.LINE)
    series = _line_series(color="#112233", fill_enabled=True, fill_color="#778899",
                           fill_alpha=0.5, fill_orientation="horizontal", fill_base=1.0,
                           fill_to_index=-1)

    tab.load_series_style(series)

    assert tab.fill_enabled_toggle.isChecked() is True
    assert tab.fill_horizontal_toggle.isChecked() is True

    tab.apply_series_style_to(series)

    assert series.style.fill_enabled is True
    assert series.style.fill_color == "#778899"
    assert series.style.fill_alpha == 0.5
    assert series.style.fill_orientation == "horizontal"


def test_load_then_apply_round_trips_vector_series():
    _qapp()
    tab = StyleTab(app_context=None)
    tab.set_chart_type(ChartType.VECTOR)
    series = _vector_series(vector_color="#abcdef", vector_scale=2.0, vector_width=0.02)

    tab.load_series_style(series)

    assert tab.vector_color_row.currentColor() == "#abcdef"
    assert tab.vector_scale_slider.value() == 2.0

    tab.apply_series_style_to(series)

    assert series.style.vector_color == "#abcdef"
    assert series.style.vector_scale == 2.0
    assert series.style.vector_width == 0.02


def test_load_does_not_crash_for_bar_series_with_no_marker_or_fill_fields():
    """A BarSeriesStyle has no marker_*/fill_* fields at all -- loading
    must not raise AttributeError just because the (hidden) Marker/Fill
    cards' controls still get populated with some default value."""
    _qapp()
    tab = StyleTab(app_context=None)
    tab.set_chart_type(ChartType.BAR)
    series = _line_series(series_type=SeriesType.BAR, color="#654321")

    tab.load_series_style(series)  # must not raise

    assert tab.line_color_row.currentColor() == "#654321"


def test_apply_does_not_write_marker_fields_onto_a_bar_series_style():
    """apply_series_style_to must not attempt to set marker_style/etc. on
    a BarSeriesStyle instance, which doesn't declare those fields."""
    _qapp()
    tab = StyleTab(app_context=None)
    tab.set_chart_type(ChartType.BAR)
    series = _line_series(series_type=SeriesType.BAR, color="#654321")

    tab.apply_series_style_to(series)  # must not raise

    assert series.style.color is not None  # color is still written
    assert not hasattr(series.style, "marker_style")


def test_error_bar_fields_live_on_style_error_bars_not_dataseries():
    """Error-bar fields moved off DataSeries onto style.error_bars (Task 2);
    apply_series_style_to must write there, not back onto the series."""
    _qapp()
    tab = StyleTab(app_context=None)
    tab.set_chart_type(ChartType.LINE)
    series = _line_series(color="#112233")

    tab.load_series_style(series)
    tab.apply_series_style_to(series)

    assert not hasattr(series, "error_color")
    assert series.style.error_bars.error_color == ""  # unchanged default


def test_card_visibility_uses_the_selected_series_own_type_not_the_chart_type():
    """A Line-typed chart with a Scatter-typed series selected must show
    Scatter's spec (marker required, no fill card) for that series --
    not Line's (marker optional, fill card visible)."""
    _qapp()
    tab = StyleTab(app_context=None)
    # Qt only reports isVisible() truthfully for a widget whose top-level
    # ancestor has actually been shown (see test_style_tab_vector.py's
    # _tab() helper for the same pattern) -- without this, isVisible() is
    # always False regardless of setVisible() calls.
    tab.show()
    tab.set_chart_type(ChartType.LINE)
    series = _line_series(series_type=SeriesType.SCATTER, color="#112233")
    tab._current_target = ("series", series)

    tab._update_target_cards_visibility()

    assert tab.fill_card.isVisible() is False  # Scatter has no fill support
    assert tab.marker_card.isVisible() is True  # Scatter's marker is required, not optional


def test_load_then_apply_round_trips_show_value_labels_for_line_series():
    """Regression (#125): the Value Labels toggle must persist through a
    load-then-apply cycle like every other per-series style field."""
    _qapp()
    tab = StyleTab(app_context=None)
    tab.set_chart_type(ChartType.LINE)
    series = _line_series(color="#112233", show_value_labels=True)

    tab.load_series_style(series)

    assert tab.value_labels_enabled_toggle.isChecked() is True

    tab.apply_series_style_to(series)

    assert series.style.show_value_labels is True


def test_load_then_apply_round_trips_show_value_labels_for_bar_series():
    _qapp()
    tab = StyleTab(app_context=None)
    tab.set_chart_type(ChartType.BAR)
    series = _line_series(series_type=SeriesType.BAR, color="#654321", show_value_labels=True)

    tab.load_series_style(series)

    assert tab.value_labels_enabled_toggle.isChecked() is True

    tab.apply_series_style_to(series)

    assert series.style.show_value_labels is True


def test_value_labels_card_visible_for_supported_types_hidden_otherwise():
    """SeriesTypeSpec.supports_value_labels (LINE/SCATTER/BAR only) drives
    the card's visibility, mirroring every other per-type card (Fill,
    Error Bars, ...)."""
    _qapp()
    tab = StyleTab(app_context=None)
    tab.show()
    tab.set_chart_type(ChartType.LINE)

    line_series = _line_series(color="#112233")
    tab._current_target = ("series", line_series)
    tab._update_target_cards_visibility()
    assert tab.value_labels_card.isVisible() is True

    bar_series = _line_series(series_type=SeriesType.BAR, color="#112233")
    tab._current_target = ("series", bar_series)
    tab._update_target_cards_visibility()
    assert tab.value_labels_card.isVisible() is True

    vector_series = _vector_series(vector_color="#112233")
    tab._current_target = ("series", vector_series)
    tab._update_target_cards_visibility()
    assert tab.value_labels_card.isVisible() is False


def test_value_labels_mode_and_arrow_controls_hidden_for_bar_shown_for_line():
    """Mode/arrow/offset only apply to Line/Scatter (BarSeriesStyle has no
    such fields -- bar_label() has no offset/arrow concept); the toggle
    itself and the color/background controls apply to all three."""
    _qapp()
    tab = StyleTab(app_context=None)
    tab.show()
    tab.set_chart_type(ChartType.LINE)

    line_series = _line_series(color="#112233", show_value_labels=True)
    tab.load_series_style(line_series)
    tab._current_target = ("series", line_series)
    tab._update_target_cards_visibility()
    assert tab.value_labels_mode_control.isVisible() is True
    assert tab.value_labels_arrow_toggle.isVisible() is True
    assert tab.value_labels_offset_x_spin.isVisible() is True

    bar_series = _line_series(series_type=SeriesType.BAR, color="#112233", show_value_labels=True)
    tab.load_series_style(bar_series)
    tab._current_target = ("series", bar_series)
    tab._update_target_cards_visibility()
    assert tab.value_labels_mode_control.isVisible() is False
    assert tab.value_labels_arrow_toggle.isVisible() is False
    assert tab.value_labels_offset_x_spin.isVisible() is False
    # Color/background controls still apply to Bar.
    assert tab.value_labels_match_color_toggle.isVisible() is True
    assert tab.value_labels_bg_enabled_toggle.isVisible() is True


def test_value_labels_sub_controls_hidden_when_toggle_off():
    _qapp()
    tab = StyleTab(app_context=None)
    tab.show()
    tab.set_chart_type(ChartType.LINE)
    series = _line_series(color="#112233", show_value_labels=False)
    tab.load_series_style(series)
    tab._current_target = ("series", series)

    tab._update_target_cards_visibility()

    assert tab.value_labels_mode_control.isVisible() is False
    assert tab.value_labels_match_color_toggle.isVisible() is False
    assert tab.value_labels_bg_enabled_toggle.isVisible() is False


def test_value_labels_text_color_row_hidden_while_matching_series_color():
    _qapp()
    tab = StyleTab(app_context=None)
    tab.show()
    tab.set_chart_type(ChartType.LINE)
    series = _line_series(color="#112233", show_value_labels=True)
    tab.load_series_style(series)
    tab._current_target = ("series", series)
    tab._update_target_cards_visibility()
    assert tab.value_labels_match_color_toggle.isChecked() is True  # default: "" == match
    assert tab.value_labels_text_color_row.isVisible() is False

    tab.value_labels_match_color_toggle.setChecked(checked=False)
    assert tab.value_labels_text_color_row.isVisible() is True


def test_value_labels_background_controls_hidden_until_enabled():
    _qapp()
    tab = StyleTab(app_context=None)
    tab.show()
    tab.set_chart_type(ChartType.LINE)
    series = _line_series(color="#112233", show_value_labels=True)
    tab.load_series_style(series)
    tab._current_target = ("series", series)
    tab._update_target_cards_visibility()
    assert tab.value_labels_bg_enabled_toggle.isChecked() is False  # default: no background
    assert tab.value_labels_bg_color_row.isVisible() is False
    assert tab.value_labels_bg_alpha_slider.isVisible() is False

    tab.value_labels_bg_enabled_toggle.setChecked(checked=True)
    assert tab.value_labels_bg_color_row.isVisible() is True
    assert tab.value_labels_bg_alpha_slider.isVisible() is True


def test_load_does_not_crash_for_vector_series_with_no_show_value_labels_field():
    """VectorSeriesStyle declares no show_value_labels field -- loading
    must not raise just because the (hidden) card's toggle still gets
    populated with some default value."""
    _qapp()
    tab = StyleTab(app_context=None)
    tab.set_chart_type(ChartType.VECTOR)
    series = _vector_series(vector_color="#abcdef")

    tab.load_series_style(series)  # must not raise

    assert tab.value_labels_enabled_toggle.isChecked() is False

    tab.apply_series_style_to(series)  # must not raise

    assert not hasattr(series.style, "show_value_labels")


def test_load_then_apply_round_trips_value_label_mode_arrow_offset_for_line_series():
    _qapp()
    tab = StyleTab(app_context=None)
    tab.set_chart_type(ChartType.LINE)
    series = _line_series(
        color="#112233", show_value_labels=True, value_label_mode="xy",
        value_label_show_arrow=True, value_label_offset_x=2.0, value_label_offset_y=-3.0,
    )

    tab.load_series_style(series)

    assert tab.value_labels_mode_control.currentValue() == "xy"
    assert tab.value_labels_arrow_toggle.isChecked() is True
    assert tab.value_labels_offset_x_spin.value() == 2.0
    assert tab.value_labels_offset_y_spin.value() == -3.0

    tab.apply_series_style_to(series)

    assert series.style.value_label_mode == "xy"
    assert series.style.value_label_show_arrow is True
    assert series.style.value_label_offset_x == 2.0
    assert series.style.value_label_offset_y == -3.0


def test_load_then_apply_round_trips_value_label_text_color_for_line_series():
    _qapp()
    tab = StyleTab(app_context=None)
    tab.set_chart_type(ChartType.LINE)
    series = _line_series(color="#112233", show_value_labels=True, value_label_text_color="#abcdef")

    tab.load_series_style(series)

    assert tab.value_labels_match_color_toggle.isChecked() is False
    assert tab.value_labels_text_color_row.currentColor() == "#abcdef"

    tab.apply_series_style_to(series)

    assert series.style.value_label_text_color == "#abcdef"


def test_load_then_apply_round_trips_value_label_text_color_match_convention():
    """Default ("" == match series color) must survive the round trip, same
    as marker/fill/band's existing match-line conventions."""
    _qapp()
    tab = StyleTab(app_context=None)
    tab.set_chart_type(ChartType.LINE)
    series = _line_series(color="#112233", show_value_labels=True)  # value_label_text_color == ""

    tab.load_series_style(series)

    assert tab.value_labels_match_color_toggle.isChecked() is True

    tab.apply_series_style_to(series)

    assert series.style.value_label_text_color == ""


def test_load_then_apply_round_trips_value_label_background_for_bar_series():
    _qapp()
    tab = StyleTab(app_context=None)
    tab.set_chart_type(ChartType.BAR)
    series = _line_series(
        series_type=SeriesType.BAR, color="#654321", show_value_labels=True,
        value_label_bg_color="#00ff00", value_label_bg_alpha=0.4,
    )

    tab.load_series_style(series)

    assert tab.value_labels_bg_enabled_toggle.isChecked() is True
    assert tab.value_labels_bg_color_row.currentColor() == "#00ff00"
    assert tab.value_labels_bg_alpha_slider.value() == 0.4

    tab.apply_series_style_to(series)

    assert series.style.value_label_bg_color == "#00ff00"
    assert series.style.value_label_bg_alpha == 0.4


def test_load_then_apply_round_trips_value_label_no_background_by_default():
    _qapp()
    tab = StyleTab(app_context=None)
    tab.set_chart_type(ChartType.BAR)
    series = _line_series(series_type=SeriesType.BAR, color="#654321", show_value_labels=True)

    tab.load_series_style(series)

    assert tab.value_labels_bg_enabled_toggle.isChecked() is False

    tab.apply_series_style_to(series)

    assert series.style.value_label_bg_color == ""


def test_load_does_not_crash_for_vector_series_with_no_value_label_style_fields():
    """VectorSeriesStyle declares none of the new value_label_* fields --
    loading/applying must not raise (same convention as the existing
    show_value_labels regression test just above)."""
    _qapp()
    tab = StyleTab(app_context=None)
    tab.set_chart_type(ChartType.VECTOR)
    series = _vector_series(vector_color="#abcdef")

    tab.load_series_style(series)  # must not raise
    tab.apply_series_style_to(series)  # must not raise

    assert not hasattr(series.style, "value_label_mode")
    assert not hasattr(series.style, "value_label_text_color")


def test_is_scatter_series_target_uses_the_selected_series_own_type():
    """_is_scatter_series_target must read the SELECTED SERIES' type, not
    the chart's -- a Scatter-typed series inside a Line-typed chart is
    still a scatter series for "match line" purposes (no line drawn for
    it), and a Line-typed series inside a Scatter-typed chart is not."""
    _qapp()
    tab = StyleTab(app_context=None)
    tab.set_chart_type(ChartType.LINE)
    scatter_series = _line_series(series_type=SeriesType.SCATTER)
    tab._current_target = ("series", scatter_series)

    assert tab._is_scatter_series_target() is True

    tab.set_chart_type(ChartType.SCATTER)
    line_series = _line_series(series_type=SeriesType.LINE)
    tab._current_target = ("series", line_series)

    assert tab._is_scatter_series_target() is False
