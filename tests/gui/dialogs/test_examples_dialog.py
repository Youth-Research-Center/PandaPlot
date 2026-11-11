"""Tests for ExamplesDialog: cards, search and tag filters, details page and opening."""

import sys

import pytest
from PySide6.QtCore import QEvent, QObject, Qt, QUrl
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QApplication, QDialog

from pandaplot.app import build_app_context
from pandaplot.gui.dialogs import examples_dialog as examples_dialog_module
from pandaplot.gui.dialogs.example_card import CoverSource, describe_contents
from pandaplot.gui.dialogs.examples_dialog import ExamplesDialog
from pandaplot.models.project.example_info import ExampleLevel, ExampleSection, example_tag
from pandaplot.models.project.items import Chart
from pandaplot.services.example_project_loader import ExampleProjectLoader
from pandaplot.utils.examples import ExampleProject, discover_example_projects


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _png(color: str) -> bytes:
    image = QImage(40, 30, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
    from PySide6.QtCore import QBuffer, QIODevice

    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def _example(name: str = "Demo", **overrides) -> ExampleProject:
    fields = {
        "path": f"/examples/{name}.pplot", "name": name, "summary": f"{name} summary.", "description": f"# {name}\n\nLong **text** for {name}.",
        "section": ExampleSection.GETTING_STARTED, "level": ExampleLevel.BEGINNER, "tags": (), "featured_chart_ids": (), "start_note_id": None,
        "data_credit": "", "cover_image": None, "dataset_count": 0, "chart_count": 0, "note_count": 0,
    }
    fields.update(overrides)
    return ExampleProject(**fields)


def _tags(*tag_ids: str):
    return tuple(example_tag(tag_id) for tag_id in tag_ids)


class _FakeProject:
    def __init__(self, charts: dict[str, Chart]):
        self._charts = charts

    def find_item(self, item_id: str):
        return self._charts.get(item_id)


@pytest.fixture
def make_dialog(qtbot, monkeypatch):
    """Build a dialog over the given examples. Real ``exec()`` is never called: tests use show() and result()."""
    _qapp()

    def factory(examples: list[ExampleProject], *, charts: dict[str, Chart] | None = None) -> ExamplesDialog:
        monkeypatch.setattr(examples_dialog_module, "discover_example_projects", lambda: examples)
        monkeypatch.setattr(ExampleProjectLoader, "load", lambda _self, _example: _FakeProject(charts or {}))
        dialog = ExamplesDialog(build_app_context())
        qtbot.addWidget(dialog)
        dialog.show()
        return dialog

    return factory


class _RenderLog(list):
    """Names of the charts rendered; ``sizes`` holds the ``max_size_px`` each render was asked for."""

    sizes: list


def _patch_renderer(monkeypatch, *, fail_for: frozenset[str] = frozenset()) -> _RenderLog:
    """Replace the headless renderer with a fake that paints a blue image; returns the rendered chart names."""
    from pandaplot.gui.components.tabs.chart import chart_editor

    rendered = _RenderLog()
    requested_sizes: list[tuple[int, int] | None] = []
    rendered.sizes = requested_sizes

    def fake_render(chart, _series, _defaults, *, max_size_px=None):
        rendered.append(chart.name)
        requested_sizes.append(max_size_px)
        if chart.name in fail_for:
            return None
        image = QImage(80, 60, QImage.Format.Format_RGB32)
        image.fill(QColor("#0000ff"))
        return image

    monkeypatch.setattr(chart_editor, "render_chart_to_qimage", fake_render)
    return rendered


def _tagged_examples() -> list[ExampleProject]:
    return [
        _example("Pendulum", tags=_tags("physics", "curve_fitting"), description="Damped oscillation."),
        _example("Spring", tags=_tags("physics", "smoothing")),
        _example("Survey", tags=_tags("statistics", "curve_fitting"), section=ExampleSection.ANALYSING_DATA),
    ]


def _names(dialog: ExamplesDialog) -> list[str]:
    return [card.example.name for card in dialog.visible_cards]


# ---------------------------------------------------------------------------------------------- list page


def test_example_card_exposes_its_title_and_summary_to_assistive_tech(make_dialog):
    dialog = make_dialog([_example("Damped Oscillator", summary="A fitted decay curve.")])

    card = dialog.cards[0]

    assert card.accessibleName() == "Damped Oscillator"
    assert card.accessibleDescription() == "A fitted decay curve."
    assert card.focusPolicy() == Qt.FocusPolicy.StrongFocus


def test_header_search_box_and_focus(make_dialog):
    dialog = make_dialog([_example()])

    assert dialog.title_label.text() == "Examples"
    assert "your copy won't change the original" in dialog.subtitle_label.text()
    assert dialog.search_edit.placeholderText() == "Search examples"
    assert dialog.focusWidget() is dialog.search_edit


def test_cards_are_grouped_under_section_headers_in_section_order_skipping_empty_sections(make_dialog):
    dialog = make_dialog([
        _example("A", section=ExampleSection.GETTING_STARTED),
        _example("B", section=ExampleSection.CHARTS),
    ])

    assert list(dialog.section_headers) == [ExampleSection.GETTING_STARTED, ExampleSection.CHARTS]
    assert [header.text() for header in dialog.section_headers.values()] == ["GETTING STARTED", "CHARTS"]
    assert ExampleSection.ANALYSING_DATA not in dialog.section_grids


def test_card_shows_title_summary_level_tags_and_contents(make_dialog):
    dialog = make_dialog([_example(
        "Pendulum", level=ExampleLevel.INTERMEDIATE, tags=_tags("physics", "smoothing"), dataset_count=2, chart_count=4, note_count=1,
    )])
    card = dialog.cards[0]

    assert card.title_label.text() == "Pendulum"
    assert card.summary_label.text() == "Pendulum summary."
    assert card.meta_row.level_label.text() == "Intermediate"
    assert [label.text() for label in card.meta_row.tag_labels] == ["Physics", "Smoothing"]
    assert card.contents_label.text() == "2 datasets · 4 charts · 1 note"
    assert card.details_button.text() == "See details"
    assert card.open_button.text() == "Open example"


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        ((1, 1, 1), "1 dataset · 1 chart · 1 note"),
        ((2, 0, 3), "2 datasets · 3 notes"),
        ((0, 1, 0), "1 chart"),
        ((0, 0, 0), ""),
    ],
)
def test_contents_wording_skips_zero_counts_and_pluralises(counts, expected):
    example = _example(dataset_count=counts[0], chart_count=counts[1], note_count=counts[2])

    assert describe_contents(example) == expected


