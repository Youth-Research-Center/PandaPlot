"""Drawing, selecting, moving, resizing, deleting, pan and zoom on the sketch
canvas, driven by real mouse and key events on its viewport."""
import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas
from pandaplot.gui.components.tabs.sketch.tools.tool_manager import ToolMode
from pandaplot.models.project import Project
from pandaplot.models.project.items.sketch import (
    EllipseElement,
    FreehandElement,
    LineElement,
    RectangleElement,
    Sketch,
    SketchLayer,
    TextElement,
)

LEFT = Qt.MouseButton.LeftButton
NO_MODIFIER = Qt.KeyboardModifier.NoModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier


@pytest.fixture
def app_context(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return build_app_context()


@pytest.fixture
def sketch(app_context) -> Sketch:
    sketch = Sketch(id="sketch", canvas_width=400.0, canvas_height=300.0, layers=[
        SketchLayer(id="bottom", name="Bottom"),
        SketchLayer(id="top", name="Top"),
    ], active_layer_id="top")
    project = Project(name="Tools")
    project.add_item(sketch)
    app_context.get_app_state().load_project(project)
    return sketch


@pytest.fixture
def canvas(qtbot, app_context, sketch) -> SketchCanvas:
    canvas = SketchCanvas(sketch, app_context=app_context)
    qtbot.addWidget(canvas)
    canvas.resize(600, 500)
    canvas.show()
    qtbot.waitExposed(canvas)
    assert canvas.zoom == 1.0
    return canvas


def _mouse_at(canvas: SketchCanvas, kind: QEvent.Type, viewport_pos: QPoint, *,
              button: Qt.MouseButton = LEFT, modifiers: Qt.KeyboardModifier = NO_MODIFIER) -> None:
    """Send a mouse event to the canvas viewport at a viewport position."""
    buttons = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else button
    global_pos = QPointF(canvas.viewport().mapToGlobal(viewport_pos))
    event = QMouseEvent(kind, QPointF(viewport_pos), global_pos, button, buttons, modifiers)
    QApplication.sendEvent(canvas.viewport(), event)


def _mouse(canvas: SketchCanvas, kind: QEvent.Type, scene: tuple[float, float], *,
           button: Qt.MouseButton = LEFT, modifiers: Qt.KeyboardModifier = NO_MODIFIER) -> None:
    """Send a mouse event at a scene position, mapped through the current view."""
    _mouse_at(canvas, kind, canvas.mapFromScene(QPointF(*scene)), button=button, modifiers=modifiers)


def _drag(canvas: SketchCanvas, points: list[tuple[float, float]], *,
          button: Qt.MouseButton = LEFT, modifiers: Qt.KeyboardModifier = NO_MODIFIER) -> None:
    _mouse(canvas, QEvent.Type.MouseButtonPress, points[0], button=button, modifiers=modifiers)
    for point in points[1:]:
        _mouse(canvas, QEvent.Type.MouseMove, point, button=button, modifiers=modifiers)
    _mouse(canvas, QEvent.Type.MouseButtonRelease, points[-1], button=button, modifiers=modifiers)


def _click(canvas: SketchCanvas, point: tuple[float, float], *, modifiers: Qt.KeyboardModifier = NO_MODIFIER) -> None:
    _drag(canvas, [point], modifiers=modifiers)


def _key(canvas: SketchCanvas, key: Qt.Key, kind: QEvent.Type = QEvent.Type.KeyPress) -> None:
    QApplication.sendEvent(canvas, QKeyEvent(kind, key, NO_MODIFIER))


def _wheel(canvas: SketchCanvas, scene: tuple[float, float], steps: int, modifiers: Qt.KeyboardModifier) -> None:
    position = QPointF(canvas.mapFromScene(QPointF(*scene)))
    event = QWheelEvent(position, QPointF(canvas.viewport().mapToGlobal(position.toPoint())), QPoint(), QPoint(0, 120 * steps),
                        Qt.MouseButton.NoButton, modifiers, Qt.ScrollPhase.NoScrollPhase, False)  # noqa: FBT003 - Qt constructor
    QApplication.sendEvent(canvas.viewport(), event)


def _elements(sketch: Sketch, layer_id: str = "top") -> list:
    layer = sketch.get_layer(layer_id)
    assert layer is not None
    return layer.elements


def _add(sketch: Sketch, element, layer_id: str = "top"):
    sketch.add_element(layer_id, element)
    return element


class TestDrawingTools:
    def test_rectangle_drag_in_any_direction_creates_a_normalised_rectangle(self, canvas, sketch):
        canvas.tool_manager.set_tool(ToolMode.RECTANGLE)

        _drag(canvas, [(150, 120), (100, 90), (50, 40)])

        [rectangle] = _elements(sketch)
        assert isinstance(rectangle, RectangleElement)
        assert (rectangle.x, rectangle.y, rectangle.width, rectangle.height) == (50, 40, 100, 80)
        assert canvas.element_item(rectangle.id) is not None

    def test_ellipse_drag_spans_its_bounding_box(self, canvas, sketch):
        canvas.tool_manager.set_tool(ToolMode.ELLIPSE)

        _drag(canvas, [(40, 60), (140, 100)])

        [ellipse] = _elements(sketch)
        assert isinstance(ellipse, EllipseElement)
        assert (ellipse.x, ellipse.y, ellipse.rx, ellipse.ry) == (90, 80, 50, 20)

    def test_line_runs_from_press_to_release_and_may_be_horizontal(self, canvas, sketch):
        canvas.tool_manager.set_tool(ToolMode.LINE)

        _drag(canvas, [(20, 30), (220, 30)])

        [line] = _elements(sketch)
        assert isinstance(line, LineElement)
        assert (line.x, line.y, line.dx, line.dy) == (20, 30, 200, 0)

    @pytest.mark.parametrize("mode", [ToolMode.RECTANGLE, ToolMode.ELLIPSE, ToolMode.LINE, ToolMode.FREEHAND])
    def test_a_click_without_a_drag_draws_nothing(self, canvas, sketch, mode):
        canvas.tool_manager.set_tool(mode)

        _click(canvas, (100, 100))

        assert _elements(sketch) == []

    def test_a_preview_follows_the_drag_and_goes_away_on_release(self, canvas, sketch):
        canvas.tool_manager.set_tool(ToolMode.RECTANGLE)
        _mouse(canvas, QEvent.Type.MouseButtonPress, (10, 10))
        _mouse(canvas, QEvent.Type.MouseMove, (60, 50))

        assert canvas._preview is not None
        assert _elements(sketch) == []

        _mouse(canvas, QEvent.Type.MouseButtonRelease, (60, 50))
        assert canvas._preview is None

    def test_pen_stroke_is_simplified_and_stored_relative_to_its_start(self, canvas, sketch):
        canvas.tool_manager.set_tool(ToolMode.FREEHAND)
        straight = [(20 + 5 * i, 50.0) for i in range(30)]
        corner = [(165.0, 50 + 5 * i) for i in range(1, 20)]

        _drag(canvas, [*straight, *corner])

        [stroke] = _elements(sketch)
        assert isinstance(stroke, FreehandElement)
        assert (stroke.x, stroke.y) == (20, 50)
        assert stroke.points == [(0.0, 0.0), (145.0, 0.0), (145.0, 95.0)]

    def test_text_tool_places_the_typed_text_at_the_click(self, canvas, sketch, app_context, monkeypatch):
        monkeypatch.setattr(app_context.get_ui_controller(), "get_text_input", lambda *_args, **_kwargs: "R1")
        canvas.tool_manager.set_tool(ToolMode.TEXT)

        _click(canvas, (70, 80))

        [label] = _elements(sketch)
        assert isinstance(label, TextElement)
        assert (label.text, label.x, label.y) == ("R1", 70, 80)

    @pytest.mark.parametrize("typed", [None, "   "])
    def test_cancelled_or_blank_text_adds_nothing(self, canvas, sketch, app_context, monkeypatch, typed):
        monkeypatch.setattr(app_context.get_ui_controller(), "get_text_input", lambda *_args, **_kwargs: typed)
        canvas.tool_manager.set_tool(ToolMode.TEXT)

        _click(canvas, (70, 80))

        assert _elements(sketch) == []

    def test_each_drawn_element_is_one_undo_step(self, canvas, sketch, app_context):
        canvas.tool_manager.set_tool(ToolMode.RECTANGLE)
        _drag(canvas, [(10, 10), (60, 60)])
        _drag(canvas, [(100, 100), (160, 160)])

        app_context.get_command_executor().undo()

        assert len(_elements(sketch)) == 1
        assert len(canvas._element_items) == 1

    @pytest.mark.parametrize(("flag", "message"), [("locked", "locked"), ("visible", "hidden")])
    def test_drawing_on_a_locked_or_hidden_active_layer_is_refused_with_a_message(self, canvas, sketch, qtbot, flag, message):
        layer = sketch.active_layer
        setattr(layer, flag, flag == "locked")
        canvas.tool_manager.set_tool(ToolMode.RECTANGLE)

        with qtbot.waitSignal(canvas.status_message) as blocker:
            _drag(canvas, [(10, 10), (60, 60)])

        assert message in blocker.args[0]
        assert _elements(sketch) == []
        assert canvas._preview is None

    def test_space_drag_pans_instead_of_drawing(self, canvas, sketch):
        canvas.tool_manager.set_tool(ToolMode.RECTANGLE)

        _key(canvas, Qt.Key.Key_Space)
        _drag(canvas, [(10, 10), (60, 60)])
        _key(canvas, Qt.Key.Key_Space, QEvent.Type.KeyRelease)

        assert _elements(sketch) == []


class TestSelection:
    def test_click_selects_the_topmost_element_and_empty_click_clears(self, canvas, sketch):
        _add(sketch, RectangleElement(id="low", x=50, y=50, width=100, height=100, fill_color="#FF0000"), "bottom")
        _add(sketch, RectangleElement(id="high", x=50, y=50, width=100, height=100, fill_color="#00FF00"))
        canvas.rebuild()

        _click(canvas, (100, 100))
        assert canvas.selected_ids == ("high",)

        _click(canvas, (300, 250))
        assert canvas.selected_ids == ()

    def test_shift_click_adds_and_removes(self, canvas, sketch):
        _add(sketch, RectangleElement(id="a", x=10, y=10, width=50, height=50, fill_color="#FF0000"))
        _add(sketch, RectangleElement(id="b", x=100, y=10, width=50, height=50, fill_color="#FF0000"))
        canvas.rebuild()

        _click(canvas, (30, 30))
        _click(canvas, (120, 30), modifiers=SHIFT)
        assert canvas.selected_ids == ("a", "b")

        _click(canvas, (30, 30), modifiers=SHIFT)
        assert canvas.selected_ids == ("b",)

    def test_outline_only_shapes_are_picked_on_their_edge_not_inside(self, canvas, sketch):
        _add(sketch, RectangleElement(id="frame", x=50, y=50, width=200, height=100))
        canvas.rebuild()

        _click(canvas, (150, 100))
        assert canvas.selected_ids == ()

        _click(canvas, (52, 100))
        assert canvas.selected_ids == ("frame",)

    def test_thin_lines_are_picked_within_a_few_pixels(self, canvas, sketch):
        _add(sketch, LineElement(id="wire", x=20, y=100, dx=200, dy=0, stroke_width=1.0))
        canvas.rebuild()

        _click(canvas, (100, 104))

        assert canvas.selected_ids == ("wire",)

    def test_rubber_band_selects_what_it_touches_on_interactive_layers(self, canvas, sketch):
        _add(sketch, RectangleElement(id="in", x=20, y=20, width=40, height=40))
        _add(sketch, RectangleElement(id="out", x=300, y=200, width=40, height=40))
        _add(sketch, RectangleElement(id="locked", x=30, y=30, width=20, height=20), "bottom")
        bottom = sketch.get_layer("bottom")
        assert bottom is not None
        bottom.locked = True
        canvas.rebuild()

        _drag(canvas, [(5, 5), (100, 100)])

        assert canvas.selected_ids == ("in",)
        assert not canvas._rubber_band.isVisible()

    def test_elements_on_hidden_or_locked_layers_cannot_be_picked(self, canvas, sketch):
        _add(sketch, RectangleElement(id="under", x=50, y=50, width=100, height=100, fill_color="#FF0000"), "bottom")
        _add(sketch, RectangleElement(id="over", x=50, y=50, width=100, height=100, fill_color="#00FF00"))
        top = sketch.get_layer("top")
        assert top is not None
        top.locked = True
        canvas.rebuild()

        _click(canvas, (100, 100))

        assert canvas.selected_ids == ("under",)

    def test_selection_survives_a_redraw_and_drops_what_became_unselectable(self, canvas, sketch, app_context):
        _add(sketch, RectangleElement(id="a", x=10, y=10, width=50, height=50, fill_color="#FF0000"))
        _add(sketch, RectangleElement(id="b", x=10, y=100, width=50, height=50, fill_color="#FF0000"), "bottom")
        canvas.rebuild()
        canvas.set_selection(["a", "b"])

        canvas.rebuild()
        assert canvas.selected_ids == ("a", "b")

        bottom = sketch.get_layer("bottom")
        assert bottom is not None
        bottom.visible = False
        canvas.rebuild()
        assert canvas.selected_ids == ("a",)

    def test_switching_to_a_drawing_tool_clears_the_selection(self, canvas, sketch):
        _add(sketch, RectangleElement(id="a", x=10, y=10, width=50, height=50, fill_color="#FF0000"))
        canvas.rebuild()
        canvas.set_selection(["a"])

        canvas.tool_manager.set_tool(ToolMode.LINE)

        assert canvas.selected_ids == ()


class TestMoveResizeDelete:
    def test_dragging_the_selection_moves_it_in_one_undo_step(self, canvas, sketch, app_context):
        a = _add(sketch, RectangleElement(id="a", x=10, y=10, width=50, height=50, fill_color="#FF0000"))
        b = _add(sketch, EllipseElement(id="b", x=200, y=100, rx=20, ry=20, fill_color="#FF0000"))
        canvas.rebuild()
        canvas.set_selection(["a", "b"])

        _drag(canvas, [(30, 30), (40, 35), (60, 50)])

        assert (a.x, a.y, b.x, b.y) == (40, 30, 230, 120)
        assert canvas.selected_ids == ("a", "b")
        app_context.get_command_executor().undo()
        assert (a.x, a.y, b.x, b.y) == (10, 10, 200, 100)

    def test_a_click_on_the_selection_moves_nothing(self, canvas, sketch, app_context):
        a = _add(sketch, RectangleElement(id="a", x=10, y=10, width=50, height=50, fill_color="#FF0000"))
        canvas.rebuild()

        _click(canvas, (30, 30))

        assert (a.x, a.y) == (10, 10)
        assert app_context.get_command_executor().undo_stack == []

    def test_the_model_is_untouched_until_release(self, canvas, sketch):
        a = _add(sketch, RectangleElement(id="a", x=10, y=10, width=50, height=50, fill_color="#FF0000"))
        canvas.rebuild()
        canvas.set_selection(["a"])
        _mouse(canvas, QEvent.Type.MouseButtonPress, (30, 30))
        _mouse(canvas, QEvent.Type.MouseMove, (80, 80))

        assert (a.x, a.y) == (10, 10)
        item = canvas.element_item("a")
        assert item is not None
        assert item.pos() == QPointF(60, 60)

    def test_escape_during_a_drag_cancels_it(self, canvas, sketch, app_context):
        a = _add(sketch, RectangleElement(id="a", x=10, y=10, width=50, height=50, fill_color="#FF0000"))
        canvas.rebuild()
        canvas.set_selection(["a"])
        _mouse(canvas, QEvent.Type.MouseButtonPress, (30, 30))
        _mouse(canvas, QEvent.Type.MouseMove, (80, 80))

        _key(canvas, Qt.Key.Key_Escape)
        _mouse(canvas, QEvent.Type.MouseButtonRelease, (80, 80))

        assert (a.x, a.y) == (10, 10)
        item = canvas.element_item("a")
        assert item is not None
        assert item.pos() == QPointF(10, 10)
        assert app_context.get_command_executor().undo_stack == []

    def test_dragging_a_corner_handle_resizes(self, canvas, sketch):
        rectangle = _add(sketch, RectangleElement(id="r", x=100, y=100, width=100, height=50, stroke_width=4.0))
        canvas.rebuild()
        canvas.set_selection(["r"])

        _drag(canvas, [(200, 150), (250, 200), (300, 250)])

        assert (rectangle.x, rectangle.y, rectangle.width, rectangle.height) == (100, 100, 200, 150)

    def test_shift_on_a_corner_keeps_the_proportions(self, canvas, sketch):
        rectangle = _add(sketch, RectangleElement(id="r", x=100, y=100, width=100, height=50))
        canvas.rebuild()
        canvas.set_selection(["r"])

        _drag(canvas, [(200, 150), (300, 160)], modifiers=SHIFT)

        assert (rectangle.width, rectangle.height) == pytest.approx((200, 100))

    def test_an_edge_handle_resizes_one_axis_from_the_opposite_side(self, canvas, sketch):
        ellipse = _add(sketch, EllipseElement(id="e", x=150, y=150, rx=50, ry=25))
        canvas.rebuild()
        canvas.set_selection(["e"])

        _drag(canvas, [(100, 150), (60, 150)])

        assert (ellipse.x, ellipse.y, ellipse.rx, ellipse.ry) == (130, 150, 70, 25)

    def test_rotated_elements_get_no_resize_handles(self, canvas, sketch):
        _add(sketch, RectangleElement(id="r", x=100, y=100, width=100, height=50, rotation=30.0, fill_color="#FF0000"))
        canvas.rebuild()
        canvas.set_selection(["r"])

        assert not canvas.can_resize_selection()
        assert not any(handle.isVisible() for handle in canvas._handles.values())

    @pytest.mark.parametrize("key", [Qt.Key.Key_Delete, Qt.Key.Key_Backspace])
    def test_delete_and_backspace_remove_the_selection_undoably(self, canvas, sketch, app_context, key):
        _add(sketch, RectangleElement(id="a", x=10, y=10, width=50, height=50, fill_color="#FF0000"))
        _add(sketch, RectangleElement(id="b", x=100, y=10, width=50, height=50, fill_color="#FF0000"))
        canvas.rebuild()
        canvas.set_selection(["a"])

        _key(canvas, key)

        assert [element.id for element in _elements(sketch)] == ["b"]
        assert canvas.selected_ids == ()
        app_context.get_command_executor().undo()
        assert [element.id for element in _elements(sketch)] == ["a", "b"]

    def test_escape_without_a_drag_clears_the_selection(self, canvas, sketch):
        _add(sketch, RectangleElement(id="a", x=10, y=10, width=50, height=50, fill_color="#FF0000"))
        canvas.rebuild()
        canvas.set_selection(["a"])

        _key(canvas, Qt.Key.Key_Escape)

        assert canvas.selected_ids == ()


class TestZoomAndPan:
    def test_ctrl_wheel_zooms_around_the_pointer(self, canvas):
        # Zoomed in far enough that the canvas overflows the view; while it
        # fits, Qt keeps it centred and nothing can stay under the pointer.
        canvas.zoom_by(3.0)
        anchor = (100.0, 80.0)
        before = canvas.mapFromScene(QPointF(*anchor))

        _wheel(canvas, anchor, 2, Qt.KeyboardModifier.ControlModifier)

        assert canvas.zoom == pytest.approx(3.0 * SketchCanvas.WHEEL_ZOOM_STEP ** 2)
        after = canvas.mapFromScene(QPointF(*anchor))
        assert abs(after.x() - before.x()) <= 1 and abs(after.y() - before.y()) <= 1

    def test_zoom_is_limited_to_ten_percent_and_ten_times(self, canvas):
        _wheel(canvas, (200, 150), 40, Qt.KeyboardModifier.ControlModifier)
        assert canvas.zoom == pytest.approx(SketchCanvas.MAX_ZOOM)

        _wheel(canvas, (200, 150), -60, Qt.KeyboardModifier.ControlModifier)
        assert canvas.zoom == pytest.approx(SketchCanvas.MIN_ZOOM)

    def test_wheel_without_ctrl_does_not_zoom(self, canvas):
        _wheel(canvas, (200, 150), 2, NO_MODIFIER)

        assert canvas.zoom == 1.0

    def test_middle_drag_pans_a_zoomed_view(self, canvas):
        canvas.zoom_by(4.0)
        start = canvas.mapToScene(canvas.viewport().rect().center())

        press = canvas.mapFromScene(QPointF(100, 100))
        middle = Qt.MouseButton.MiddleButton
        # Viewport positions, fixed before the view starts moving.
        _mouse_at(canvas, QEvent.Type.MouseButtonPress, press, button=middle)
        _mouse_at(canvas, QEvent.Type.MouseMove, press - QPoint(40, 20), button=middle)
        _mouse_at(canvas, QEvent.Type.MouseMove, press - QPoint(80, 40), button=middle)
        _mouse_at(canvas, QEvent.Type.MouseButtonRelease, press - QPoint(80, 40), button=middle)

        # Content follows the pointer, so the view moves the other way.
        end = canvas.mapToScene(canvas.viewport().rect().center())
        assert end.x() == pytest.approx(start.x() + 20, abs=0.5)
        assert end.y() == pytest.approx(start.y() + 10, abs=0.5)

    def test_handles_keep_their_screen_size_when_zoomed(self, canvas, sketch):
        _add(sketch, RectangleElement(id="r", x=100, y=100, width=100, height=50, fill_color="#FF0000"))
        canvas.rebuild()
        canvas.set_selection(["r"])

        canvas.zoom_by(3.0)

        handle = next(iter(canvas._handles.values()))
        on_screen = handle.deviceTransform(canvas.viewportTransform()).mapRect(handle.rect())
        assert on_screen.width() == pytest.approx(SketchCanvas.HANDLE_SIZE_PX)
