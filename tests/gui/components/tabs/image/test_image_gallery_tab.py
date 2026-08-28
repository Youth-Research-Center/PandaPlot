"""Tests for ImageGalleryTab."""
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QBuffer, QIODevice, QMimeData
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication, QLabel

from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.tabs.image.image_gallery_tab import ImageGalleryTab
from pandaplot.models.project.items import Image, ImageGallery
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


def _project_stub(*items):
    """Minimal stand-in for a Project, resolving find_item() from a dict of
    real ImageGallery/Image instances so _rebuild_breadcrumb's parent-walk
    can actually traverse ImageGallery.parent_id chains (unlike the default
    Mock() app_context fixture, where isinstance(parent, ImageGallery) always
    fails and the breadcrumb chain never grows past one element)."""
    by_id = {item.id: item for item in items}
    stub = Mock()
    stub.find_item.side_effect = lambda item_id: by_id.get(item_id)
    return stub


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _real_png_bytes() -> bytes:
    """A small but genuinely decodable PNG, for tests that need
    `_thumbnail_for` to succeed rather than fail."""
    pixmap = QPixmap(4, 4)
    pixmap.fill(QColor("blue"))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    return bytes(buffer.data())


def _bordered_png_bytes(size: int = 120, border: int = 20) -> bytes:
    """A large, genuinely decodable PNG with a distinct-colored border and a
    different-colored center -- large enough that _thumbnail_for's own
    120x120 scaling still leaves both colors present. Used to prove a
    resulting small icon was actually produced by downscaling the whole
    image, rather than by center-cropping a small patch that would land
    entirely inside just one of the two regions."""
    from PySide6.QtGui import QPainter

    pixmap = QPixmap(size, size)
    pixmap.fill(QColor("red"))
    painter = QPainter(pixmap)
    painter.fillRect(border, border, size - 2 * border, size - 2 * border, QColor("green"))
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    return bytes(buffer.data())


_FAKE_TOKENS = {
    "text_muted": "#6B7280",
    "border_subtle": "#ECEEF2",
    "surface_white": "#FFFFFF",
    "accent": "#4A56C6",
    "accent_selected_bg": "#EEF0FB",
}


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    ctx.get_app_state.return_value = Mock()

    theme_manager = Mock()
    theme_manager.get_design_tokens.return_value = dict(_FAKE_TOKENS)

    def _get_manager(manager_type, *args, **kwargs):
        if manager_type is ThemeManager:
            return theme_manager
        return Mock()

    ctx.get_manager.side_effect = _get_manager
    return ctx


