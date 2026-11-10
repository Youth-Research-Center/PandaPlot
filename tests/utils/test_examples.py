import json
import zipfile
from pathlib import Path

import pytest

from pandaplot.models.project.example_info import ExampleInfo, ExampleLevel, ExampleSection, example_tag
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.items.note import Note
from pandaplot.models.project.project import Project
from pandaplot.storage.chart_data_manager import ChartDataManager
from pandaplot.storage.dataset_data_manager import DatasetDataManager
from pandaplot.storage.item_data_manager_factory import ItemDataManagerFactory
from pandaplot.storage.note_data_manager import NoteDataManager
from pandaplot.storage.project_data_manager import ProjectDataManager
from pandaplot.utils.examples import ExampleProject, discover_example_projects, get_examples_dir


def _write_pplot(path: Path, name: str, description: str):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("project.json", json.dumps({"name": name, "description": description}))


def _save(path: Path, project: Project) -> None:
    factory = ItemDataManagerFactory()
    factory.register("note", Note, NoteDataManager(), "note")
    factory.register("chart", Chart, ChartDataManager(), "chart")
    factory.register("dataset", Dataset, DatasetDataManager(), "dataset")
    ProjectDataManager(factory).save(project, str(path))


def _project(name: str, description: str = "", info: ExampleInfo | None = None, *, charts: int = 0, datasets: int = 0, notes: int = 0) -> Project:
    project = Project(name=name, description=description)
    for i in range(datasets):
        project.add_item(Dataset(id=f"d{i}", name=f"D{i}"))
    for i in range(charts):
        project.add_item(Chart(id=f"c{i}", name=f"C{i}", chart_type="line"))
    for i in range(notes):
        project.add_item(Note(id=f"n{i}", name=f"N{i}", content="x"))
    if info is not None:
        project.example_info = info
    return project


