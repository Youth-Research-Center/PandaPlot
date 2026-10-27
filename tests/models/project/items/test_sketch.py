"""Tests for the Sketch item model, its layers and element primitives."""
import dataclasses
import json
from typing import Any

import pytest

from pandaplot.models.project.items.sketch import (
    ELEMENT_TYPES,
    EllipseElement,
    FreehandElement,
    LineElement,
    RectangleElement,
    Sketch,
    SketchElement,
    SketchLayer,
    StrokeStyle,
    TextAlignment,
    TextElement,
)
from pandaplot.models.project.items.sketch.sketch_element import STYLE_VALUE_CHECKS, is_hex_color


def _all_element_types() -> list[SketchElement]:
    return [
        FreehandElement(id="f", x=1.0, y=2.0, stroke_color="#FF0000", stroke_width=3.0, points=[(0.0, 0.0), (5.0, 2.5)]),
        LineElement(id="l", x=10.0, y=20.0, dx=30.0, dy=-5.0, stroke_style=StrokeStyle.DASHED),
        RectangleElement(id="r", x=100.0, y=100.0, width=200.0, height=150.0, corner_radius=8.0, fill_color="#00FF0080", rotation=15.0),
        EllipseElement(id="e", x=50.0, y=60.0, rx=40.0, ry=20.0, stroke_style=StrokeStyle.DASH_DOT),
        TextElement(
            id="t", x=5.0, y=6.0, text="Hello", font_family="Serif", font_size=24,
            is_bold=True, is_italic=True, alignment=TextAlignment.CENTER,
        ),
    ]


class TestElements:
    def test_registry_maps_every_builtin_type(self):
        assert ELEMENT_TYPES == {
            "freehand": FreehandElement,
            "line": LineElement,
            "rectangle": RectangleElement,
            "ellipse": EllipseElement,
            "text": TextElement,
        }

    @pytest.mark.parametrize("element", _all_element_types(), ids=lambda e: e.TYPE)
    def test_round_trip_preserves_every_field_and_concrete_type(self, element):
        data = element.to_dict()

        restored = SketchElement.from_dict(json.loads(json.dumps(data)))

        assert type(restored) is type(element)
        assert restored == element
        assert data["type"] == element.TYPE

    def test_freehand_points_come_back_as_tuples(self):
        element = FreehandElement(points=[(1.0, 2.0)])

        restored = SketchElement.from_dict(json.loads(json.dumps(element.to_dict())))

        assert isinstance(restored, FreehandElement)
        assert restored.points == [(1.0, 2.0)]
        assert isinstance(restored.points[0], tuple)

    def test_unknown_type_returns_none(self):
        assert SketchElement.from_dict({"type": "resistor", "x": 1.0}) is None

    def test_invalid_values_fall_back_to_defaults(self):
        restored = SketchElement.from_dict({
            "id": "r", "type": "rectangle", "x": "left", "y": float("nan"),
            "stroke_width": -4, "stroke_style": "wavy", "fill_color": 7,
            "width": -10.0, "height": True,
        })

        assert restored == RectangleElement(id="r", stroke_width=0.0, width=0.0, height=0.0)

    def test_invalid_text_values_fall_back_to_defaults(self):
        restored = SketchElement.from_dict({
            "id": "t", "type": "text", "text": 5, "font_size": 0, "is_bold": "yes", "alignment": "justify",
        })

        assert restored == TextElement(id="t")

    def test_malformed_freehand_points_are_dropped(self):
        restored = SketchElement.from_dict({"type": "freehand", "points": [[1, 2], [3], "x", [None, 4], [5.5, 6]]})

        assert isinstance(restored, FreehandElement)
        assert restored.points == [(1.0, 2.0), (5.5, 6.0)]

    def test_string_enums_are_coerced_on_construction(self):
        kwargs: dict[str, Any] = {"stroke_style": "dotted", "alignment": "right"}

        element = TextElement(**kwargs)

        assert element.stroke_style is StrokeStyle.DOTTED
        assert element.alignment is TextAlignment.RIGHT

    @pytest.mark.parametrize("factory", [
        lambda: RectangleElement(width=-1.0),
        lambda: EllipseElement(ry=-1.0),
        lambda: TextElement(font_size=0),
        lambda: LineElement(stroke_width=-0.5),
    ])
    def test_invalid_geometry_is_rejected(self, factory):
        with pytest.raises(ValueError):
            factory()

    def test_new_elements_get_distinct_ids(self):
        assert LineElement().id != LineElement().id


