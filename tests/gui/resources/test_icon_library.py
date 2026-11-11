"""Tests for the bundled-icon loader and tinted QIcon renderer."""

import pytest
from PySide6.QtCore import QByteArray, QSize
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtSvg import QSvgRenderer

from pandaplot.gui.resources import icon_library
from tests.gui.icon_testing import assert_tinted, strongest_pixel


def test_icon_svg_returns_a_tintable_svg():
    svg = icon_library.icon_svg("folder")

    assert svg.startswith("<svg")
    assert "currentColor" in svg


def test_icon_svg_unknown_icon_names_the_icon_and_how_to_add_it():
    with pytest.raises(KeyError, match="no-such-icon.*icon_manifest.toml"):
        icon_library.icon_svg("no-such-icon")


def test_icon_svg_unknown_weight_lists_available_weights():
    with pytest.raises(KeyError, match="bold.*regular"):
        icon_library.icon_svg("folder", weight="bold")


def test_icon_attributions_name_each_source_with_version_and_licence():
    sources = icon_library._load_bundle()["sources"]
    expected = [f"{meta['title']} {meta['version']} ({meta['license']})" for _, meta in sorted(sources.items())]

    attributions = icon_library.icon_attributions()

    assert attributions == expected
    assert any(line.startswith("Phosphor Icons ") for line in attributions)


def test_every_bundled_icon_renders_in_every_weight(qapp):
    for name, entry in icon_library._load_bundle()["icons"].items():
        for weight, svg in entry["weights"].items():
            renderer = QSvgRenderer(QByteArray(svg.replace("currentColor", "#000000").encode("utf-8")))
            assert renderer.isValid(), f"{name}/{weight}"
            assert not icon_library.build_icon(name, "#000000", weight=weight).isNull(), f"{name}/{weight}"


def test_build_icon_renders_in_the_requested_colour(qapp):
    tint = QColor("#2255aa")

    icon = icon_library.build_icon("folder", "#2255aa", size=48)

    assert isinstance(icon, QIcon) and not icon.isNull()
    image = icon.pixmap(QSize(48, 48)).toImage()
    strongest = max(
        (image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height())),
        key=lambda pixel: pixel.alpha(),
    )
    assert strongest.alpha() > 200
    assert abs(strongest.red() - tint.red()) < 8
    assert abs(strongest.green() - tint.green()) < 8
    assert abs(strongest.blue() - tint.blue()) < 8


def test_build_icon_uses_disabled_colour_for_disabled_mode(qapp):
    icon = icon_library.build_icon("folder", "#2255aa", size=48, disabled_color="#aa2222")

    image = icon.pixmap(QSize(48, 48), QIcon.Mode.Disabled).toImage()
    strongest = max(
        (image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height())),
        key=lambda pixel: pixel.alpha(),
    )
    assert strongest.red() > strongest.blue()


def test_build_icon_rejects_an_invalid_colour(qapp):
    with pytest.raises(ValueError, match="colour"):
        icon_library.build_icon("folder", "not-a-colour")


def test_build_icon_uses_selected_colour_for_selected_mode(qapp):
    icon = icon_library.build_icon("folder", "#2255aa", size=48, selected_color="#ffffff")

    selected = strongest_pixel(icon.pixmap(QSize(48, 48), QIcon.Mode.Selected))
    normal = strongest_pixel(icon.pixmap(QSize(48, 48), QIcon.Mode.Normal))
    assert_tinted(selected, "#ffffff")
    assert_tinted(normal, "#2255aa")


class _RenderCounter:
    """Counts `QSvgRenderer` instances created by the icon library (one per rendered pixmap)."""

    def __init__(self) -> None:
        self.count = 0


@pytest.fixture
def render_counter(monkeypatch):
    """Start every test from an empty icon cache and count the SVG renders the library performs."""
    icon_library.clear_icon_cache()
    counter = _RenderCounter()

    def counting_renderer(data):
        counter.count += 1
        return QSvgRenderer(data)

    monkeypatch.setattr(icon_library, "QSvgRenderer", counting_renderer)
    yield counter
    icon_library.clear_icon_cache()


def test_identical_icons_are_rendered_once(qapp, render_counter):
    icon_library.build_icon("folder", "#2255aa", size=16)
    icon_library.build_icon("folder", "#2255aa", size=16)

    assert render_counter.count == 1


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ({"name": "folder", "color": "#2255aa"}, {"name": "table", "color": "#2255aa"}),
        ({"name": "folder", "color": "#2255aa"}, {"name": "folder", "color": "#aa2222"}),
        ({"name": "folder", "color": "#2255aa", "size": 16}, {"name": "folder", "color": "#2255aa", "size": 24}),
    ],
    ids=["name", "colour", "size"],
)
def test_a_different_name_colour_or_size_renders_again(qapp, render_counter, first, second):
    icon_library.build_icon(**first)
    icon_library.build_icon(**second)

    assert render_counter.count == 2


def test_a_different_weight_renders_again(qapp, render_counter, monkeypatch):
    regular_svg = icon_library.icon_svg("folder")
    # Only the regular weight is bundled, so another weight is simulated.
    monkeypatch.setattr(icon_library, "icon_svg", lambda name, *, weight: regular_svg)

    icon_library.build_icon("folder", "#2255aa", weight="regular")
    icon_library.build_icon("folder", "#2255aa", weight="fill")

    assert render_counter.count == 2


def test_a_different_device_pixel_ratio_renders_again(qapp, render_counter, monkeypatch):
    monkeypatch.setattr(icon_library, "_device_pixel_ratio", lambda: 1.0)
    icon_library.build_icon("folder", "#2255aa")
    monkeypatch.setattr(icon_library, "_device_pixel_ratio", lambda: 2.0)
    icon = icon_library.build_icon("folder", "#2255aa")

    assert render_counter.count == 2
    assert icon.availableSizes() == [QSize(40, 40)]


def test_each_icon_state_is_rendered_once_per_colour(qapp, render_counter):
    for _ in range(3):
        icon_library.build_icon("folder", "#2255aa", disabled_color="#aaaaaa", selected_color="#ffffff")

    assert render_counter.count == 3


def test_clear_icon_cache_forces_a_re_render(qapp, render_counter):
    icon_library.build_icon("folder", "#2255aa")
    icon_library.clear_icon_cache()
    icon_library.build_icon("folder", "#2255aa")

    assert render_counter.count == 2


def test_cached_icons_are_independent_objects(qapp, render_counter):
    first = icon_library.build_icon("folder", "#2255aa", size=48)
    second = icon_library.build_icon("folder", "#2255aa", size=48)
    assert first is not second

    extra = QPixmap(48, 48)
    extra.fill(QColor("#ff0000"))
    first.addPixmap(extra, QIcon.Mode.Disabled)

    third = icon_library.build_icon("folder", "#2255aa", size=48)
    assert_tinted(strongest_pixel(third.pixmap(QSize(48, 48), QIcon.Mode.Normal)), "#2255aa")
    assert strongest_pixel(third.pixmap(QSize(48, 48), QIcon.Mode.Disabled)).red() < 200
    assert render_counter.count == 1


def test_a_failed_render_is_not_cached(qapp, render_counter):
    for _ in range(2):
        with pytest.raises(ValueError, match="colour"):
            icon_library.build_icon("folder", "not-a-colour")
