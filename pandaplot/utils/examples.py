"""Discovery of bundled example projects (.pplot files under the examples/ directory)."""

import json
import logging
import os
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pandaplot.models.project.example_info import (
    ExampleInfo,
    ExampleLevel,
    ExampleSection,
    ExampleTag,
    example_tag,
    summary_from_description,
)

logger = logging.getLogger(__name__)

_COVER_IMAGE_ENTRY = "cover.png"
_SECTION_ORDER = {section: index for index, section in enumerate(ExampleSection)}


@dataclass(frozen=True)
class ExampleProject:
    """What the examples browser knows about one bundled example, read from its .pplot file."""

    path: str
    name: str
    summary: str
    description: str
    section: ExampleSection
    level: ExampleLevel
    tags: tuple[ExampleTag, ...]
    featured_chart_ids: tuple[str, ...]
    start_note_id: str | None
    data_credit: str
    cover_image: bytes | None
    dataset_count: int
    chart_count: int
    note_count: int


def get_examples_dir() -> Path:
    """Return the repo-root examples/ directory (sibling of the pandaplot package)."""
    return Path(__file__).resolve().parent.parent.parent / "examples"


def is_in_examples_dir(path: str | os.PathLike[str] | None) -> bool:
    """Return whether ``path`` lies inside the bundled examples directory.

    Args:
        path: A file path, possibly relative or containing symlinks.

    Returns:
        True when the resolved path is within ``get_examples_dir()``; False for an
        empty or unresolvable path.
    """
    if not path:
        return False
    try:
        return Path(path).resolve().is_relative_to(get_examples_dir().resolve())
    except (OSError, ValueError, RuntimeError):
        logger.debug("Could not resolve %r to test it against the examples directory", path, exc_info=True)
        return False


def _item_ids_by_type(project_meta: dict[str, Any]) -> dict[str, set[str]]:
    """Group the ids in project.json's ``item_files`` map by item type name."""
    ids: dict[str, set[str]] = {}
    item_files = project_meta.get("item_files")
    if not isinstance(item_files, dict):
        return ids
    for item_id, info in item_files.items():
        if isinstance(info, dict) and isinstance(info.get("type"), str):
            ids.setdefault(info["type"], set()).add(item_id)
    return ids


def _read_example(pplot_path: Path) -> ExampleProject:
    """Build an ExampleProject from project.json and cover.png of one archive.

    Raises:
        Exception: If the archive or its project.json cannot be read.
    """
    with zipfile.ZipFile(pplot_path) as archive:
        project_meta = json.loads(archive.read("project.json"))
        if not isinstance(project_meta, dict):
            raise TypeError("project.json is not an object")
        cover_image = None
        if project_meta.get("cover_image") == _COVER_IMAGE_ENTRY and _COVER_IMAGE_ENTRY in archive.namelist():
            try:
                cover_image = archive.read(_COVER_IMAGE_ENTRY)
            except (zipfile.BadZipFile, zlib.error, OSError, EOFError, NotImplementedError, RuntimeError):
                logger.warning("Ignoring damaged cover image in example project '%s'", pplot_path, exc_info=True)

    info = ExampleInfo.from_dict(project_meta.get("example"))
    ids = _item_ids_by_type(project_meta)
    charts = ids.get("chart", set())
    notes = ids.get("note", set())
    raw_description = project_meta.get("description")
    description = raw_description if isinstance(raw_description, str) else ""
    raw_name = project_meta.get("name")

    return ExampleProject(
        path=str(pplot_path),
        name=raw_name if isinstance(raw_name, str) and raw_name else pplot_path.stem,
        summary=info.summary or summary_from_description(description),
        description=description,
        section=info.section,
        level=info.level,
        tags=tuple(tag for tag in map(example_tag, info.tag_ids) if tag is not None),
        featured_chart_ids=tuple(chart_id for chart_id in info.featured_chart_ids if chart_id in charts),
        start_note_id=info.start_note_id if info.start_note_id in notes else None,
        data_credit=info.data_credit,
        cover_image=cover_image,
        dataset_count=len(ids.get("dataset", set())),
        chart_count=len(charts),
        note_count=len(notes),
    )


def discover_example_projects(examples_dir: Path | None = None) -> list[ExampleProject]:
    """Scan examples_dir for .pplot project files and read their example metadata.

    Only project.json and cover.png are read from each archive. Every .pplot file is listed, whether or not
    its example settings are enabled; files without settings get the defaults. Unreadable files are skipped
    with a warning. Results are ordered by section, then by name (case-insensitive).
    """
    if examples_dir is None:
        examples_dir = get_examples_dir()

    if not examples_dir.is_dir():
        return []

    examples: list[ExampleProject] = []
    for pplot_path in sorted(examples_dir.rglob("*.pplot")):
        try:
            examples.append(_read_example(pplot_path))
        except Exception as e:  # noqa: BLE001
            logger.warning("Skipping unreadable example project '%s': %s", pplot_path, e)

    examples.sort(key=lambda example: (_SECTION_ORDER[example.section], example.name.casefold()))
    return examples
