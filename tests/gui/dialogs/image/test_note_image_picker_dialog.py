from unittest.mock import Mock

import pytest
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from pandaplot.gui.dialogs.image.note_image_picker_dialog import NoteImagePickerDialog
from pandaplot.models.project.items import Folder, Image, ImageGallery
from pandaplot.models.state.app_context import AppContext


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    ctx.get_app_state.return_value = Mock()
    return ctx


class _ProjectStub:
    def __init__(self, items):
        self._items = items

    def get_all_items(self):
        return self._items


@pytest.fixture(autouse=True)
def _plain_icons(monkeypatch):
    monkeypatch.setattr(NoteImagePickerDialog, "_tile_icon_for", lambda *_args, **_kwargs: QIcon())


def test_empty_folder_nests_under_folder_that_holds_only_empty_folders(app_context):
    """A folder whose subtree has no images has len() == 0; it must still be a tree parent."""
    outer = Folder(name="Outer")
    inner = Folder(name="Inner")
    outer.add_item(inner)
    gallery = ImageGallery(name="Photos")
    image = Image(name="pic.png")
    gallery.add_item(image)
    project = _ProjectStub([outer, inner, gallery, image])

    dialog = NoteImagePickerDialog(app_context, project)

    top_level = {dialog.tree.topLevelItem(i).text(0): dialog.tree.topLevelItem(i) for i in range(dialog.tree.topLevelItemCount())}
    assert set(top_level) == {"Outer", "Photos"}
    assert [top_level["Outer"].child(i).text(0) for i in range(top_level["Outer"].childCount())] == ["Inner"]
    assert top_level["Photos"].child(0).text(0) == "pic.png"