def test_cover_uses_the_cover_image_bytes(make_dialog):
    dialog = make_dialog([_example(cover_image=_png("#ff0000"), featured_chart_ids=("c1",))])
    card = dialog.cards[0]

    assert card.cover_source is CoverSource.COVER_IMAGE
    assert card.cover.pixmap.toImage().pixelColor(5, 5) == QColor("#ff0000")


def test_cover_without_image_is_a_lazy_render_of_the_first_featured_chart(make_dialog, monkeypatch, qtbot):
    rendered = _patch_renderer(monkeypatch)
    charts = {"c1": Chart(id="c1", name="First"), "c2": Chart(id="c2", name="Second")}
    dialog = make_dialog([_example(featured_chart_ids=("c1", "c2"))], charts=charts)
    card = dialog.cards[0]

    assert card.cover_source is CoverSource.PLACEHOLDER  # nothing is rendered before the event loop runs
    qtbot.waitUntil(lambda: card.cover_source is CoverSource.CHART_RENDER)

    assert rendered == ["First"]
    assert card.cover.pixmap.toImage().pixelColor(5, 5) == QColor("#0000ff")


def test_cover_is_a_placeholder_without_image_or_featured_chart_or_when_rendering_fails(make_dialog, monkeypatch, qtbot):
    _patch_renderer(monkeypatch, fail_for=frozenset({"Broken"}))
    charts = {"c1": Chart(id="c1", name="Broken")}
    dialog = make_dialog([_example("Bare"), _example("Failing", featured_chart_ids=("c1",))], charts=charts)
    qtbot.wait(50)

    assert [card.cover_source for card in dialog.cards] == [CoverSource.PLACEHOLDER, CoverSource.PLACEHOLDER]
    assert not dialog.cards[0].cover.pixmap.isNull()