class TestDiscoverExampleProjects:
    def test_missing_directory_returns_empty_list(self, tmp_path):
        assert discover_example_projects(tmp_path / "does-not-exist") == []

    def test_empty_directory_returns_empty_list(self, tmp_path):
        assert discover_example_projects(tmp_path) == []

    def test_reads_name_and_description_from_each_pplot(self, tmp_path):
        _write_pplot(tmp_path / "a.pplot", "Project A", "Description A")
        _write_pplot(tmp_path / "b.pplot", "Project B", "Description B")

        examples = discover_example_projects(tmp_path)

        assert [e.name for e in examples] == ["Project A", "Project B"]
        assert examples[0].description == "Description A"
        assert examples[0].path == str(tmp_path / "a.pplot")
        assert isinstance(examples[0], ExampleProject)

    def test_finds_pplot_files_in_subdirectories(self, tmp_path):
        subdir = tmp_path / "nested"
        subdir.mkdir()
        _write_pplot(subdir / "nested.pplot", "Nested Project", "Nested description")

        examples = discover_example_projects(tmp_path)

        assert [e.name for e in examples] == ["Nested Project"]

    def test_skips_corrupt_pplot_file(self, tmp_path, caplog):
        (tmp_path / "corrupt.pplot").write_text("not a zip file")
        _write_pplot(tmp_path / "valid.pplot", "Valid Project", "Valid description")

        with caplog.at_level("WARNING"):
            examples = discover_example_projects(tmp_path)

        assert [e.name for e in examples] == ["Valid Project"]
        assert "corrupt.pplot" in caplog.text

    def test_skips_pplot_without_project_json(self, tmp_path):
        with zipfile.ZipFile(tmp_path / "no_meta.pplot", "w") as archive:
            archive.writestr("items/something.json", "{}")

        assert discover_example_projects(tmp_path) == []

    def test_skips_project_json_that_is_not_an_object(self, tmp_path):
        with zipfile.ZipFile(tmp_path / "list.pplot", "w") as archive:
            archive.writestr("project.json", "[]")

        assert discover_example_projects(tmp_path) == []

    def test_missing_name_falls_back_to_filename_stem(self, tmp_path):
        with zipfile.ZipFile(tmp_path / "fallback.pplot", "w") as archive:
            archive.writestr("project.json", json.dumps({"description": "No name field"}))

        examples = discover_example_projects(tmp_path)

        assert examples[0].name == "fallback"
        assert examples[0].description == "No name field"

    def test_full_metadata_counts_and_cover(self, tmp_path):
        info = ExampleInfo(
            is_example=True, summary="Card text", section=ExampleSection.ANALYSING_DATA, level=ExampleLevel.INTERMEDIATE,
            tag_ids=("physics", "curve_fitting"), featured_chart_ids=("c1", "c0"), start_note_id="n0", data_credit="Credit")
        project = _project("Full", "# Full\n\nLong text.", info, datasets=2, charts=3, notes=1)
        from tests.storage.test_project_data_manager import _png_bytes

        project.cover_image = _png_bytes()
        _save(tmp_path / "full.pplot", project)

        (example,) = discover_example_projects(tmp_path)

        assert example.name == "Full"
        assert example.summary == "Card text"
        assert example.description == "# Full\n\nLong text."
        assert example.section is ExampleSection.ANALYSING_DATA
        assert example.level is ExampleLevel.INTERMEDIATE
        assert example.tags == (example_tag("physics"), example_tag("curve_fitting"))
        assert example.featured_chart_ids == ("c1", "c0")
        assert example.start_note_id == "n0"
        assert example.data_credit == "Credit"
        assert example.cover_image == project.cover_image
        assert (example.dataset_count, example.chart_count, example.note_count) == (2, 3, 1)

    def test_no_example_block_gets_defaults_and_summary_from_description(self, tmp_path):
        _save(tmp_path / "plain.pplot", _project("Plain", "First sentence here. Second one."))

        (example,) = discover_example_projects(tmp_path)

        assert example.summary == "First sentence here."
        assert example.section is ExampleSection.GETTING_STARTED
        assert example.level is ExampleLevel.BEGINNER
        assert example.tags == ()
        assert example.featured_chart_ids == ()
        assert example.start_note_id is None
        assert example.cover_image is None
        assert (example.dataset_count, example.chart_count, example.note_count) == (0, 0, 0)

    def test_legacy_file_without_example_key_is_listed(self, tmp_path):
        _write_pplot(tmp_path / "legacy.pplot", "Legacy", "Old text. More.")

        (example,) = discover_example_projects(tmp_path)

        assert example.summary == "Old text."
        assert example.section is ExampleSection.GETTING_STARTED

    def test_unknown_featured_and_start_note_ids_are_filtered(self, tmp_path):
        info = ExampleInfo(featured_chart_ids=("c0", "gone", "n0"), start_note_id="c0")
        _save(tmp_path / "f.pplot", _project("F", info=info, charts=1, notes=1))

        (example,) = discover_example_projects(tmp_path)

        assert example.featured_chart_ids == ("c0",)
        assert example.start_note_id is None

    def test_unknown_tags_in_file_are_ignored(self, tmp_path):
        with zipfile.ZipFile(tmp_path / "t.pplot", "w") as archive:
            archive.writestr("project.json", json.dumps({"name": "T", "example": {"tags": ["physics", "nonsense"]}}))

        (example,) = discover_example_projects(tmp_path)

        assert [t.id for t in example.tags] == ["physics"]

    def test_ordered_by_section_then_name_case_insensitively(self, tmp_path):
        for file, name, section in [
            ("1", "zebra", ExampleSection.GETTING_STARTED),
            ("2", "Apple", ExampleSection.CHARTS),
            ("3", "banana", ExampleSection.GETTING_STARTED),
            ("4", "Cherry", ExampleSection.ANALYSING_DATA),
            ("5", "Aardvark", ExampleSection.GETTING_STARTED),
        ]:
            _save(tmp_path / f"{file}.pplot", _project(name, info=ExampleInfo(section=section)))

        names = [e.name for e in discover_example_projects(tmp_path)]

        assert names == ["Aardvark", "banana", "zebra", "Cherry", "Apple"]

    def test_bundled_examples_directory_discovers_five_projects(self):
        examples = discover_example_projects(get_examples_dir())

        assert len(examples) == 5
        assert all(e.name and e.path for e in examples)
        assert [e.section for e in examples] == sorted((e.section for e in examples), key=list(ExampleSection).index)


@pytest.mark.parametrize("attr", ["name", "path"])
def test_example_project_is_frozen(attr):
    example = ExampleProject(
        path="p", name="n", summary="", description="", section=ExampleSection.CHARTS, level=ExampleLevel.BEGINNER, tags=(),
        featured_chart_ids=(), start_note_id=None, data_credit="", cover_image=None, dataset_count=0, chart_count=0, note_count=0)
    with pytest.raises(AttributeError):
        setattr(example, attr, "x")
