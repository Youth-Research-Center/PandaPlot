from pandaplot.models.chart.chart_style import ChartStyle


def test_defaults():
    style = ChartStyle()
    assert style.figure_size == (10, 6)
    assert style.figure_background_color == "#ffffff"
    assert style.axes_background_color == "#ffffff"
    assert style.font_size == 12
    assert style.font_family == "Arial"
    assert style.dpi == 100


def test_to_dict_from_dict_round_trip():
    style = ChartStyle(figure_background_color=None, font_size=16)
    data = style.to_dict()
    restored = ChartStyle.from_dict(data)
    assert restored.figure_background_color is None
    assert restored.font_size == 16


def test_dict_style_shim():
    style = ChartStyle()
    style["figure_background_color"] = None
    assert style.figure_background_color is None
    assert style.get("axes_background_color") == "#ffffff"


def test_contains_checks_both_typed_fields_and_legacy():
    style = ChartStyle()
    assert "font_size" in style
    assert "some_future_key" not in style
    style["some_future_key"] = 1
    assert "some_future_key" in style
