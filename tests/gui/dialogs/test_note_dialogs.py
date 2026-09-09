"""Unit tests for note dialogs (NoteChartPickerDialog and NoteTablePickerDialog)."""

from unittest.mock import MagicMock

import pandas as pd

from pandaplot.gui.dialogs.note.note_chart_picker_dialog import NoteChartPickerDialog
from pandaplot.gui.dialogs.note.note_table_picker_dialog import (
    NoteTablePickerDialog,
    custom_to_markdown_table,
    dataset_to_markdown_table,
)
from pandaplot.models.project.items import Chart, Dataset, Folder
from pandaplot.models.project.project import Project


def _create_mock_app_context(project=None):
    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}
    app_context.get_manager.return_value.get_design_tokens.return_value = {}
    return app_context


def test_note_chart_picker_dialog_tree_and_selection(qapp):
    project = Project(name="Test Project")
    folder = Folder(name="Plots")
    chart1 = Chart(name="Line Plot")
    chart2 = Chart(name="Bar Plot")

    project.add_item(folder)
    project.add_item(chart1, parent_id=folder.id)
    project.add_item(chart2)

    app_context = _create_mock_app_context(project)

    dialog = NoteChartPickerDialog(app_context, project)
    assert dialog.tree.topLevelItemCount() == 2  # folder and chart2 at root

    # Initially no selection
    assert dialog.ok_button.isEnabled() is False
    assert dialog.get_selected_chart() is None

    # Find and select chart1 in tree
    folder_item = dialog.tree.topLevelItem(0)
    if folder_item.text(0) == "Plots":
        chart1_item = folder_item.child(0)
    else:
        chart1_item = dialog.tree.topLevelItem(1).child(0)

    dialog.tree.setCurrentItem(chart1_item)
    assert dialog.ok_button.isEnabled() is True

    dialog._on_ok_clicked()
    assert dialog.get_selected_chart() == chart1


def test_note_chart_picker_dialog_empty_state(qapp):
    project = Project(name="Empty Project")
    app_context = _create_mock_app_context(project)

    dialog = NoteChartPickerDialog(app_context, project)
    assert dialog.empty_label.isHidden() is False
    assert dialog.ok_button.isEnabled() is False
    assert dialog.get_selected_chart() is None


def test_custom_to_markdown_table():
    md = custom_to_markdown_table(rows=2, cols=2, include_header=True)
    expected = (
        "| Header 1 | Header 2 |\n"
        "| --- | --- |\n"
        "| Cell | Cell |\n"
        "| Cell | Cell |"
    )
    assert md == expected


def test_custom_to_markdown_table_without_header_still_has_blank_header_and_delimiter():
    md = custom_to_markdown_table(rows=1, cols=2, include_header=False)
    expected = (
        "|  |  |\n"
        "| --- | --- |\n"
        "| Cell | Cell |"
    )
    assert md == expected


def test_dataset_to_markdown_table():
    dataset = Dataset(name="Sample Data")
    dataset.df = pd.DataFrame({"X": [1, 2, 3], "Y": [10, 20, 30]})

    md_all = dataset_to_markdown_table(dataset)
    assert "| X | Y |" in md_all
    assert "| 1 | 10 |" in md_all
    assert "| 3 | 30 |" in md_all

    md_limited = dataset_to_markdown_table(dataset, max_rows=1)
    assert "| 1 | 10 |" in md_limited
    assert "| 2 | 20 |" not in md_limited


def test_custom_to_markdown_table_without_header_is_still_a_valid_table():
    """A Markdown table needs a header + delimiter row structurally, even
    when the user doesn't want visible header labels -- otherwise the
    "table" is just plain pipe-delimited text lines to any Markdown
    renderer (see PR #383 review)."""
    from markdown import markdown

    md = custom_to_markdown_table(rows=2, cols=2, include_header=False)
    lines = md.split("\n")

    assert lines[1] == "| --- | --- |"  # delimiter row must be the second line
    html = markdown(md, extensions=["tables"])
    assert "<table>" in html


def test_dataset_to_markdown_table_escapes_pipes_and_newlines():
    dataset = Dataset(name="Messy Data")
    dataset.df = pd.DataFrame({
        "Note": ["a | b", "line1\nline2"],
        "Value": [1, 2],
    })

    md = dataset_to_markdown_table(dataset)

    lines = md.split("\n")
    assert len(lines) == 4  # header, separator, 2 data rows -- no extra rows from embedded newlines
    assert "a \\| b" in md
    assert "line1 line2" in md


def test_dataset_to_markdown_table_preserves_literal_nan_string():
    dataset = Dataset(name="Mixed Data")
    dataset.df = pd.DataFrame({
        "Label": ["nan", "real value"],
        "Value": [float("nan"), 2],
    })

    md = dataset_to_markdown_table(dataset)

    assert "| nan |  |" in md  # literal string "nan" preserved as a real cell value
    assert "| real value | 2.0 |" in md  # a true NaN elsewhere still renders as an empty cell


def test_note_table_picker_no_datasets_label_uses_theme_palette(qapp):
    project = Project(name="Empty Dataset Project")
    app_context = _create_mock_app_context(project)
    app_context.get_manager.return_value.get_surface_palette.return_value = {"secondary_fg": "#123456"}

    dialog = NoteTablePickerDialog(app_context, project)

    assert "#123456" in dialog.no_datasets_label.styleSheet()


def test_note_table_picker_dialog_from_dataset(qapp):
    project = Project(name="Dataset Project")
    dataset = Dataset(name="Data 1")
    dataset.df = pd.DataFrame({"A": [100, 200], "B": [300, 400]})
    project.add_item(dataset)

    app_context = _create_mock_app_context(project)

    dialog = NoteTablePickerDialog(app_context, project)
    dialog.tab_widget.setCurrentIndex(0)  # Dataset tab
    assert dialog.ok_button.isEnabled() is True

    md = dialog.get_markdown_table()
    assert "| A | B |" in md
    assert "| 100 | 300 |" in md