def test_chart_renders_are_cached_per_dialog(make_dialog, monkeypatch, qtbot):
    rendered = _patch_renderer(monkeypatch)
    charts = {"c1": Chart(id="c1", name="First")}
    dialog = make_dialog([_example(featured_chart_ids=("c1",))], charts=charts)
    qtbot.waitUntil(lambda: dialog.cards[0].cover_source is CoverSource.CHART_RENDER)

    dialog._show_details(dialog.cards[0].example)
    qtbot.waitUntil(lambda: dialog.preview_images[0].pixmap() is not None and not dialog.preview_images[0].pixmap().isNull())

    assert rendered == ["First"]


def test_chips_are_hidden_when_no_example_has_tags(make_dialog):
    dialog = make_dialog([_example("A"), _example("B")])

    assert dialog.tag_chips == {}
    assert dialog.chips_widget.isHidden()


def test_chips_show_only_used_tags_with_counts_in_two_labelled_rows(make_dialog):
    dialog = make_dialog(_tagged_examples())

    assert set(dialog.tag_chips) == {"physics", "statistics", "curve_fitting", "smoothing"}
    assert {group.value: label.text() for group, label in dialog.group_labels.items()} == {"topic": "Topic", "technique": "Technique"}
    assert dialog.tag_chips["physics"].text() == "Physics (2)"
    assert dialog.tag_chips["curve_fitting"].text() == "Curve fitting (2)"
    assert all(chip.isCheckable() for chip in dialog.tag_chips.values())


def test_chip_counts_update_and_unavailable_tags_are_disabled(make_dialog):
    dialog = make_dialog(_tagged_examples())

    dialog.tag_chips["physics"].click()

    assert _names(dialog) == ["Pendulum", "Spring"]
    assert dialog.tag_chips["statistics"].text() == "Statistics (3)"  # OR within the group
    assert dialog.tag_chips["curve_fitting"].text() == "Curve fitting (1)"  # AND across groups

    dialog.search_edit.setText("damped")

    assert dialog.tag_chips["smoothing"].text() == "Smoothing (0)"
    assert not dialog.tag_chips["smoothing"].isEnabled()
    assert dialog.tag_chips["physics"].isEnabled()  # selected, so it stays usable


def test_search_filters_as_you_type_and_hides_empty_sections(make_dialog):
    dialog = make_dialog(_tagged_examples())

    dialog.search_edit.setText("survey")

    assert _names(dialog) == ["Survey"]
    assert dialog.section_headers[ExampleSection.GETTING_STARTED].isHidden()
    assert not dialog.section_headers[ExampleSection.ANALYSING_DATA].isHidden()
    assert dialog.empty_panel.isHidden()


def test_clear_filters_is_enabled_only_when_something_is_set_and_resets_chips_and_search(make_dialog):
    dialog = make_dialog(_tagged_examples())
    assert not dialog.clear_button.isEnabled()

    dialog.tag_chips["statistics"].click()
    dialog.search_edit.setText("sur")
    assert dialog.clear_button.isEnabled()
    dialog.clear_button.click()

    assert dialog.search_edit.text() == ""
    assert dialog.selected_tag_ids == frozenset()
    assert not any(chip.isChecked() for chip in dialog.tag_chips.values())
    assert len(_names(dialog)) == 3
    assert not dialog.clear_button.isEnabled()


