"""Tests for ExportSketchDialog and the sketch tab's Export action."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget

from pandaplot.app import build_app_context, create_tab_factory
from pandaplot.gui.components.tabs.sketch.sketch_export import ExportFormat, ExportRegion, SketchExportOptions
from pandaplot.gui.components.tabs.sketch.sketch_tab import SketchTab
from pandaplot.gui.dialogs.sketch.export_sketch_dialog import ExportSketchDialog
from pandaplot.models.project import Project
from pandaplot.models.project.items.sketch import RectangleElement, Sketch, SketchLayer


@pytest.fixture
def app_context(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return build_app_context()


@pytest.fixture
def sketch(app_context) -> Sketch:
    sketch = Sketch(id="sketch-1", name="Plan", canvas_width=400.0, canvas_height=300.0, layers=[
        SketchLayer(id="shapes", name="Shapes", elements=[RectangleElement(x=10.0, y=10.0, width=50.0, height=40.0, stroke_width=0.0)]),
        SketchLayer(id="notes", name="Notes", visible=False),
    ])
    project = Project(name="Export")
    project.add_item(sketch)
    app_context.get_app_state().load_project(project)
    return sketch


@pytest.fixture
def dialog(qtbot, app_context, sketch) -> ExportSketchDialog:
    dialog = ExportSketchDialog(app_context, sketch)
    qtbot.addWidget(dialog)
    return dialog


def _check(dialog: ExportSketchDialog, layer_id: str, *, checked: bool) -> None:
    for row in range(dialog.layer_list.count()):
        item = dialog.layer_list.item(row)
        if item.data(Qt.ItemDataRole.UserRole) == layer_id:
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)


class TestDialog:
    def test_defaults(self, dialog):
        assert dialog.options() == SketchExportOptions(layer_ids=frozenset({"shapes"}))
        assert dialog.size_label.text() == "Output: 400 × 300 px"
        assert dialog.export_button.isEnabled()
        assert [dialog.layer_list.item(row).text() for row in range(dialog.layer_list.count())] == ["Notes (hidden)", "Shapes"]

    def test_starts_from_the_given_options(self, app_context, sketch, qtbot):
        initial = SketchExportOptions(
            format=ExportFormat.SVG, region=ExportRegion.ELEMENTS, transparent=True, scale=3.0, padding=4.0, layer_ids=frozenset({"notes", "shapes"}),
        )
        dialog = ExportSketchDialog(app_context, sketch, initial=initial)
        qtbot.addWidget(dialog)

        assert dialog.options() == initial

    @pytest.mark.parametrize(("export_format", "transparency", "scale"), [
        (ExportFormat.PNG, True, True),
        (ExportFormat.JPEG, False, True),
        (ExportFormat.SVG, True, False),
        (ExportFormat.PDF, False, False),
    ])
    def test_controls_follow_the_format(self, dialog, export_format, transparency, scale):
        dialog.transparent_radio.setChecked(True)

        dialog.format_combo.setCurrentIndex(dialog.format_combo.findData(export_format.value))

        assert dialog.transparent_radio.isEnabled() is transparency
        assert dialog.scale_input.isEnabled() is scale
        assert dialog.options().transparent is transparency

    def test_size_follows_scale_region_and_format(self, dialog):
        dialog.scale_input.setValue(2.0)
        assert dialog.size_label.text() == "Output: 800 × 600 px"

        dialog.elements_radio.setChecked(True)
        dialog.padding_input.setValue(5.0)
        assert dialog.size_label.text() == "Output: 120 × 100 px"

        dialog.format_combo.setCurrentIndex(dialog.format_combo.findData(ExportFormat.PDF.value))
        assert dialog.size_label.text() == "Output: 60 × 50 pt"

    def test_no_layers_disables_export(self, dialog):
        _check(dialog, "shapes", checked=False)

        assert not dialog.export_button.isEnabled()
        assert "Choose at least one layer" in dialog.size_label.text()

    def test_an_empty_elements_region_disables_export(self, dialog):
        _check(dialog, "shapes", checked=False)
        _check(dialog, "notes", checked=True)
        dialog.elements_radio.setChecked(True)

        assert not dialog.export_button.isEnabled()
        assert "no elements" in dialog.size_label.text()

    def test_too_large_disables_export(self, dialog, app_context, sketch, qtbot):
        sketch.canvas_width = sketch.canvas_height = 20000.0
        big = ExportSketchDialog(app_context, sketch)
        qtbot.addWidget(big)

        assert "too large" in big.size_label.text()
        assert not big.export_button.isEnabled()

    def test_ask_returns_none_when_cancelled(self, app_context, sketch, monkeypatch):
        monkeypatch.setattr(ExportSketchDialog, "exec", lambda self: ExportSketchDialog.DialogCode.Rejected)

        assert ExportSketchDialog.ask(app_context, sketch) is None

    def test_ask_returns_the_options_when_accepted(self, app_context, sketch, monkeypatch):
        def accept(self):
            self.format_combo.setCurrentIndex(self.format_combo.findData(ExportFormat.JPEG.value))
            return ExportSketchDialog.DialogCode.Accepted

        monkeypatch.setattr(ExportSketchDialog, "exec", accept)

        options = ExportSketchDialog.ask(app_context, sketch)

        assert options is not None and options.format is ExportFormat.JPEG


class TestTabExport:
    @pytest.fixture
    def container(self, qtbot) -> QWidget:
        # qtbot holds only a weak reference; the fixture keeps the tab's parent alive.
        container = QWidget()
        qtbot.addWidget(container)
        return container

    @pytest.fixture
    def tab(self, app_context, sketch, container) -> SketchTab:
        tab = create_tab_factory().create_tab(app_context, sketch, parent=container)
        assert isinstance(tab, SketchTab)
        return tab

    @pytest.fixture
    def out_dir(self, tmp_path):
        # tmp_path is also HOME, which holds the app's config folder.
        out_dir = tmp_path / "exports"
        out_dir.mkdir()
        return out_dir

    @pytest.fixture
    def asked(self, monkeypatch) -> list[SketchExportOptions | None]:
        """Initial options the dialog was opened with; it answers with PNG at 2x."""
        seen: list[SketchExportOptions | None] = []

        def ask(_app_context, _sketch, _parent=None, *, initial=None):
            seen.append(initial)
            return SketchExportOptions(scale=2.0, layer_ids=frozenset({"shapes"}))

        monkeypatch.setattr(ExportSketchDialog, "ask", staticmethod(ask))
        return seen

    def test_export_writes_the_file_and_reports_it(self, tab, app_context, monkeypatch, out_dir, asked):
        path = out_dir / "plan.png"
        requests = []

        def save_path(*args):
            requests.append(args)
            return str(path)

        monkeypatch.setattr(app_context.get_ui_controller(), "get_save_file_path", save_path)

        tab.export_action.trigger()

        assert QImage(str(path)).size().toTuple() == (800, 600)
        assert requests == [("Export Plan", "Plan.png", "PNG image (*.png)", ".png")]
        assert tab.status_label.text() == "Exported to plan.png"

    def test_the_next_export_starts_from_the_last_options(self, tab, app_context, monkeypatch, out_dir, asked):
        monkeypatch.setattr(app_context.get_ui_controller(), "get_save_file_path", lambda *_args: str(out_dir / "plan.png"))

        tab.export_action.trigger()
        tab.export_action.trigger()

        assert asked == [None, SketchExportOptions(scale=2.0, layer_ids=frozenset({"shapes"}))]

    def test_cancelling_the_file_dialog_writes_nothing(self, tab, app_context, monkeypatch, out_dir, asked):
        monkeypatch.setattr(app_context.get_ui_controller(), "get_save_file_path", lambda *_args: None)

        tab.export_action.trigger()

        assert list(out_dir.iterdir()) == []
        assert tab.status_label.text() == ""

    def test_a_failed_export_shows_an_error(self, tab, app_context, monkeypatch, out_dir, asked):
        errors = []
        monkeypatch.setattr(app_context.get_ui_controller(), "get_save_file_path", lambda *_args: str(out_dir / "missing" / "plan.png"))
        monkeypatch.setattr(app_context.get_ui_controller(), "show_error_message", lambda title, message: errors.append((title, message)))

        tab.export_action.trigger()

        assert len(errors) == 1
        assert errors[0][0] == "Export Failed"
        assert "Could not write" in errors[0][1]