class TestSketchLayer:
    def test_round_trip_preserves_fields_and_element_order(self):
        layer = SketchLayer(id="layer-1", name="Ink", visible=False, locked=True, opacity=0.25, elements=_all_element_types())

        restored = SketchLayer.from_dict(json.loads(json.dumps(layer.to_dict())))

        assert restored == layer
        assert [element.id for element in restored.elements] == ["f", "l", "r", "e", "t"]

    def test_unknown_elements_are_skipped_but_others_kept_in_order(self):
        data = SketchLayer(elements=[LineElement(id="a"), LineElement(id="b")]).to_dict()
        data["elements"].insert(1, {"id": "x", "type": "resistor"})

        restored = SketchLayer.from_dict(data)

        assert [element.id for element in restored.elements] == ["a", "b"]

    def test_invalid_fields_fall_back_to_defaults(self):
        restored = SketchLayer.from_dict({"id": "l", "name": None, "visible": "no", "locked": 1, "opacity": 3.0, "elements": "none"})

        assert restored == SketchLayer(id="l", opacity=1.0)

    def test_opacity_out_of_range_is_rejected(self):
        with pytest.raises(ValueError):
            SketchLayer(opacity=1.5)


class TestSketch:
    def test_new_sketch_has_one_active_default_layer(self):
        sketch = Sketch(name="Drawing")

        assert len(sketch.layers) == 1
        assert sketch.layers[0].name == "Layer 1"
        assert sketch.active_layer is sketch.layers[0]
        assert (sketch.canvas_width, sketch.canvas_height, sketch.background_color) == (1920.0, 1080.0, "#FFFFFF")

    def test_active_layer_defaults_to_top_layer_when_unknown(self):
        bottom, top = SketchLayer(id="bottom"), SketchLayer(id="top")

        sketch = Sketch(layers=[bottom, top], active_layer_id="missing")

        assert sketch.active_layer_id == "top"

    def test_non_positive_canvas_size_is_rejected(self):
        with pytest.raises(ValueError):
            Sketch(canvas_width=0)

    def test_round_trip_preserves_every_field(self):
        sketch = Sketch(
            id="sketch-1", name="Circuit",
            layers=[SketchLayer(id="bg", name="Background", elements=_all_element_types()), SketchLayer(id="ink", opacity=0.5)],
            active_layer_id="bg", canvas_width=800.0, canvas_height=600.0, background_color="#101010",
        )
        sketch.parent_id = "folder-1"
        sketch.metadata = {"note": "x"}

        restored = Sketch.from_dict(json.loads(json.dumps(sketch.to_dict())))

        assert restored.to_dict() == sketch.to_dict()
        assert restored.layers == sketch.layers
        assert (restored.id, restored.name, restored.parent_id, restored.active_layer_id) == ("sketch-1", "Circuit", "folder-1", "bg")

    def test_from_dict_without_layers_gets_a_default_layer(self):
        restored = Sketch.from_dict({"id": "s", "name": "Empty", "layers": [], "canvas_width": -5})

        assert len(restored.layers) == 1
        assert restored.active_layer_id == restored.layers[0].id
        assert restored.canvas_width == 1920.0

    def test_add_layer_inserts_at_index_and_on_top_by_default(self):
        sketch = Sketch(layers=[SketchLayer(id="a")])

        assert sketch.add_layer(SketchLayer(id="c")) == 1
        assert sketch.add_layer(SketchLayer(id="b"), index=1) == 1

        assert [layer.id for layer in sketch.layers] == ["a", "b", "c"]

    def test_add_layer_rejects_duplicate_id(self):
        sketch = Sketch(layers=[SketchLayer(id="a")])

        with pytest.raises(ValueError):
            sketch.add_layer(SketchLayer(id="a"))

    def test_remove_layer_returns_its_index_and_restores_in_place(self):
        sketch = Sketch(layers=[SketchLayer(id="a"), SketchLayer(id="b"), SketchLayer(id="c")])

        layer, index = sketch.remove_layer("b")
        sketch.add_layer(layer, index=index)

        assert index == 1
        assert [layer.id for layer in sketch.layers] == ["a", "b", "c"]

    def test_removing_active_layer_activates_the_layer_in_its_place(self):
        sketch = Sketch(layers=[SketchLayer(id="a"), SketchLayer(id="b"), SketchLayer(id="c")], active_layer_id="b")

        sketch.remove_layer("b")
        assert sketch.active_layer_id == "c"

        sketch.remove_layer("c")
        assert sketch.active_layer_id == "a"

    def test_last_layer_cannot_be_removed(self):
        sketch = Sketch()

        with pytest.raises(ValueError):
            sketch.remove_layer(sketch.layers[0].id)

    def test_remove_unknown_layer_raises_key_error(self):
        with pytest.raises(KeyError):
            Sketch().remove_layer("missing")

    def test_move_layer_reorders_and_returns_old_index(self):
        sketch = Sketch(layers=[SketchLayer(id="a"), SketchLayer(id="b"), SketchLayer(id="c")])

        old_index = sketch.move_layer("a", 5)

        assert old_index == 0
        assert [layer.id for layer in sketch.layers] == ["b", "c", "a"]

    def test_add_and_remove_element_preserve_position(self):
        sketch = Sketch(layers=[SketchLayer(id="a", elements=[LineElement(id="1"), LineElement(id="2"), LineElement(id="3")])])

        layer, element, index = sketch.remove_element("2")
        sketch.add_element(layer.id, element, index=index)

        assert (layer.id, element.id, index) == ("a", "2", 1)
        assert [element.id for element in sketch.layers[0].elements] == ["1", "2", "3"]

    def test_add_element_rejects_unknown_layer_and_duplicate_id(self):
        sketch = Sketch(layers=[SketchLayer(id="a", elements=[LineElement(id="1")])])

        with pytest.raises(KeyError):
            sketch.add_element("missing", LineElement())
        with pytest.raises(ValueError):
            sketch.add_element("a", LineElement(id="1"))

    def test_remove_unknown_element_raises_key_error(self):
        with pytest.raises(KeyError):
            Sketch().remove_element("missing")

    def test_find_element_returns_layer_and_element(self):
        element = EllipseElement(id="e")
        sketch = Sketch(layers=[SketchLayer(id="a"), SketchLayer(id="b", elements=[element])])

        result = sketch.find_element("e")

        assert result is not None
        layer, found = result

        assert layer.id == "b"
        assert found is element
        assert sketch.find_element("missing") is None

    def test_mutations_update_modified_time(self):
        sketch = Sketch()
        sketch.modified_at = "2000-01-01T00:00:00"

        sketch.add_element(sketch.active_layer_id, LineElement())

        assert sketch.modified_at != "2000-01-01T00:00:00"