def test_no_results_shows_the_empty_state_whose_button_clears_the_filters(make_dialog):
    dialog = make_dialog(_tagged_examples())

    dialog.search_edit.setText("zzzz")

    assert not dialog.empty_panel.isHidden()
    assert dialog.empty_panel.heading_label.text() == "No examples match"
    assert dialog.empty_panel.description_label.text() == "Try other words or fewer filters."
    assert dialog.visible_cards == []
    assert all(card.isHidden() for card in dialog.cards)

    dialog.empty_panel.action_buttons[0].click()

    assert dialog.empty_panel.isHidden()
    assert len(_names(dialog)) == 3


def test_no_examples_at_all_shows_the_not_found_message(make_dialog):
    dialog = make_dialog([])

    assert not dialog.no_examples_label.isHidden()
    assert dialog.no_examples_label.text() == "No example projects were found."
    assert dialog.empty_panel.isHidden()


def test_cards_use_two_columns_when_wide_and_one_when_narrow(make_dialog, qtbot):
    dialog = make_dialog([_example("A"), _example("B")])
    grid = dialog.section_grids[ExampleSection.GETTING_STARTED]
    assert grid.getItemPosition(1)[:2] == (0, 1)

    dialog.resize(600, 640)
    qtbot.waitUntil(lambda: grid.getItemPosition(1)[:2] == (1, 0))

    dialog.resize(900, 640)
    qtbot.waitUntil(lambda: grid.getItemPosition(1)[:2] == (0, 1))


def test_enter_on_a_focused_card_opens_its_details(make_dialog, qtbot):
    dialog = make_dialog([_example("Demo")])
    card = dialog.cards[0]
    card.setFocus()

    qtbot.keyClick(card, Qt.Key.Key_Return)

    assert dialog.stack.currentWidget() is dialog.details_page
    assert dialog.details_title.text() == "Demo"


# ---------------------------------------------------------------------------------------------- details page


def test_details_show_the_rendered_description_level_contents_and_credit(make_dialog):
    example = _example(
        "Pendulum", level=ExampleLevel.INTERMEDIATE, tags=_tags("physics"), dataset_count=1, chart_count=2, data_credit="Data: Example Lab",
    )
    dialog = make_dialog([example])

    dialog.cards[0].details_button.click()

    assert dialog.stack.currentWidget() is dialog.details_page
    assert dialog.details_title.text() == "Pendulum"
    assert dialog.details_meta.level_label.text() == "Intermediate"
    assert [label.text() for label in dialog.details_meta.tag_labels] == ["Physics"]
    assert dialog.details_contents.text() == "What's inside: 1 dataset · 2 charts"
    assert dialog.description_browser.isReadOnly()
    assert "<strong>text</strong>" in dialog.description_browser.toHtml() or "text" in dialog.description_browser.toPlainText()
    assert "Long text for Pendulum." in dialog.description_browser.toPlainText()
    assert not dialog.credit_label.isHidden()
    assert dialog.credit_label.text() == "Data: Example Lab"


def test_details_fall_back_to_the_summary_and_hide_empty_credit_and_previews(make_dialog):
    dialog = make_dialog([_example("Bare", description="", summary="Only a summary.")])

    dialog.cards[0].details_button.click()

    assert "Only a summary." in dialog.description_browser.toPlainText()
    assert dialog.credit_label.isHidden()
    assert dialog.credit_header.isHidden()
    assert dialog.previews_host.isHidden()


def test_details_render_featured_chart_previews_with_captions_and_a_placeholder_for_failures(make_dialog, monkeypatch, qtbot):
    _patch_renderer(monkeypatch, fail_for=frozenset({"Broken chart"}))
    charts = {"c1": Chart(id="c1", name="Decay"), "c2": Chart(id="c2", name="Broken chart"), "c3": Chart(id="c3", name="Fit")}
    dialog = make_dialog([_example(featured_chart_ids=("c1", "c2", "c3"))], charts=charts)

    dialog.cards[0].details_button.click()
    qtbot.waitUntil(lambda: [label.text() for label in dialog.preview_captions] == ["Decay", "Broken chart", "Fit"])

    images = dialog.preview_images
    assert images[0].pixmap() is not None and not images[0].pixmap().isNull()
    assert images[1].text() == "Preview not available"
    assert images[1].pixmap() is None or images[1].pixmap().isNull()
    assert not images[2].pixmap().isNull()
    assert dialog.result() == QDialog.DialogCode.Rejected  # a failed render never opens or closes anything


