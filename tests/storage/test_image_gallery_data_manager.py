import io
from zipfile import ZipFile

from pandaplot.models.project.items.image import ImageGallery
from pandaplot.storage.image_gallery_data_manager import ImageGalleryDataManager


class TestImageGalleryDataManager:
    def test_round_trip_metadata_only(self):
        gallery = ImageGallery(id="gal-1", name="Vacation")

        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as zf:
            ImageGalleryDataManager().save(gallery, zf, "items/gal-1")
            assert zf.namelist() == ["items/gal-1.json"]

        buffer.seek(0)
        with ZipFile(buffer, "r") as zf:
            loaded = ImageGalleryDataManager().load(ImageGallery, zf, "items/gal-1", schema_version=1)

        assert loaded.id == "gal-1"
        assert loaded.name == "Vacation"
        assert loaded.get_items() == []


def test_load_without_timestamps_keeps_string_defaults():
    """Legacy/hand-edited metadata may omit timestamps; they must stay str, not None."""
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as zf:
        zf.writestr("items/gal-1.json", '{"id": "gal-1", "name": "G"}')

    buffer.seek(0)
    with ZipFile(buffer, "r") as zf:
        loaded = ImageGalleryDataManager().load(ImageGallery, zf, "items/gal-1", schema_version=1)

    assert isinstance(loaded.created_at, str)
    assert loaded.modified_at == loaded.created_at
