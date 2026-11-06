"""Item loaders must keep string timestamps when saved metadata holds explicit nulls.

Projects written by the old loader serialized ``created_at``/``modified_at`` as
``null``; ``dict.get(key, default)`` only falls back when the key is absent.
"""
import io
import json
from zipfile import ZipFile

import pytest

from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.items.folder import Folder
from pandaplot.models.project.items.image import ImageGallery
from pandaplot.models.project.items.note import Note
from pandaplot.storage.dataset_data_manager import DatasetDataManager
from pandaplot.storage.folder_data_manager import FolderDataManager
from pandaplot.storage.image_gallery_data_manager import ImageGalleryDataManager
from pandaplot.storage.note_data_manager import NoteDataManager

_LOADERS = [
    pytest.param(FolderDataManager, Folder, {}, id="folder"),
    pytest.param(NoteDataManager, Note, {"items/x.md": "body"}, id="note"),
    pytest.param(ImageGalleryDataManager, ImageGallery, {}, id="gallery"),
    pytest.param(DatasetDataManager, Dataset, {}, id="dataset"),
]


@pytest.mark.parametrize(("manager_cls", "item_cls", "extra_files"), _LOADERS)
@pytest.mark.parametrize("metadata", [
    {"created_at": None, "modified_at": None},
    {},
], ids=["explicit-null", "missing"])
def test_loader_keeps_string_timestamps(manager_cls, item_cls, extra_files, metadata):
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as zf:
        zf.writestr("items/x.json", json.dumps({"id": "x", "name": "X", **metadata}))
        for path, content in extra_files.items():
            zf.writestr(path, content)

    buffer.seek(0)
    with ZipFile(buffer, "r") as zf:
        loaded = manager_cls().load(item_cls, zf, "items/x", schema_version=1)

    assert isinstance(loaded.created_at, str)
    assert loaded.modified_at == loaded.created_at


def test_loader_preserves_saved_timestamps():
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as zf:
        zf.writestr(
            "items/x.json",
            json.dumps({"id": "x", "name": "X", "created_at": "2020-01-01T00:00:00", "modified_at": "2021-02-02T00:00:00"}),
        )

    buffer.seek(0)
    with ZipFile(buffer, "r") as zf:
        loaded = FolderDataManager().load(Folder, zf, "items/x", schema_version=1)

    assert loaded.created_at == "2020-01-01T00:00:00"
    assert loaded.modified_at == "2021-02-02T00:00:00"


@pytest.mark.parametrize("data", [
    {"id": "d", "name": "D", "created_at": None, "modified_at": None},
    {"id": "d", "name": "D"},
], ids=["explicit-null", "missing"])
def test_dataset_from_dict_keeps_string_timestamps(data):
    loaded = Dataset.from_dict(data)

    assert isinstance(loaded.created_at, str)
    assert loaded.modified_at == loaded.created_at