def test_preview_for_a_missing_chart_shows_the_placeholder(make_dialog, qtbot):
    dialog = make_dialog([_example(featured_chart_ids=("gone",))], charts={})

    dialog.cards[0].details_button.click()

    qtbot.waitUntil(lambda: dialog.preview_images[0].text() == "Preview not available")


def test_back_keeps_query_chips_and_scroll_position(make_dialog, qtbot):
    examples = [_example(f"Ex{index:02d}", tags=_tags("physics")) for index in range(12)] + [_example("Other", tags=_tags("statistics"))]
    dialog = make_dialog(examples)
    dialog.resize(900, 300)
    dialog.tag_chips["physics"].click()
    dialog.search_edit.setText("ex")
    scrollbar = dialog.list_scroll.verticalScrollBar()
    qtbot.waitUntil(lambda: scrollbar.maximum() > 100)
    scrollbar.setValue(120)
    card = dialog.visible_cards[3]

    card.details_button.click()
    assert dialog.stack.currentWidget() is dialog.details_page
    dialog.back_button.click()

    assert dialog.stack.currentWidget() is dialog.list_page
    assert dialog.search_edit.text() == "ex"
    assert dialog.selected_tag_ids == frozenset({"physics"})
    assert dialog.tag_chips["physics"].isChecked()
    assert scrollbar.value() == 120
    assert dialog.focusWidget() is card


def test_back_returns_focus_to_the_see_details_button_that_was_pressed(make_dialog, qtbot):
    dialog = make_dialog([_example("A"), _example("B")])
    card = dialog.cards[1]
    card.details_button.setFocus()
    qtbot.waitUntil(lambda: dialog.focusWidget() is card.details_button)

    qtbot.keyClick(card.details_button, Qt.Key.Key_Return)
    assert dialog.stack.currentWidget() is dialog.details_page
    dialog.back_button.click()

    assert dialog.focusWidget() is card.details_button


def test_back_after_enter_on_the_card_returns_focus_to_the_card(make_dialog, qtbot):
    dialog = make_dialog([_example("A")])
    card = dialog.cards[0]
    card.setFocus()
    qtbot.waitUntil(lambda: dialog.focusWidget() is card)

    qtbot.keyClick(card, Qt.Key.Key_Return)
    dialog.back_button.click()

    assert dialog.focusWidget() is card


def test_closing_unsubscribes_the_dialog_from_the_event_bus(make_dialog):
    from pandaplot.models.events.event_types import ThemeEvents

    dialog = make_dialog([_example()])
    bus = dialog.app_context.event_bus
    assert dialog._on_theme_changed in bus._subscribers[ThemeEvents.THEME_CHANGED]

    dialog.reject()

    assert dialog._on_theme_changed not in bus._subscribers.get(ThemeEvents.THEME_CHANGED, [])


def test_bottom_back_button_also_returns_to_the_list(make_dialog):
    dialog = make_dialog([_example()])
    dialog.cards[0].details_button.click()

    dialog.bottom_back_button.click()

    assert dialog.stack.currentWidget() is dialog.list_page


def test_escape_goes_back_on_details_and_rejects_on_the_list(make_dialog, qtbot):
    dialog = make_dialog([_example()])
    dialog.cards[0].details_button.click()

    qtbot.keyClick(dialog, Qt.Key.Key_Escape)

    assert dialog.stack.currentWidget() is dialog.list_page
    assert dialog.isVisible()

    qtbot.keyClick(dialog, Qt.Key.Key_Escape)

    assert dialog.result() == QDialog.DialogCode.Rejected
    assert not dialog.isVisible()


