from pandaplot.models.project.items import Image, ImageGallery, ItemCollection


class TestImage:
    def test_defaults(self):
        image = Image(name="Photo")

        assert image.name == "Photo"
        assert image.source_file == ""
        assert image.storage_mode == "copied"
        assert image.image_ext == ""
        assert image.width == 0
        assert image.height == 0
        assert image.get_bytes() is None

    def test_construction_with_all_fields(self):
        image = Image(
            id="img-1",
            name="Sunset",
            source_file="/tmp/sunset.jpg",
            storage_mode="external",
            image_ext="jpg",
            width=1920,
            height=1080,
        )

        assert image.id == "img-1"
        assert image.source_file == "/tmp/sunset.jpg"
        assert image.storage_mode == "external"
        assert image.image_ext == "jpg"
        assert image.width == 1920
        assert image.height == 1080

    def test_set_and_get_bytes(self):
        image = Image(name="Cat")
        image.set_bytes(b"raw-bytes")

        assert image.get_bytes() == b"raw-bytes"

    def test_size_bytes_defaults_to_none(self):
        image = Image(name="Photo")

        assert image.size_bytes is None

    def test_size_bytes_round_trips_through_to_dict_from_dict(self):
        image = Image(id="img-5", name="Photo", size_bytes=204800)

        restored = Image.from_dict(image.to_dict())

        assert restored.size_bytes == 204800

    def test_to_dict_from_dict_round_trip(self):
        image = Image(
            id="img-2",
            name="Moon",
            source_file="https://example.com/moon.png",
            storage_mode="external",
            image_ext="png",
            width=800,
            height=600,
        )

        restored = Image.from_dict(image.to_dict())

        assert restored.id == image.id
        assert restored.name == image.name
        assert restored.source_file == image.source_file
        assert restored.storage_mode == image.storage_mode
        assert restored.image_ext == image.image_ext
        assert restored.width == image.width
        assert restored.height == image.height
        assert restored.parent_id == image.parent_id
        assert restored.created_at == image.created_at

    def test_note_id_defaults_to_none(self):
        image = Image(name="Photo")

        assert image.note_id is None

    def test_note_id_round_trips_through_to_dict_from_dict(self):
        image = Image(id="img-6", name="Chart Snapshot", note_id="note-42")

        restored = Image.from_dict(image.to_dict())

        assert restored.note_id == "note-42"


class TestImageGallery:
    def test_is_item_collection(self):
        gallery = ImageGallery(name="Vacation")

        assert isinstance(gallery, ItemCollection)
        assert gallery.name == "Vacation"
        assert gallery.get_items() == []

    def test_default_name(self):
        gallery = ImageGallery()

        assert gallery.name == "New Image Gallery"

    def test_can_nest_gallery_as_album(self):
        gallery = ImageGallery(name="Trip")
        album = ImageGallery(name="Day 1")
        image = Image(name="Beach")

        gallery.add_item(album)
        album.add_item(image)

        assert album.parent_id == gallery.id
        assert image.parent_id == album.id
        assert gallery.get_item_by_id(album.id) is album
        assert album.get_item_by_id(image.id) is image

    def test_to_dict_from_dict_round_trip_with_children(self):
        gallery = ImageGallery(id="gal-1", name="Trip")
        image = Image(id="img-3", name="Beach", source_file="/tmp/beach.png",
                       storage_mode="copied", image_ext="png", width=100, height=50)
        gallery.add_item(image)

        data = gallery.to_dict()

        assert data["id"] == "gal-1"
        assert data["name"] == "Trip"
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == "img-3"