class TestImageGalleryTab:
    def test_tab_title_is_gallery_name(self, app_context):
        gallery = ImageGallery(name="Trip Photos")
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        assert tab.get_tab_title() == "Trip Photos"

    def test_grid_has_one_tile_per_child(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(Image(name="Beach"))
        gallery.add_item(Image(name="Mountain"))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        assert tab.grid.count() == 2

    def test_album_child_gets_a_tile_too(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(ImageGallery(name="Day 1"))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        assert tab.grid.count() == 1
        assert tab.grid.item(0).text() == "Day 1"

    def test_selecting_tile_enables_delete_button(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(Image(name="Beach"))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        assert tab.delete_button.isEnabled() is False

        tab.grid.item(0).setSelected(True)
        tab.grid.itemSelectionChanged.emit()

        assert tab.delete_button.isEnabled() is True

    def test_group_into_album_button_enabled_only_for_multi_image_selection(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(Image(name="Beach"))
        gallery.add_item(Image(name="Mountain"))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        assert tab.group_into_album_button.isEnabled() is False

        tab.grid.item(0).setSelected(True)
        tab.grid.item(1).setSelected(True)
        tab.grid.itemSelectionChanged.emit()

        assert tab.group_into_album_button.isEnabled() is True


class TestEventConcernsThisGallery:
    def test_removed_item_no_longer_in_gallery_still_matches_last_populate(self, app_context):
        """Regression: undo of ImportImagesCommand removes the image from the
        gallery *then* emits PROJECT_ITEM_REMOVED with only
        {"project", "image_id"} (no parent_id). By the time the event
        arrives, gallery.get_items() no longer contains it, so matching
        against current children alone would miss it and leave a stale
        tile. The filter must still recognize it via the last-populate
        snapshot.
        """
        gallery = ImageGallery(name="Trip")
        image = Image(name="Beach")
        gallery.add_item(image)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)
        assert tab.grid.count() == 1

        # Simulate the undo: item already removed from the gallery by the
        # time the event fires.
        gallery.remove_item(image)
        event_data = {"project": Mock(), "image_id": image.id}

        assert tab._event_concerns_this_gallery(event_data) is True

    def test_unrelated_removed_item_does_not_match(self, app_context):
        gallery = ImageGallery(name="Trip")
        image = Image(name="Beach")
        gallery.add_item(image)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        event_data = {"project": Mock(), "image_id": "some-other-id-never-in-this-gallery"}

        assert tab._event_concerns_this_gallery(event_data) is False


class TestImageGalleryTabNavigation:
    def test_root_gallery_is_current_gallery_initially(self, app_context):
        gallery = ImageGallery(name="Trip")
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        assert tab.root_gallery is gallery
        assert tab.current_gallery is gallery

    def test_tab_title_stays_root_name_after_navigating(self, app_context):
        gallery = ImageGallery(name="Trip")
        album = ImageGallery(name="Day 1")
        gallery.add_item(album)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        tab._navigate_to(album)

        assert tab.get_tab_title() == "Trip"
        assert tab.current_gallery is album

    def test_navigate_to_repopulates_grid_for_new_current_gallery(self, app_context):
        gallery = ImageGallery(name="Trip")
        album = ImageGallery(name="Day 1")
        album.add_item(Image(name="Sunrise"))
        gallery.add_item(album)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)
        assert tab.grid.count() == 1  # just the album tile

        tab._navigate_to(album)

        assert tab.grid.count() == 1  # now the album's own child
        assert tab.grid.item(0).text() == "Sunrise"

    def test_back_and_forward_navigate_history(self, app_context):
        gallery = ImageGallery(name="Trip")
        album = ImageGallery(name="Day 1")
        gallery.add_item(album)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        tab._navigate_to(album)
        assert tab.current_gallery is album

        tab._go_back()
        assert tab.current_gallery is gallery

        tab._go_forward()
        assert tab.current_gallery is album

    def test_navigating_after_going_back_truncates_forward_history(self, app_context):
        gallery = ImageGallery(name="Trip")
        album_a = ImageGallery(name="Day 1")
        album_b = ImageGallery(name="Day 2")
        gallery.add_item(album_a)
        gallery.add_item(album_b)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        tab._navigate_to(album_a)
        tab._go_back()
        tab._navigate_to(album_b)

        # forward history from album_a's branch should be gone
        tab._go_back()
        assert tab.current_gallery is gallery
        tab._go_forward()
        assert tab.current_gallery is album_b

    def test_double_click_album_navigates_in_place_not_new_tab(self, app_context):
        gallery = ImageGallery(name="Trip")
        album = ImageGallery(name="Day 1")
        gallery.add_item(album)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        tab._on_item_double_clicked(tab.grid.item(0))

        assert tab.current_gallery is album
        app_context.get_app_state.return_value.event_bus.emit.assert_not_called()


class TestBreadcrumbSegments:
    def test_three_level_nesting_produces_three_breadcrumb_segments(self, app_context):
        root = ImageGallery(name="Trip")
        album = ImageGallery(name="Day 1")
        sub_album = ImageGallery(name="Morning")
        root.add_item(album)
        album.add_item(sub_album)
        app_context.get_app_state.return_value.current_project = _project_stub(root, album, sub_album)
        tab = ImageGalleryTab(app_context=app_context, gallery=root, parent=None)

        tab._navigate_to(album)
        tab._navigate_to(sub_album)

        segments = [
            tab.breadcrumb_row_layout.itemAt(i).widget()
            for i in range(tab.breadcrumb_row_layout.count())
            if isinstance(tab.breadcrumb_row_layout.itemAt(i).widget(), (PButton, QLabel))
            and tab.breadcrumb_row_layout.itemAt(i).widget().text().strip() != ">"
        ]
        names = [w.text() for w in segments]
        assert names == ["Trip", "Day 1", "Morning"]

    def test_renaming_ancestor_gallery_refreshes_breadcrumb(self, app_context):
        """Regression: breadcrumb segments render each ancestor's name as
        static QLabel/button text at navigation time (_rebuild_breadcrumb),
        so renaming an ancestor gallery -- not just the currently displayed
        one -- left the breadcrumb showing the old name. This isn't covered
        by _event_concerns_this_gallery (scoped to current_gallery's own
        id/children), so it needs its own ancestor-chain check."""
        root = ImageGallery(name="Trip")
        album = ImageGallery(name="Day 1")
        root.add_item(album)
        app_context.get_app_state.return_value.current_project = _project_stub(root, album)
        tab = ImageGalleryTab(app_context=app_context, gallery=root, parent=None)

        tab._navigate_to(album)

        root.update_name("Trip Renamed")
        tab._on_project_item_changed({"item_id": root.id, "new_name": "Trip Renamed"})

        segments = [
            tab.breadcrumb_row_layout.itemAt(i).widget()
            for i in range(tab.breadcrumb_row_layout.count())
            if isinstance(tab.breadcrumb_row_layout.itemAt(i).widget(), (PButton, QLabel))
            and tab.breadcrumb_row_layout.itemAt(i).widget().text().strip() != ">"
        ]
        names = [w.text() for w in segments]
        assert names == ["Trip Renamed", "Day 1"]

    def test_clicking_non_last_segment_navigates_and_updates_history(self, app_context):
        root = ImageGallery(name="Trip")
        album = ImageGallery(name="Day 1")
        sub_album = ImageGallery(name="Morning")
        root.add_item(album)
        album.add_item(sub_album)
        app_context.get_app_state.return_value.current_project = _project_stub(root, album, sub_album)
        tab = ImageGalleryTab(app_context=app_context, gallery=root, parent=None)

        tab._navigate_to(album)
        tab._navigate_to(sub_album)

        # Find the "Trip" (root) breadcrumb segment button and click it.
        root_button = None
        for i in range(tab.breadcrumb_row_layout.count()):
            widget = tab.breadcrumb_row_layout.itemAt(i).widget()
            if isinstance(widget, PButton) and widget.text() == "Trip":
                root_button = widget
                break
        assert root_button is not None
        root_button.click()

        assert tab.current_gallery is root
        # History should now have the root appended after sub_album, and
        # forward navigation should return to sub_album.
        tab._go_back()
        assert tab.current_gallery is sub_album
        tab._go_forward()
        assert tab.current_gallery is root

    def test_last_segment_is_not_a_clickable_button(self, app_context):
        root = ImageGallery(name="Trip")
        album = ImageGallery(name="Day 1")
        root.add_item(album)
        app_context.get_app_state.return_value.current_project = _project_stub(root, album)
        tab = ImageGalleryTab(app_context=app_context, gallery=root, parent=None)

        tab._navigate_to(album)

        last_widget = None
        for i in range(tab.breadcrumb_row_layout.count()):
            widget = tab.breadcrumb_row_layout.itemAt(i).widget()
            if isinstance(widget, (PButton, QLabel)) and widget.text() == "Day 1":
                last_widget = widget
        assert last_widget is not None
        assert not isinstance(last_widget, PButton)


class TestImageGalleryTabSelectionCheckmarks:
    def test_selecting_a_tile_updates_its_icon(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(Image(name="Beach"))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        unselected_icon = tab.grid.item(0).icon()

        tab.grid.item(0).setSelected(True)
        tab.grid.itemSelectionChanged.emit()

        selected_icon = tab.grid.item(0).icon()
        from PySide6.QtCore import QSize
        assert unselected_icon.pixmap(QSize(120, 120)).toImage() != selected_icon.pixmap(QSize(120, 120)).toImage()


class TestImageGalleryTabContextMenu:
    def test_context_menu_has_rename_and_delete_for_single_selection(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(Image(name="Beach"))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)
        tab.grid.item(0).setSelected(True)
        tab.grid.itemSelectionChanged.emit()

        menu = tab._build_context_menu(tab.grid.item(0))
        action_texts = [a.text() for a in menu.actions()]

        assert "Rename" in action_texts
        assert "Delete" in action_texts

    def test_context_menu_has_open_in_new_tab_for_album(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(ImageGallery(name="Day 1"))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)
        tab.grid.item(0).setSelected(True)
        tab.grid.itemSelectionChanged.emit()

        menu = tab._build_context_menu(tab.grid.item(0))
        action_texts = [a.text() for a in menu.actions()]

        assert "Open in New Tab" in action_texts

    def test_context_menu_has_no_open_in_new_tab_for_image(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(Image(name="Beach"))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)
        tab.grid.item(0).setSelected(True)
        tab.grid.itemSelectionChanged.emit()

        menu = tab._build_context_menu(tab.grid.item(0))
        action_texts = [a.text() for a in menu.actions()]

        assert "Open in New Tab" not in action_texts

    def test_open_in_new_tab_emits_tab_open_requested(self, app_context):
        gallery = ImageGallery(name="Trip")
        album = ImageGallery(name="Day 1")
        gallery.add_item(album)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)
        tab.grid.item(0).setSelected(True)
        tab.grid.itemSelectionChanged.emit()

        tab._open_in_new_tab(album)

        app_context.get_app_state.return_value.event_bus.emit.assert_called_once()
        args = app_context.get_app_state.return_value.event_bus.emit.call_args.args
        assert args[1]["item_id"] == album.id


class TestImageGalleryTabViewToggle:
    def test_defaults_to_grid_view_visible(self, app_context):
        gallery = ImageGallery(name="Trip")
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        assert tab.grid.isVisible() or not tab.isVisible()  # visibility only meaningful once shown; check stacked index instead
        assert tab.view_stack.currentWidget() is tab.grid

    def test_switching_to_list_shows_list_view(self, app_context):
        gallery = ImageGallery(name="Trip")
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        tab.view_toggle.setCurrentValue("list")
        tab._on_view_mode_changed("list")

        assert tab.view_stack.currentWidget() is tab.list_view

    def test_list_view_has_one_row_per_child_with_expected_columns(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(Image(name="Beach", width=1920, height=1080, size_bytes=204800))
        gallery.add_item(ImageGallery(name="Day 1"))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        tab._populate_list_view()

        assert tab.list_view.topLevelItemCount() == 2
        names = {tab.list_view.topLevelItem(i).text(0) for i in range(2)}
        assert names == {"Beach", "Day 1"}

        beach_row = next(
            tab.list_view.topLevelItem(i) for i in range(2)
            if tab.list_view.topLevelItem(i).text(0) == "Beach"
        )
        assert beach_row.text(1) == "Image"
        assert beach_row.text(2) == "1920×1080"

        album_row = next(
            tab.list_view.topLevelItem(i) for i in range(2)
            if tab.list_view.topLevelItem(i).text(0) == "Day 1"
        )
        assert album_row.text(1) == "Album"
        assert album_row.text(2) == ""

    def test_list_view_shows_dash_for_unknown_size(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(Image(name="Linked", size_bytes=None))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        tab._populate_list_view()

        row = tab.list_view.topLevelItem(0)
        assert row.text(3) == "—"


class TestImageGalleryTabMovedEvent:
    def test_subscribes_to_project_item_moved(self, app_context):
        gallery = ImageGallery(name="Trip")
        ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        subscribed_events = [call.args[0] for call in app_context.event_bus.subscribe.call_args_list]
        from pandaplot.models.events.event_types import ProjectEvents
        assert ProjectEvents.PROJECT_ITEM_MOVED in subscribed_events

    def test_moved_event_matching_source_folder_repopulates(self, app_context):
        gallery = ImageGallery(name="Trip")
        image = Image(name="Beach")
        gallery.add_item(image)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)
        assert tab.grid.count() == 1

        # Simulate the move: image already removed from this gallery by the
        # time MoveItemCommand's event fires (mirrors PROJECT_ITEM_REMOVED's
        # existing timing in this codebase).
        gallery.remove_item(image)
        event_data = {
            "project": Mock(), "item_id": image.id, "item_type": "image",
            "source_folder": gallery.id, "target_folder": "some-album-id", "item": image,
        }

        assert tab._event_concerns_this_gallery(event_data) is True
        tab._on_project_item_changed(event_data)
        assert tab.grid.count() == 0


class TestImageGalleryTabListViewSelection:
    """Regression coverage for the toolbar/context-menu acting on stale grid
    selection after the user has switched to (and selected in) list view."""

    def test_switching_view_mode_clears_selection_on_both_widgets(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(Image(name="Beach"))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        tab.grid.item(0).setSelected(True)
        tab.grid.itemSelectionChanged.emit()
        assert tab.delete_button.isEnabled() is True

        tab._on_view_mode_changed("list")
        assert tab.grid.selectedItems() == []
        assert tab.list_view.selectedItems() == []
        assert tab.delete_button.isEnabled() is False

        tab.list_view.topLevelItem(0).setSelected(True)
        tab.list_view.itemSelectionChanged.emit()
        assert tab.delete_button.isEnabled() is True

        tab._on_view_mode_changed("grid")
        assert tab.grid.selectedItems() == []
        assert tab.list_view.selectedItems() == []
        assert tab.delete_button.isEnabled() is False

    def test_selecting_in_list_view_enables_toolbar(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(Image(name="Beach"))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)
        tab._on_view_mode_changed("list")

        assert tab.delete_button.isEnabled() is False

        tab.list_view.topLevelItem(0).setSelected(True)
        tab.list_view.itemSelectionChanged.emit()

        assert tab.delete_button.isEnabled() is True
        assert tab.rename_button.isEnabled() is True

    def test_delete_acts_on_list_selection_not_stale_grid_selection(self, app_context):
        gallery = ImageGallery(name="Trip")
        beach = Image(name="Beach")
        mountain = Image(name="Mountain")
        gallery.add_item(beach)
        gallery.add_item(mountain)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        # Select "Beach" in grid view, then switch to list view and select a
        # DIFFERENT row there. Selection should reset on switch, so only the
        # list-view pick is live.
        beach_grid_item = next(
            tab.grid.item(i) for i in range(tab.grid.count()) if tab.grid.item(i).text() == "Beach"
        )
        beach_grid_item.setSelected(True)
        tab.grid.itemSelectionChanged.emit()

        tab._on_view_mode_changed("list")
        mountain_row = next(
            tab.list_view.topLevelItem(i) for i in range(tab.list_view.topLevelItemCount())
            if tab.list_view.topLevelItem(i).text(0) == "Mountain"
        )
        mountain_row.setSelected(True)
        tab.list_view.itemSelectionChanged.emit()

        selected = tab._selected_children()
        assert [c.name for c in selected] == ["Mountain"]

    def test_context_menu_from_list_view_uses_list_selection(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(ImageGallery(name="Day 1"))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)
        tab._on_view_mode_changed("list")

        row = tab.list_view.topLevelItem(0)
        row.setSelected(True)
        tab.list_view.itemSelectionChanged.emit()

        menu = tab._build_context_menu(row)
        action_texts = [a.text() for a in menu.actions()]

        assert "Open in New Tab" in action_texts


class TestImageGalleryTabThemeRefresh:
    def test_apply_theme_refreshes_grid_tile_icons(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(Image(name="Beach"))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        calls_before = tab.app_context.get_manager.call_count
        tab._apply_theme()

        # _apply_theme should have pulled fresh tokens (via _current_tokens)
        # to rebuild every tile icon, not been a no-op.
        assert tab.app_context.get_manager.call_count > calls_before


class TestImageGalleryTabListViewIconScaling:
    def test_list_view_icon_is_scaled_thumbnail_not_center_crop(self, app_context):
        """Regression: build_gallery_tile_icon() only centers a pixmap, it
        doesn't scale it. The list view's 16x16 icon reused the 120x120 grid
        thumbnail as-is, so centering center-cropped its green interior
        instead of showing a scaled view of the whole bordered image.
        """
        gallery = ImageGallery(name="Trip")
        image = Image(name="Beach")
        image.set_bytes(_bordered_png_bytes(size=120, border=20))
        gallery.add_item(image)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        tab._on_view_mode_changed("list")
        row = tab.list_view.topLevelItem(0)

        from PySide6.QtCore import QSize
        icon_image = row.icon(0).pixmap(QSize(16, 16)).toImage()
        colors = {
            icon_image.pixelColor(x, y).getRgb()
            for x in range(icon_image.width())
            for y in range(icon_image.height())
        }

        assert len(colors) > 1, (
            "list-view row icon is a single uniform color -- looks like a "
            "center-crop of the thumbnail rather than a genuine downscale"
        )


class TestImageGalleryTabMoveCopy:
    def test_move_button_enabled_for_any_non_empty_selection(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(Image(name="Beach"))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        assert tab.move_button.isEnabled() is False
        assert tab.copy_button.isEnabled() is False

        tab.grid.item(0).setSelected(True)
        tab.grid.itemSelectionChanged.emit()

        assert tab.move_button.isEnabled() is True
        assert tab.copy_button.isEnabled() is True

    def test_move_and_copy_disabled_for_album_only_selection(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(ImageGallery(name="Day 1"))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        tab.grid.item(0).setSelected(True)
        tab.grid.itemSelectionChanged.emit()

        assert tab.move_button.isEnabled() is False
        assert tab.copy_button.isEnabled() is False

    def test_move_and_copy_enabled_for_mixed_image_and_album_selection(self, app_context, monkeypatch):
        gallery = ImageGallery(name="Trip")
        image = Image(name="Beach")
        album = ImageGallery(name="Day 1")
        gallery.add_item(image)
        gallery.add_item(album)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        for i in range(tab.grid.count()):
            tab.grid.item(i).setSelected(True)
        tab.grid.itemSelectionChanged.emit()

        assert tab.move_button.isEnabled() is True
        assert tab.copy_button.isEnabled() is True

        target_gallery_id = "some-other-gallery-id"

        class _FakeDialog:
            def __init__(self, *a, **kw):
                pass
            def exec(self):
                from PySide6.QtWidgets import QDialog
                return QDialog.DialogCode.Accepted
            def get_selected_gallery_id(self):
                return target_gallery_id

        monkeypatch.setattr(
            "pandaplot.gui.dialogs.image.gallery_destination_picker_dialog.GalleryDestinationPickerDialog",
            _FakeDialog,
        )

        tab._on_move_clicked()

        executor = tab.app_context.get_command_executor.return_value
        assert executor.execute_command.call_count == 1
        move_command = executor.execute_command.call_args.args[0]
        assert move_command.item_id == image.id

    def test_move_executes_move_item_command_per_selected_image(self, app_context, monkeypatch):
        gallery = ImageGallery(name="Trip")
        image = Image(name="Beach")
        gallery.add_item(image)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)
        tab.grid.item(0).setSelected(True)
        tab.grid.itemSelectionChanged.emit()

        target_gallery_id = "some-other-gallery-id"

        class _FakeDialog:
            def __init__(self, *a, **kw):
                pass
            def exec(self):
                from PySide6.QtWidgets import QDialog
                return QDialog.DialogCode.Accepted
            def get_selected_gallery_id(self):
                return target_gallery_id

        monkeypatch.setattr(
            "pandaplot.gui.dialogs.image.gallery_destination_picker_dialog.GalleryDestinationPickerDialog",
            _FakeDialog,
        )

        tab._on_move_clicked()

        executor = tab.app_context.get_command_executor.return_value
        assert executor.execute_command.called
        move_command = executor.execute_command.call_args.args[0]
        assert move_command.item_id == image.id
        assert move_command.target_folder_id == target_gallery_id
        assert move_command.source_folder_id == gallery.id

    def test_copy_executes_copy_images_command_once_for_whole_selection(self, app_context, monkeypatch):
        gallery = ImageGallery(name="Trip")
        image1 = Image(name="Beach")
        image2 = Image(name="Mountain")
        gallery.add_item(image1)
        gallery.add_item(image2)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)
        tab.grid.item(0).setSelected(True)
        tab.grid.item(1).setSelected(True)
        tab.grid.itemSelectionChanged.emit()

        target_gallery_id = "some-other-gallery-id"

        class _FakeDialog:
            def __init__(self, *a, **kw):
                pass
            def exec(self):
                from PySide6.QtWidgets import QDialog
                return QDialog.DialogCode.Accepted
            def get_selected_gallery_id(self):
                return target_gallery_id

        monkeypatch.setattr(
            "pandaplot.gui.dialogs.image.gallery_destination_picker_dialog.GalleryDestinationPickerDialog",
            _FakeDialog,
        )

        tab._on_copy_clicked()

        executor = tab.app_context.get_command_executor.return_value
        assert executor.execute_command.called
        copy_command = executor.execute_command.call_args.args[0]
        assert set(copy_command.image_ids) == {image1.id, image2.id}
        assert copy_command.target_gallery_id == target_gallery_id

    def test_move_does_nothing_when_dialog_cancelled(self, app_context, monkeypatch):
        gallery = ImageGallery(name="Trip")
        image = Image(name="Beach")
        gallery.add_item(image)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)
        tab.grid.item(0).setSelected(True)
        tab.grid.itemSelectionChanged.emit()

        class _FakeDialog:
            def __init__(self, *a, **kw):
                pass
            def exec(self):
                from PySide6.QtWidgets import QDialog
                return QDialog.DialogCode.Rejected
            def get_selected_gallery_id(self):
                return None

        monkeypatch.setattr(
            "pandaplot.gui.dialogs.image.gallery_destination_picker_dialog.GalleryDestinationPickerDialog",
            _FakeDialog,
        )

        tab._on_move_clicked()

        executor = tab.app_context.get_command_executor.return_value
        assert not executor.execute_command.called


class TestImageGalleryTabBrokenThumbnails:
    def test_failed_thumbnail_load_produces_broken_icon_distinct_from_success(self, app_context):
        gallery = ImageGallery(name="Trip")
        good_image = Image(name="Beach")
        good_image.set_bytes(_real_png_bytes())
        bad_image = Image(name="Corrupt")
        bad_image.set_bytes(b"not a real image")
        gallery.add_item(good_image)
        gallery.add_item(bad_image)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        good_item = next(
            tab.grid.item(i) for i in range(tab.grid.count()) if tab.grid.item(i).text() == "Beach"
        )
        bad_item = next(
            tab.grid.item(i) for i in range(tab.grid.count()) if tab.grid.item(i).text() == "Corrupt"
        )

        from PySide6.QtCore import QSize
        good_pixmap = good_item.icon().pixmap(QSize(120, 120)).toImage()
        bad_pixmap = bad_item.icon().pixmap(QSize(120, 120)).toImage()

        assert good_pixmap != bad_pixmap
        assert tab._thumbnail_for(bad_image) is None
        assert tab._thumbnail_for(good_image) is not None


class TestImageGalleryTabDragDropOntoAlbum:
    def test_dropping_image_mime_data_on_album_tile_moves_image(self, app_context):
        gallery = ImageGallery(name="Trip")
        image = Image(name="Beach")
        album = ImageGallery(name="Day 1")
        gallery.add_item(image)
        gallery.add_item(album)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        album_index = next(i for i in range(tab.grid.count()) if tab.grid.item(i).text() == "Day 1")
        album_item = tab.grid.item(album_index)

        mime = QMimeData()
        mime.setData("application/x-pandaplot-image-ids", image.id.encode("utf-8"))

        tab.grid._handle_drop_on_item(album_item, mime)

        executor = tab.app_context.get_command_executor.return_value
        assert executor.execute_command.called
        move_command = executor.execute_command.call_args.args[0]
        assert move_command.item_id == image.id
        assert move_command.target_folder_id == album.id
        assert move_command.source_folder_id == gallery.id

    def test_dropping_on_image_tile_is_a_no_op(self, app_context):
        gallery = ImageGallery(name="Trip")
        image_a = Image(name="Beach")
        image_b = Image(name="Mountain")
        gallery.add_item(image_a)
        gallery.add_item(image_b)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        target_index = next(i for i in range(tab.grid.count()) if tab.grid.item(i).text() == "Mountain")
        target_item = tab.grid.item(target_index)

        mime = QMimeData()
        mime.setData("application/x-pandaplot-image-ids", image_a.id.encode("utf-8"))

        tab.grid._handle_drop_on_item(target_item, mime)

        executor = tab.app_context.get_command_executor.return_value
        assert not executor.execute_command.called

    def test_dropping_multiple_selected_images_moves_all(self, app_context):
        gallery = ImageGallery(name="Trip")
        image_a = Image(name="Beach")
        image_b = Image(name="Mountain")
        album = ImageGallery(name="Day 1")
        gallery.add_item(image_a)
        gallery.add_item(image_b)
        gallery.add_item(album)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        album_index = next(i for i in range(tab.grid.count()) if tab.grid.item(i).text() == "Day 1")
        album_item = tab.grid.item(album_index)

        mime = QMimeData()
        mime.setData("application/x-pandaplot-image-ids", f"{image_a.id}\n{image_b.id}".encode("utf-8"))

        tab.grid._handle_drop_on_item(album_item, mime)

        executor = tab.app_context.get_command_executor.return_value
        assert executor.execute_command.call_count == 2

    def test_dropping_an_album_id_onto_another_album_does_not_destroy_its_contents(self, app_context):
        """Regression: a drag payload can contain an album id (e.g. an album
        tile was part of the selection when the drag started). Moving an
        ImageGallery through MoveItemCommand would recursively strip its
        descendants from the project index first, permanently destroying
        them (undo only re-parents the now-empty album). _move_images_to
        must skip any dragged id that isn't an Image."""
        gallery = ImageGallery(name="Trip")
        source_album = ImageGallery(name="Day 1")
        image_in_album = Image(name="Beach")
        source_album.add_item(image_in_album)
        target_album = ImageGallery(name="Day 2")
        gallery.add_item(source_album)
        gallery.add_item(target_album)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        target_index = next(i for i in range(tab.grid.count()) if tab.grid.item(i).text() == "Day 2")
        target_item = tab.grid.item(target_index)

        mime = QMimeData()
        mime.setData("application/x-pandaplot-image-ids", source_album.id.encode("utf-8"))

        tab.grid._handle_drop_on_item(target_item, mime)

        executor = tab.app_context.get_command_executor.return_value
        assert not executor.execute_command.called
        assert image_in_album in source_album.get_items()

    def test_dropping_an_album_id_onto_itself_is_a_no_op(self, app_context):
        gallery = ImageGallery(name="Trip")
        album = ImageGallery(name="Day 1")
        image_in_album = Image(name="Beach")
        album.add_item(image_in_album)
        gallery.add_item(album)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        album_index = next(i for i in range(tab.grid.count()) if tab.grid.item(i).text() == "Day 1")
        album_item = tab.grid.item(album_index)

        mime = QMimeData()
        mime.setData("application/x-pandaplot-image-ids", album.id.encode("utf-8"))

        tab.grid._handle_drop_on_item(album_item, mime)

        executor = tab.app_context.get_command_executor.return_value
        assert not executor.execute_command.called
        assert image_in_album in album.get_items()


class TestImageGalleryTabDragDropOntoBreadcrumb:
    def test_dropping_on_ancestor_breadcrumb_segment_moves_image_up(self, app_context):
        gallery = ImageGallery(name="Trip")
        album = ImageGallery(name="Day 1")
        image = Image(name="Beach")
        gallery.add_item(album)
        album.add_item(image)
        app_context.get_app_state.return_value.current_project = _project_stub(gallery, album)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        tab._navigate_to(album)
        assert tab.current_gallery is album

        # The root "Trip" segment is the only clickable ancestor at this depth.
        ancestor_segment = next(
            tab.breadcrumb_row_layout.itemAt(i).widget()
            for i in range(tab.breadcrumb_row_layout.count())
            if hasattr(tab.breadcrumb_row_layout.itemAt(i).widget(), "text")
            and tab.breadcrumb_row_layout.itemAt(i).widget().text() == "Trip"
        )

        mime = QMimeData()
        mime.setData("application/x-pandaplot-image-ids", image.id.encode("utf-8"))

        ancestor_segment._handle_breadcrumb_drop(mime)

        executor = tab.app_context.get_command_executor.return_value
        assert executor.execute_command.called
        move_command = executor.execute_command.call_args.args[0]
        assert move_command.item_id == image.id
        assert move_command.target_folder_id == gallery.id
        assert move_command.source_folder_id == album.id


class TestImageGalleryTabSort:
    def test_default_sort_is_name_ascending(self, app_context):
        gallery = ImageGallery(name="Trip")
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        assert tab._sort_field == "name"
        assert tab._sort_ascending is True

    def test_grid_sorted_by_name_ascending_by_default(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(Image(name="Zebra"))
        gallery.add_item(Image(name="Apple"))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        names = [tab.grid.item(i).text() for i in range(tab.grid.count())]
        assert names == ["Apple", "Zebra"]

    def test_sort_by_name_descending(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(Image(name="Apple"))
        gallery.add_item(Image(name="Zebra"))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        tab._sort_ascending = False
        tab._populate_grid()

        names = [tab.grid.item(i).text() for i in range(tab.grid.count())]
        assert names == ["Zebra", "Apple"]

    def test_sort_by_size(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(Image(name="Big", storage_mode="external", size_bytes=1000))
        gallery.add_item(Image(name="Small", storage_mode="external", size_bytes=10))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        tab._sort_field = "size"
        tab._populate_grid()

        names = [tab.grid.item(i).text() for i in range(tab.grid.count())]
        assert names == ["Small", "Big"]

    def test_sort_by_modified(self, app_context):
        gallery = ImageGallery(name="Trip")
        older = Image(name="Older")
        newer = Image(name="Newer")
        older.modified_at = "2026-01-01T00:00:00"
        newer.modified_at = "2026-02-01T00:00:00"
        gallery.add_item(newer)
        gallery.add_item(older)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        tab._sort_field = "modified"
        tab._populate_grid()

        names = [tab.grid.item(i).text() for i in range(tab.grid.count())]
        assert names == ["Older", "Newer"]

    def test_grid_and_list_view_share_the_same_order(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(Image(name="Zebra"))
        gallery.add_item(Image(name="Apple"))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        tab._populate_list_view()
        grid_names = [tab.grid.item(i).text() for i in range(tab.grid.count())]
        list_names = [tab.list_view.topLevelItem(i).text(0) for i in range(tab.list_view.topLevelItemCount())]
        assert grid_names == list_names == ["Apple", "Zebra"]

    def test_sort_field_dropdown_change_repopulates_both_views(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(Image(name="Big", storage_mode="external", size_bytes=1000))
        gallery.add_item(Image(name="Small", storage_mode="external", size_bytes=10))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        tab._on_sort_field_changed("size")

        assert tab._sort_field == "size"
        names = [tab.grid.item(i).text() for i in range(tab.grid.count())]
        assert names == ["Small", "Big"]

    def test_list_view_sorted_by_size_is_numeric_not_lexical(self, app_context):
        # Regression test: "9 B" and "10 B" are formatted text whose lexical
        # order ("10 B" < "9 B") disagrees with numeric order (9 < 10). If
        # QTreeWidget's native setSortingEnabled(True) resort were still in
        # effect, this would come back lexically sorted ("10 B" before "9 B")
        # instead of numerically ("9 B" before "10 B").
        gallery = ImageGallery(name="Trip")
        gallery.add_item(Image(name="Ten", storage_mode="external", size_bytes=10))
        gallery.add_item(Image(name="Nine", storage_mode="external", size_bytes=9))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        tab._on_view_mode_changed("list")
        tab._sort_field = "size"
        tab._populate_list_view()

        names = [tab.list_view.topLevelItem(i).text(0) for i in range(tab.list_view.topLevelItemCount())]
        sizes = [tab.list_view.topLevelItem(i).text(3) for i in range(tab.list_view.topLevelItemCount())]
        assert names == ["Nine", "Ten"]
        assert sizes == ["9 B", "10 B"]

    def test_list_view_sorted_by_type_matches_sorted_children_order(self, app_context):
        # Regression test: _sorted_children()'s "type" key sorts images
        # before albums, but QTreeWidget's native text-based sort would put
        # the literal string "Album" before "Image" -- exactly reversed. If
        # the native resort were still in effect, this would come back
        # album-first instead of image-first.
        gallery = ImageGallery(name="Trip")
        gallery.add_item(ImageGallery(name="Album"))
        gallery.add_item(Image(name="Photo"))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        tab._on_view_mode_changed("list")
        tab._sort_field = "type"
        tab._populate_list_view()

        names = [tab.list_view.topLevelItem(i).text(0) for i in range(tab.list_view.topLevelItemCount())]
        types = [tab.list_view.topLevelItem(i).text(1) for i in range(tab.list_view.topLevelItemCount())]
        assert names == ["Photo", "Album"]
        assert types == ["Image", "Album"]


class TestImageGalleryTabLongNameTruncation:
    def test_short_name_displayed_verbatim_in_grid(self, app_context):
        gallery = ImageGallery(name="Trip")
        gallery.add_item(Image(name="Beach"))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        assert tab.grid.item(0).text() == "Beach"

    def test_long_name_elided_in_grid_with_full_name_as_tooltip(self, app_context):
        long_name = "vacation_photo_from_the_summer_trip_final_edited_version_2026"
        gallery = ImageGallery(name="Trip")
        gallery.add_item(Image(name=long_name))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        displayed = tab.grid.item(0).text()
        assert displayed != long_name
        assert displayed.endswith("…") or displayed.endswith("...")
        assert tab.grid.item(0).toolTip() == long_name

    def test_long_name_elided_in_list_view_with_full_name_as_tooltip(self, app_context):
        long_name = "vacation_photo_from_the_summer_trip_final_edited_version_2026"
        gallery = ImageGallery(name="Trip")
        gallery.add_item(Image(name=long_name))
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)

        tab._populate_list_view()
        row = tab.list_view.topLevelItem(0)

        displayed = row.text(0)
        assert displayed != long_name
        assert row.toolTip(0) == long_name


def test_get_tab_data_returns_imagegallery_type_and_id():
    tab = ImageGalleryTab.__new__(ImageGalleryTab)
    tab.root_gallery = Mock(id="gal-1")

    assert tab.get_tab_data() == {"type": "imagegallery", "id": "gal-1"}


class TestImageGalleryTabTitleRefresh:
    def test_rename_of_root_gallery_refreshes_tab_title(self, app_context):
        """Regression: unlike ChartTab/NoteTab/DatasetTab, ImageGalleryTab
        never called refresh_tab_title() at all, so renaming the gallery
        shown in an open tab left its tab title stale even though the grid
        itself did repopulate on the same event."""
        gallery = ImageGallery(name="Trip")
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)
        tab.refresh_tab_title = Mock()

        gallery.update_name("Trip Renamed")
        tab._on_project_item_changed({"item_id": gallery.id, "new_name": "Trip Renamed"})

        tab.refresh_tab_title.assert_called_once()

    def test_rename_of_child_image_does_not_refresh_tab_title(self, app_context):
        """The tab title only reflects root_gallery.name, so a rename of a
        child image/sub-gallery (which does still repopulate the grid) has
        nothing to refresh the title for."""
        gallery = ImageGallery(name="Trip")
        image = Image(name="Beach")
        gallery.add_item(image)
        tab = ImageGalleryTab(app_context=app_context, gallery=gallery, parent=None)
        tab.refresh_tab_title = Mock()

        image.update_name("Beach Renamed")
        tab._on_project_item_changed({"item_id": image.id, "new_name": "Beach Renamed"})

        tab.refresh_tab_title.assert_not_called()