# ---------------------------------------------------------------------------------------------- opening


def test_open_example_on_a_card_sets_selected_path_and_accepts(make_dialog):
    dialog = make_dialog([_example("A"), _example("B")])
    accepted = []
    dialog.accepted.connect(lambda: accepted.append(True))

    dialog.cards[1].open_button.click()

    assert dialog.selected_path == "/examples/B.pplot"
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert accepted == [True]


def test_open_example_on_the_details_page_sets_selected_path_and_accepts(make_dialog):
    dialog = make_dialog([_example("A"), _example("B")])
    dialog.cards[0].details_button.click()

    dialog.details_open_button.click()

    assert dialog.selected_path == "/examples/A.pplot"
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_cancel_rejects_without_a_selection(make_dialog):
    dialog = make_dialog([_example()])

    dialog.close_btn.click()

    assert dialog.selected_path is None
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_enter_in_the_search_box_does_not_open_an_example(make_dialog, qtbot):
    dialog = make_dialog([_example()])

    qtbot.keyClick(dialog.search_edit, Qt.Key.Key_Return)

    assert dialog.selected_path is None
    assert dialog.result() != QDialog.DialogCode.Accepted


# ---------------------------------------------------------------------------------------------- real examples


def test_the_bundled_examples_open_in_the_dialog_and_render_a_real_chart_preview(qtbot):
    _qapp()
    examples = discover_example_projects()
    assert examples
    dialog = ExamplesDialog(build_app_context())
    qtbot.addWidget(dialog)
    dialog.show()
    assert len(dialog.cards) == len(examples)
    assert all(card.title_label.text() for card in dialog.cards)

    context = build_app_context()
    project = ExampleProjectLoader(context).load(examples[0])
    chart = next(item for item in project.get_all_items() if isinstance(item, Chart) and item.data_series)
    featured = ExampleProject(**{**examples[0].__dict__, "featured_chart_ids": (chart.id,)})
    dialog._examples = [featured]
    dialog.cards[0].example = featured

    dialog._show_details(featured)
    qtbot.waitUntil(lambda: dialog.preview_captions[0].text() == chart.name, timeout=20000)

    pixmap = dialog.preview_images[0].pixmap()
    assert isinstance(pixmap, QPixmap)
    assert not pixmap.isNull()


# ---------------------------------------------------------------------------------------------- review fixes


def test_closing_releases_the_loaded_projects_pictures_and_covers(make_dialog, monkeypatch, qtbot):
    _patch_renderer(monkeypatch)
    charts = {"c1": Chart(id="c1", name="First")}
    dialog = make_dialog([_example(featured_chart_ids=("c1",))], charts=charts)
    qtbot.waitUntil(lambda: dialog.cards[0].cover_source is CoverSource.CHART_RENDER)
    dialog._loader._projects["/examples/Demo.pplot"] = None
    assert dialog._chart_pixmaps
    assert dialog._loader._projects

    dialog.reject()

    assert dialog._chart_pixmaps == {}
    assert dialog._loader._projects == {}
    assert dialog.cards[0].cover.pixmap is None


def test_a_render_scheduled_before_closing_does_not_reload_anything(make_dialog, monkeypatch, qtbot):
    rendered = _patch_renderer(monkeypatch)
    charts = {"c1": Chart(id="c1", name="First")}
    dialog = make_dialog([_example(featured_chart_ids=("c1",))], charts=charts)

    dialog.reject()  # before the cover's single-shot render has run
    qtbot.wait(50)

    assert rendered == []
    assert dialog._chart_pixmaps == {}


