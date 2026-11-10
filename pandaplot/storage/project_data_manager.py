import json
import logging
import zipfile
import zlib

from PySide6.QtGui import QImage

from pandaplot.models.migrations.runner import run_cross_item_migrations
from pandaplot.models.migrations.schema_version import CURRENT_SCHEMA_VERSION
from pandaplot.models.project import Project
from pandaplot.models.project.items import Item
from pandaplot.storage.item_data_manager_factory import ItemDataManagerFactory
from pandaplot.utils.errors import UserFacingError

COVER_IMAGE_ENTRY = "cover.png"
"""Reserved zip entry holding the project's cover image (#598)."""


class _ZipBytesProxy:
    """Mimics zipfile.ZipFile.read() using pre-loaded bytes so managers need no changes."""
    def __init__(self, raw_data: dict):
        self._raw_data = raw_data

    def read(self, path: str) -> bytes:
        return self._raw_data[path]

    def namelist(self) -> list:
        return list(self._raw_data.keys())


class ProjectDataManager:
    def __init__(self, item_data_manager_factory: ItemDataManagerFactory):
        self.data_factory = item_data_manager_factory
        self.logger = logging.getLogger(self.__class__.__name__)

    def save(self, project: Project, filepath: str):
        self.logger.info(f"Saving project {project.name} to {filepath}")
        with zipfile.ZipFile(filepath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            project_dict = project.to_dict()

            # Add item references (with paths to their separate files)
            for item in project.get_all_items():
                type_name = item.__class__.__name__.lower()
                item_file = f"items/{item.id}.{self.data_factory.get_extension_for_type(type_name)}"
                project_dict.setdefault("item_files", {})[item.id] = {
                    "type": type_name,
                    "path": item_file
                }
                manager = self.data_factory.get_manager(type_name)
                manager.save(item, zf, item_file)

            if project.cover_image is not None:
                zf.writestr(COVER_IMAGE_ENTRY, project.cover_image)
                project_dict["cover_image"] = COVER_IMAGE_ENTRY

            # Save project.json last
            zf.writestr("project.json", json.dumps(project_dict, indent=2))

    def load(self, filepath: str) -> Project:
        self.logger.info(f"Loading project from {filepath}")

        # Phase 1: Read all raw bytes while the zip is open.
        # The file is held open only during this block; closing it immediately
        # prevents the Windows exclusive-lock window that would otherwise last
        # until all processing (Project.from_dict, item deserialization, …) finishes.
        with zipfile.ZipFile(filepath, "r") as zf:
            names = set(zf.namelist())
            if "project.json" not in names:
                raise UserFacingError("This is not a valid PandaPlot project file: it has no project data.")
            raw_data = {name: zf.read(name) for name in names - {COVER_IMAGE_ENTRY}}
            cover_bytes = self._read_cover_entry(zf, names)
        # ← zip closed here; Windows file lock released before any deserialization

        # Phase 2: Deserialize entirely from in-memory bytes (no file lock held).
        zip_proxy = _ZipBytesProxy(raw_data)
        project_dict = json.loads(raw_data["project.json"].decode("utf-8"))
        project = Project.from_dict(project_dict)
        schema_version = project_dict.get("schema_version", 0)
        if schema_version > CURRENT_SCHEMA_VERSION:
            # A newer schema_version means a newer app version wrote this
            # file in a shape this build doesn't know how to migrate --
            # every migration dispatcher here is a `while schema_version <
            # CURRENT_SCHEMA_VERSION` loop, so it silently no-ops instead
            # of upgrading (there's nothing to upgrade FROM its own point
            # of view). Loading anyway would hand raw, un-migrated dicts
            # straight to each item's from_dict(), which _load_item's own
            # broad except swallows into a logged error -- so the project
            # would open with items silently missing, and a later save
            # would overwrite the original file with that truncated
            # project. Refuse up front instead, before any item is loaded.
            raise UserFacingError(
                "This project was saved by a newer version of PandaPlot and cannot be opened by this one. "
                "Update PandaPlot to open it."
            )

        items = {}
        failed_items: list[str] = []
        for item_id, info in project_dict.get("item_files", {}).items():
            curr_item = self._load_item(item_id, info, zip_proxy, schema_version)
            if curr_item is not None:
                items[item_id] = curr_item
            else:
                failed_items.append(item_id)

        project.cover_image = self._validated_cover_image(project_dict, cover_bytes)

        project_root = project_dict.get("root", {})
        project.root.id = project_root.get("id", project.root.id)
        self._add_items_to_project(project, items, project_root.get("items", []))
        run_cross_item_migrations(project)
        # Not persisted (see Project.to_dict) -- purely to let callers of
        # load() surface a warning about items that were silently dropped
        # instead of the failure disappearing into the log.
        project.failed_item_ids = failed_items
        return project

    def _read_cover_entry(self, zf: zipfile.ZipFile, names: set[str]) -> bytes | None:
        """Read the optional cover entry, returning None when it is absent or cannot be read from the archive.

        The cover is decorative, so a damaged entry (CRC or decompression error) must not stop the project opening.
        """
        if COVER_IMAGE_ENTRY not in names:
            return None
        try:
            return zf.read(COVER_IMAGE_ENTRY)
        except (zipfile.BadZipFile, zlib.error, OSError, EOFError, NotImplementedError, RuntimeError):
            self.logger.warning("Project cover image %r is damaged and cannot be read; ignoring it", COVER_IMAGE_ENTRY, exc_info=True)
            return None

    def _validated_cover_image(self, project_dict: dict, data: bytes | None) -> bytes | None:
        """Return the cover image bytes, or None when absent or not a readable image."""
        entry = project_dict.get("cover_image")
        if entry is None:
            return None
        if entry != COVER_IMAGE_ENTRY or data is None:
            self.logger.warning("Project references a missing cover image entry %r; ignoring it", entry)
            return None
        if QImage.fromData(data).isNull():
            self.logger.warning("Project cover image %r is not a readable image; ignoring it", entry)
            return None
        return data

    def _load_item(self, item_id: str, info, zip_file, schema_version: int) -> Item | None:
        try:
            item_class = self.data_factory.resolve_item_class(info["type"])
            path = info["path"]
            manager = self.data_factory.get_manager(info["type"])

            item = manager.load(item_class, zip_file, path, schema_version)
            self.logger.info(
                f"Loaded item {item_id} of type {info['type']} from {path}")
            return item
        except Exception:
            self.logger.exception("Failed to load item %s", item_id)
            return None

    def _add_items_to_project(self, project: Project, items: dict[str, Item], project_tree: list[dict]) -> None:
        """Recursively add items to the project based on the project tree structure."""
        for node in project_tree:
            item_id = node.get("id")
            if item_id in items:
                project.add_item(
                    items[item_id], parent_id=node.get("parent_id"))

            if node.get("items", None) is not None:
                # Recur for children
                self._add_items_to_project(
                    project, items, node.get("items", []))
