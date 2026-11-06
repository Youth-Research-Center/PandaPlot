"""Tests for UpdateSketchElementStyleCommand."""
from unittest.mock import Mock

import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.commands.project.sketch import UpdateSketchElementStyleCommand
from pandaplot.models.events import EventBus, SketchEvents
from pandaplot.models.events.event_data import SketchChangedData
from pandaplot.models.project.items.sketch import (
    LineElement,
    RectangleElement,
    Sketch,
    SketchElement,
    SketchLayer,
    StrokeStyle,
    TextAlignment,
    TextElement,
)


@pytest.fixture
def events() -> list[dict]:
    return []


@pytest.fixture
def app_context(events):
    event_bus = EventBus()
    event_bus.subscribe(SketchEvents.SKETCH_CHANGED, events.append)
    context = Mock()
    context.event_bus = event_bus
    return context


@pytest.fixture
def sketch() -> Sketch:
    return Sketch(id="sketch-1", layers=[
        SketchLayer(id="a", elements=[
            RectangleElement(id="rect", width=10.0, height=10.0, stroke_color="#000000", fill_color=None),
            LineElement(id="line", dx=10.0, stroke_color="#FF0000"),
        ]),
        SketchLayer(id="b", elements=[TextElement(id="text", text="Hi", stroke_color="#000000")]),
    ])


def _element(sketch: Sketch, element_id: str) -> SketchElement:
    found = sketch.find_element(element_id)
    assert found is not None
    return found[1]


def _command(app_context, sketch, element_ids, style) -> UpdateSketchElementStyleCommand:
    return UpdateSketchElementStyleCommand(app_context, sketch, element_ids, style)


def test_sets_a_field_on_every_element_across_layers(app_context, sketch, events):
    command = _command(app_context, sketch, ["rect", "line", "text"], {"stroke_color": "#00FF00"})

    assert command.execute() is CommandResult.SUCCESS

    assert [_element(sketch, element_id).stroke_color for element_id in ("rect", "line", "text")] == ["#00FF00"] * 3
    assert [SketchChangedData.from_dict(event) for event in events] == [SketchChangedData(sketch_id="sketch-1")]


def test_fields_skip_elements_that_do_not_draw_with_them(app_context, sketch):
    command = _command(app_context, sketch, ["rect", "line", "text"], {"fill_color": "#80112233", "stroke_style": StrokeStyle.DOTTED})

    assert command.execute() is CommandResult.SUCCESS

    rect, line, text = (_element(sketch, element_id) for element_id in ("rect", "line", "text"))
    assert (rect.fill_color, rect.stroke_style) == ("#80112233", StrokeStyle.DOTTED)
    assert (line.fill_color, line.stroke_style) == (None, StrokeStyle.DOTTED)
    assert (text.fill_color, text.stroke_style) == (None, StrokeStyle.SOLID)


def test_text_fields(app_context, sketch):
    style = {"font_family": "Courier", "font_size": 30, "is_bold": True, "is_italic": True, "alignment": TextAlignment.RIGHT}

    assert _command(app_context, sketch, ["text"], style).execute() is CommandResult.SUCCESS

    text = _element(sketch, "text")
    assert isinstance(text, TextElement)
    assert (text.font_family, text.font_size, text.is_bold, text.is_italic, text.alignment) == ("Courier", 30, True, True, TextAlignment.RIGHT)


def test_undo_restores_each_element_and_redo_reapplies(app_context, sketch):
    command = _command(app_context, sketch, ["rect", "line"], {"stroke_color": "#0000FF", "stroke_width": 5.0})
    command.execute()

    assert command.undo() is CommandResult.SUCCESS
    rect, line = _element(sketch, "rect"), _element(sketch, "line")
    assert (rect.stroke_color, rect.stroke_width) == ("#000000", 2.0)
    assert (line.stroke_color, line.stroke_width) == ("#FF0000", 2.0)

    assert command.redo() is CommandResult.SUCCESS
    assert (rect.stroke_color, line.stroke_color, rect.stroke_width, line.stroke_width) == ("#0000FF", "#0000FF", 5.0, 5.0)


def test_unchanged_values_are_a_noop(app_context, sketch, events):
    assert _command(app_context, sketch, ["rect", "text"], {"stroke_color": "#000000"}).execute() is CommandResult.NOOP
    assert _command(app_context, sketch, ["rect"], {}).execute() is CommandResult.NOOP
    assert _command(app_context, sketch, [], {"stroke_color": "#123456"}).execute() is CommandResult.NOOP
    assert events == []


def test_a_noop_is_not_pushed_onto_the_undo_stack(app_context, sketch):
    executor = CommandExecutor()

    assert executor.execute_command(_command(app_context, sketch, ["rect"], {"fill_color": None})) is False

    assert executor.undo_stack == []


@pytest.mark.parametrize(("element_ids", "style"), [
    (["rect"], {"x": 5.0}),
    (["rect"], {"text": "changed"}),
    (["rect"], {"stroke_color": "blue"}),
    (["rect"], {"stroke_width": -1.0}),
    (["rect"], {"stroke_style": "dashed"}),
    (["text"], {"font_size": 0}),
    (["line"], {"fill_color": "#FFFFFF"}),
    (["rect", "missing"], {"stroke_color": "#FFFFFF"}),
])
def test_refuses_without_changing_anything(app_context, sketch, events, element_ids, style):
    before = sketch.to_dict()

    assert _command(app_context, sketch, element_ids, style).execute() is CommandResult.FAILURE

    assert sketch.to_dict() == before
    assert events == []


def test_refuses_elements_on_a_locked_layer(app_context, sketch):
    layer = sketch.get_layer("b")
    assert layer is not None
    layer.locked = True

    assert _command(app_context, sketch, ["rect", "text"], {"stroke_color": "#FFFFFF"}).execute() is CommandResult.FAILURE
    assert _element(sketch, "rect").stroke_color == "#000000"


def test_undo_and_redo_fail_when_an_element_is_gone(app_context, sketch):
    command = _command(app_context, sketch, ["rect", "line"], {"stroke_color": "#0000FF"})
    command.execute()
    sketch.remove_element("line")

    assert command.undo() is CommandResult.FAILURE
    assert command.redo() is CommandResult.FAILURE
    assert _element(sketch, "rect").stroke_color == "#0000FF"


def test_undo_and_redo_before_execute_fail(app_context, sketch):
    command = _command(app_context, sketch, ["rect"], {"stroke_color": "#0000FF"})

    assert command.undo() is CommandResult.FAILURE
    assert command.redo() is CommandResult.FAILURE