def test_covers_render_only_for_cards_in_view_and_the_rest_after_scrolling(make_dialog, monkeypatch, qtbot):
    rendered = _patch_renderer(monkeypatch)
    names = [f"Ex{number:02d}" for number in range(24)]
    charts = {f"c{number}": Chart(id=f"c{number}", name=name) for number, name in enumerate(names)}
    examples = [_example(name, featured_chart_ids=(f"c{number}",)) for number, name in enumerate(names)]
    dialog = make_dialog(examples, charts=charts)
    qtbot.waitUntil(lambda: len(rendered) > 0)
    qtbot.wait(100)

    assert 0 < len(rendered) < len(names)
    assert dialog.cards[-1].cover_source is CoverSource.PLACEHOLDER
    first_batch = list(rendered)

    scrollbar = dialog.list_scroll.verticalScrollBar()
    scrollbar.setValue(scrollbar.maximum())
    qtbot.waitUntil(lambda: dialog.cards[-1].cover_source is CoverSource.CHART_RENDER)

    assert rendered[: len(first_batch)] == first_batch  # nothing was rendered twice
    assert len(set(rendered)) == len(rendered)
    assert len(rendered) < len(names)  # the middle was never in view



def test_back_requests_covers_for_cards_brought_into_view_while_details_were_open(make_dialog, monkeypatch, qtbot):
    rendered = _patch_renderer(monkeypatch)
    names = [f"Ex{number:02d}" for number in range(24)]
    charts = {f"c{number}": Chart(id=f"c{number}", name=name) for number, name in enumerate(names)}
    examples = [_example(name, featured_chart_ids=(f"c{number}",)) for number, name in enumerate(names)]
    dialog = make_dialog(examples, charts=charts)
    qtbot.waitUntil(lambda: len(rendered) > 0)
    qtbot.wait(100)
    last = dialog.cards[-1]
    assert last.cover_source is CoverSource.PLACEHOLDER

    dialog.cards[0].details_button.click()
    # Enlarged while the list is hidden: every card now fits, but the hidden list cannot request covers.
    dialog.resize(dialog.width(), 20000)
    qtbot.wait(100)
    assert last.cover_source is CoverSource.PLACEHOLDER

    dialog.back_button.click()

    qtbot.waitUntil(lambda: last.cover_source is CoverSource.CHART_RENDER)
    assert len(set(rendered)) == len(rendered)  # nothing was rendered twice

def test_renders_are_requested_at_thumbnail_size_times_the_device_pixel_ratio(make_dialog, monkeypatch, qtbot):
    rendered = _patch_renderer(monkeypatch)
    charts = {"c1": Chart(id="c1", name="First")}
    dialog = make_dialog([_example(featured_chart_ids=("c1",))], charts=charts)
    monkeypatch.setattr(dialog, "devicePixelRatioF", lambda: 2.0)

    dialog.cards[0].details_button.click()
    shown: list[QPixmap] = []
    label = dialog.preview_images[0]
    original = label.setPixmap
    monkeypatch.setattr(label, "setPixmap", lambda pixmap: (shown.append(pixmap), original(pixmap))[1])
    qtbot.waitUntil(lambda: bool(shown))

    assert rendered.sizes[-1] == (examples_dialog_module.PREVIEW_WIDTH * 2, examples_dialog_module.PREVIEW_HEIGHT * 2)
    pixmap = shown[0]
    assert pixmap.devicePixelRatio() == 2.0
    assert pixmap.width() <= examples_dialog_module.PREVIEW_WIDTH * 2
    assert pixmap.height() <= examples_dialog_module.PREVIEW_HEIGHT * 2


def test_enter_presses_the_focused_button_but_not_from_the_search_box(make_dialog, qtbot):
    dialog = make_dialog([_example("Demo")])
    card = dialog.cards[0]

    card.open_button.setFocus()
    qtbot.keyClick(card.open_button, Qt.Key.Key_Return)

    assert dialog.selected_path == "/examples/Demo.pplot"
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_enter_on_a_focused_see_details_button_opens_the_details(make_dialog, qtbot):
    dialog = make_dialog([_example("Demo")])

    qtbot.keyClick(dialog.cards[0].details_button, Qt.Key.Key_Enter)

    assert dialog.stack.currentWidget() is dialog.details_page
    assert dialog.selected_path is None