class TestStyleFields:
    def test_each_type_lists_the_style_fields_it_draws_with(self):
        shape_fields = {"stroke_color", "stroke_width", "stroke_style", "fill_color"}
        assert FreehandElement.STYLE_FIELDS == shape_fields
        assert RectangleElement.STYLE_FIELDS == shape_fields
        assert EllipseElement.STYLE_FIELDS == shape_fields
        assert LineElement.STYLE_FIELDS == {"stroke_color", "stroke_width", "stroke_style"}
        assert TextElement.STYLE_FIELDS == {"stroke_color", "font_family", "font_size", "is_bold", "is_italic", "alignment"}

    def test_every_style_field_has_a_value_check_and_is_a_real_field(self):
        for element_class in ELEMENT_TYPES.values():
            field_names = {f.name for f in dataclasses.fields(element_class)}
            assert element_class.STYLE_FIELDS <= set(STYLE_VALUE_CHECKS)
            assert element_class.STYLE_FIELDS <= field_names

    @pytest.mark.parametrize(("value", "expected"), [
        ("#FFF", True), ("#00ff00", True), ("#8000FF00", True),
        ("red", False), ("#12345", False), ("00FF00", False), (None, False), (0xFF0000, False),
    ])
    def test_is_hex_color(self, value, expected):
        assert is_hex_color(value) is expected

    @pytest.mark.parametrize(("name", "valid", "invalid"), [
        ("stroke_width", [0, 0.5, 50], [-1, float("nan"), float("inf"), True, "2"]),
        ("stroke_style", [StrokeStyle.DASHED], ["dashed", None]),
        ("fill_color", [None, "#123456"], ["blue", ""]),
        ("font_family", ["Arial"], ["", "  ", None]),
        ("font_size", [1, 72], [0, -3, 12.5, True]),
        ("is_bold", [True, False], [1, None]),
        ("alignment", [TextAlignment.CENTER], ["center"]),
    ])
    def test_style_value_checks(self, name, valid, invalid):
        check = STYLE_VALUE_CHECKS[name]
        assert all(check(value) for value in valid)
        assert not any(check(value) for value in invalid)
