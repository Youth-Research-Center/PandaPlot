"""Tests for SketchPropertyBar, driven through its controls inside a real SketchTab."""
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from pandaplot.app import build_app_context, create_tab_factory
from pandaplot.gui.components.tabs.sketch.sketch_property_bar import MIXED, SketchPropertyBar
from pandaplot.gui.components.tabs.sketch.sketch_tab import SketchTab
from pandaplot.gui.components.tabs.sketch.tools.tool_manager import ToolMode
from pandaplot.models.project import Project
from pandaplot.models.project.items.sketch import (
    EllipseElement,
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
def app_context(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return build_app_context()


@pytest.fixture
def sketch(app_context) -> Sketch:
    sketch = Sketch(id="sketch-1", name="Diagram", canvas_width=800.0, canvas_height=500.0, layers=[SketchLayer(id="layer", elements=[
        RectangleElement(id="rect", x=50.0, y=50.0, width=100.0, height=60.0, stroke_color="#1D4ED8", stroke_width=4.0, fill_color="#F59E0B"),
        EllipseElement(id="ellipse", x=400.0, y=200.0, rx=80.0, ry=40.0, stroke_color="#1D4ED8", stroke_width=2.0, fill_color="#10B981"),
        LineElement(id="line", x=50.0, y=400.0, dx=500.0, stroke_color="#DC2626", stroke_width=2.0),
        TextElement(id="text", x=300.0, y=300.0, text="Label", font_size=30, is_bold=True),
    ])])
    project = Project(name="Styles")
    project.add_item(sketch)
    app_context.get_app_state().load_project(project)
    return sketch


@pytest.fixture
def container(qtbot):
    container = QWidget()
    qtbot.addWidget(container)
    return container


@pytest.fixture
def tab(app_context, sketch, container) -> SketchTab:
    tab = create_tab_factory().create_tab(app_context, sketch, parent=container)
    assert isinstance(tab, SketchTab)
    container.resize(1300, 650)
    tab.resize(1300, 650)
    container.show()
    return tab


@pytest.fixture
def bar(tab) -> SketchPropertyBar:
    return tab.property_bar


@pytest.fixture
def executor(app_context):
    return app_context.get_command_executor()


@pytest.fixture
def picked_colors(monkeypatch, app_context) -> list[str | None]:
    """Colours the colour dialog will return, in order; records nothing else."""
    answers: list[str | None] = []
    monkeypatch.setattr(app_context.get_ui_controller(), "get_color", lambda *_args, **_kwargs: answers.pop(0))
    return answers


def _element(sketch: Sketch, element_id: str) -> SketchElement:
    found = sketch.find_element(element_id)
    assert found is not None
    return found[1]


def _drag(tab: SketchTab, start: tuple[float, float], end: tuple[float, float]) -> None:
    viewport = tab.canvas.viewport()
    for kind, point in ((QEvent.Type.MouseButtonPress, start), (QEvent.Type.MouseMove, end), (QEvent.Type.MouseButtonRelease, end)):
        position = QPointF(tab.canvas.mapFromScene(QPointF(*point)))
        buttons = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton
        event = QMouseEvent(kind, position, QPointF(viewport.mapToGlobal(position.toPoint())), Qt.MouseButton.LeftButton, buttons,
                            Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(viewport, event)


def _enabled(bar: SketchPropertyBar) -> set[str]:
    return {name for name, widgets in bar.field_widgets.items() if all(widget.isEnabled() for widget in widgets)}


class TestShowingStyle:
    def test_with_nothing_selected_it_shows_the_new_element_style(self, bar, tab):
        assert bar.scope_label.text() == "New elements"
        assert _enabled(bar) == set(bar.field_widgets)
        style = tab.canvas.tool_manager.style
        assert bar.width_input.value() == style.stroke_width
        assert bar.style_combo.currentData() == style.stroke_style

    @pytest.mark.parametrize(("mode", "expected"), [
        (ToolMode.LINE, {"stroke_color", "stroke_width", "stroke_style"}),
        (ToolMode.RECTANGLE, {"stroke_color", "stroke_width", "stroke_style", "fill_color"}),
        (ToolMode.TEXT, {"stroke_color", "font_family", "font_size", "is_bold", "is_italic", "alignment"}),
    ])
    def test_a_drawing_tool_enables_only_what_its_elements_draw_with(self, bar, tab, mode, expected):
        tab.tool_actions[mode].trigger()

        assert _enabled(bar) == expected

    def test_one_selected_element_shows_its_values(self, bar, tab):
        tab.canvas.set_selection(["text"])

        assert bar.scope_label.text() == "Selection (1 element)"
        assert _enabled(bar) == {"stroke_color", "font_family", "font_size", "is_bold", "is_italic", "alignment"}
        assert bar.size_input.value() == 30
        assert bar.bold_action.isChecked()
        assert not bar.italic_action.isChecked()
        assert bar.alignment_actions[TextAlignment.LEFT].isChecked()
        assert bar.font_combo.currentText() == "Arial"

    def test_differing_values_show_mixed(self, bar, tab):
        tab.canvas.set_selection(["rect", "ellipse", "line"])

        assert bar.scope_label.text() == "Selection (3 elements)"
        assert bar.width_input.isMixed()
        assert bar.width_input.text() == MIXED
        # Same style on all three, so not mixed.
        assert bar.style_combo.currentData() == StrokeStyle.SOLID
        assert "Mixed" in bar.stroke_button.toolTip()
        assert "Mixed" in bar.fill_button.toolTip()
        # The line has no fill; the fill stays editable for the others.
        assert {"fill_color", "stroke_width"} <= _enabled(bar)
        assert "font_family" not in _enabled(bar)

    def test_values_shared_by_the_selection_are_not_mixed(self, bar, tab):
        tab.canvas.set_selection(["rect", "ellipse"])

        assert bar.stroke_button.toolTip() == "Stroke colour: #1D4ED8"
        assert bar.width_input.isMixed()


class TestChangingTheSelection:
    def test_a_color_applies_to_the_selection_and_undo_restores_it(self, bar, tab, sketch, executor, picked_colors):
        tab.canvas.set_selection(["rect", "line"])
        picked_colors.append("#22C55E")

        bar.stroke_button.click()

        assert _element(sketch, "rect").stroke_color == "#22C55E"
        assert _element(sketch, "line").stroke_color == "#22C55E"
        assert bar.stroke_button.toolTip() == "Stroke colour: #22C55E"
        assert len(executor.undo_stack) == 1

        executor.undo()

        assert _element(sketch, "rect").stroke_color == "#1D4ED8"
        assert bar.stroke_button.toolTip() == "Stroke colour: Mixed"
        assert tab.canvas.selected_ids == ("rect", "line")

    def test_a_cancelled_color_dialog_changes_nothing(self, bar, tab, executor, picked_colors):
        tab.canvas.set_selection(["rect"])
        picked_colors.append(None)

        bar.stroke_button.click()

        assert executor.undo_stack == []

    def test_fill_menu_removes_the_fill_of_shapes_only(self, bar, tab, sketch):
        tab.canvas.set_selection(["rect", "line"])

        bar.no_fill_action.trigger()

        assert _element(sketch, "rect").fill_color is None
        assert bar.fill_button.toolTip() == "Fill colour: none"

    def test_fill_menu_picks_a_translucent_fill(self, bar, tab, sketch, picked_colors):
        tab.canvas.set_selection(["ellipse"])
        picked_colors.append("#8010B981")

        bar.choose_fill_action.trigger()

        assert _element(sketch, "ellipse").fill_color == "#8010B981"

    def test_stepping_a_mixed_width_gives_every_element_one_width(self, bar, tab, sketch, executor):
        tab.canvas.set_selection(["rect", "ellipse"])
        bar.width_input.setFocus()

        QTest.keyClick(bar.width_input._edit, Qt.Key.Key_Up)

        # Steps from the first element's width (4.0) by 0.5.
        assert [_element(sketch, element_id).stroke_width for element_id in ("rect", "ellipse")] == [4.5, 4.5]
        assert not bar.width_input.isMixed()
        assert len(executor.undo_stack) == 1

    def test_line_style_combo(self, bar, tab, sketch):
        tab.canvas.set_selection(["line"])

        bar.style_combo.setCurrentIndex(bar.style_combo.findData(StrokeStyle.DASH_DOT))

        assert _element(sketch, "line").stroke_style is StrokeStyle.DASH_DOT

    def test_text_controls(self, bar, tab, sketch):
        tab.canvas.set_selection(["text"])
        text = _element(sketch, "text")
        assert isinstance(text, TextElement)

        bar.italic_action.trigger()
        bar.bold_action.trigger()
        bar.alignment_actions[TextAlignment.CENTER].trigger()
        bar.size_input.setValue(48)

        assert (text.is_italic, text.is_bold, text.alignment, text.font_size) == (True, False, TextAlignment.CENTER, 48)

    def test_clicking_the_checked_alignment_keeps_it(self, bar, tab, sketch, executor):
        tab.canvas.set_selection(["text"])

        bar.alignment_actions[TextAlignment.LEFT].trigger()

        assert bar.alignment_actions[TextAlignment.LEFT].isChecked()
        assert executor.undo_stack == []

    def test_font_family(self, bar, tab, sketch):
        tab.canvas.set_selection(["text"])
        family = next(bar.font_combo.itemText(index) for index in range(bar.font_combo.count()) if bar.font_combo.itemText(index) != "Arial")

        bar.font_combo.setCurrentIndex(bar.font_combo.findText(family))

        text = _element(sketch, "text")
        assert isinstance(text, TextElement)
        assert text.font_family == family

    def test_a_font_that_is_not_installed_is_still_shown(self, bar, tab, sketch):
        text = _element(sketch, "text")
        assert isinstance(text, TextElement)
        text.font_family = "Not A Real Font"

        tab.canvas.set_selection(["text"])

        assert bar.font_combo.currentText() == "Not A Real Font"

    def test_setting_the_value_it_already_has_adds_no_undo_step(self, bar, tab, executor):
        tab.canvas.set_selection(["rect"])

        bar.no_fill_action.trigger()
        bar.no_fill_action.trigger()

        assert len(executor.undo_stack) == 1


class TestNewElementStyle:
    def test_with_nothing_selected_changes_go_to_new_elements(self, bar, tab, sketch, executor, picked_colors):
        tab.tool_actions[ToolMode.RECTANGLE].trigger()
        picked_colors.append("#7C3AED")
        bar.stroke_button.click()
        bar.width_input.setValue(6.0)
        bar.style_combo.setCurrentIndex(bar.style_combo.findData(StrokeStyle.DOTTED))
        assert executor.undo_stack == []

        _drag(tab, (500.0, 50.0), (600.0, 120.0))

        drawn = sketch.layers[0].elements[-1]
        assert isinstance(drawn, RectangleElement)
        assert (drawn.stroke_color, drawn.stroke_width, drawn.stroke_style) == ("#7C3AED", 6.0, StrokeStyle.DOTTED)
        assert type(tab.canvas.tool_manager.style.stroke_style) is StrokeStyle
        # After drawing, the bar still shows the new-element style.
        assert bar.width_input.value() == 6.0

    def test_text_defaults_reach_new_labels(self, bar, tab, sketch, monkeypatch, app_context):
        tab.tool_actions[ToolMode.TEXT].trigger()
        bar.bold_action.trigger()
        bar.alignment_actions[TextAlignment.RIGHT].trigger()
        monkeypatch.setattr(app_context.get_ui_controller(), "get_text_input", lambda *_args: "New")

        _drag(tab, (600.0, 400.0), (600.0, 400.0))

        drawn = sketch.layers[0].elements[-1]
        assert isinstance(drawn, TextElement)
        assert (drawn.text, drawn.is_bold, drawn.alignment) == ("New", True, TextAlignment.RIGHT)