def test_enter_on_the_cancel_button_closes_the_dialog(make_dialog, qtbot):
    dialog = make_dialog([_example("Demo")])

    qtbot.keyClick(dialog.close_btn, Qt.Key.Key_Return)

    assert dialog.result() == QDialog.DialogCode.Rejected
    assert not dialog.isVisible()


def test_clicking_a_relative_link_in_the_description_keeps_the_document(make_dialog, qtbot):
    dialog = make_dialog([_example("Demo", description="See [other](other.md) for more.")])
    dialog.cards[0].details_button.click()
    browser = dialog.description_browser
    before = browser.toPlainText()
    cursor = browser.document().find("other")
    assert not cursor.isNull()
    assert browser.anchorAt(browser.cursorRect(cursor).center()) == "other.md"

    qtbot.mouseClick(browser.viewport(), Qt.MouseButton.LeftButton, pos=browser.cursorRect(cursor).center())

    assert browser.toPlainText() == before
    assert not browser.openLinks()


def test_web_links_open_externally_and_others_are_ignored(make_dialog, monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(examples_dialog_module.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    dialog = make_dialog([_example("Demo")])
    browser = dialog.description_browser

    for link in ("https://example.org/a", "mailto:a@example.org", "other.md", "file:///etc/passwd"):
        browser.anchorClicked.emit(QUrl(link))

    assert opened == ["https://example.org/a", "mailto:a@example.org"]


def test_switching_examples_removes_the_old_meta_row_and_preview_tiles_from_view(make_dialog):
    dialog = make_dialog([_example("A", featured_chart_ids=("c1", "c2"), tags=_tags("physics")), _example("B", featured_chart_ids=("c3",))])
    dialog.cards[0].details_button.click()
    old_meta = dialog.details_meta
    old_tiles = list(dialog.preview_tiles)
    assert len(old_tiles) == 2

    dialog._show_list()
    dialog.cards[1].details_button.click()

    assert old_meta.parent() is None and not old_meta.isVisible()
    assert all(tile.parent() is None and not tile.isVisible() for tile in old_tiles)
    assert len(dialog.preview_tiles) == 1
    assert dialog.details_meta.parent() is not None


def test_unchanged_visible_set_does_not_rebuild_the_grids(make_dialog, monkeypatch):
    dialog = make_dialog(_tagged_examples())
    calls: list[int] = []
    grid = dialog.section_grids[ExampleSection.GETTING_STARTED]
    original = grid.takeAt
    monkeypatch.setattr(grid, "takeAt", lambda index: calls.append(index) or original(index))

    dialog._refresh()
    assert calls == []

    dialog.search_edit.setText("Spring")
    assert calls


class _TopLevelShowRecorder(QObject):
    """Application-wide event filter that records every top-level widget that receives a Show event."""

    def __init__(self) -> None:
        super().__init__()
        self.shown: list = []

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.Show and watched.isWidgetType() and watched.isWindow():
            self.shown.append(watched)
        return False


def test_opening_the_dialog_and_its_details_shows_no_stray_top_level_windows(make_dialog, monkeypatch, qtbot):
    _patch_renderer(monkeypatch)
    charts = {"c1": Chart(id="c1", name="Decay"), "c2": Chart(id="c2", name="Fit")}
    examples = [
        _example(
            f"Ex{index}", tags=_tags("physics", "statistics"), featured_chart_ids=("c1", "c2"), data_credit="Credit.",
            dataset_count=1, chart_count=2, note_count=1,
        )
        for index in range(4)
    ] + [_example("Bare", summary="")]
    recorder = _TopLevelShowRecorder()
    app = _qapp()
    app.installEventFilter(recorder)
    try:
        dialog = make_dialog(examples, charts=charts)
        app.processEvents()
        dialog.cards[0].details_button.click()
        qtbot.waitUntil(lambda: [label.text() for label in dialog.preview_captions] == ["Decay", "Fit"])
        dialog.back_button.click()
        app.processEvents()
    finally:
        app.removeEventFilter(recorder)

    assert recorder.shown == [dialog]
