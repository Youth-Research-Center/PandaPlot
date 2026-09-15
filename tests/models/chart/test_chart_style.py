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


def test_figure_size_normalizes_a_json_list_to_a_tuple_on_construction():
    # JSON has no tuple type -- a persisted style's figure_size round-trips
    # through json.dumps/loads as a list.
    style = ChartStyle(figure_size=[12, 7])
    assert style.figure_size == (12, 7)
    assert isinstance(style.figure_size, tuple)


def test_figure_size_normalizes_a_json_list_via_from_dict():
    style = ChartStyle.from_dict({"figure_size": [12, 7]})
    assert style.figure_size == (12, 7)
    assert isinstance(style.figure_size, tuple)


def test_figure_size_normalizes_a_json_list_via_update_and_setitem():
    style = ChartStyle()
    style.update({"figure_size": [8, 4]})
    assert style.figure_size == (8, 4)
    assert isinstance(style.figure_size, tuple)

    style["figure_size"] = [9, 5]
    assert style.figure_size == (9, 5)
    assert isinstance(style.figure_size, tuple)


def test_contains_checks_both_typed_fields_and_legacy():
    style = ChartStyle()
    assert "font_size" in style
    assert "some_future_key" not in style
    style["some_future_key"] = 1
    assert "some_future_key" in style
