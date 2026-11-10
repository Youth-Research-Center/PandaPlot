"""Tests for the bundled-icon loader and tinted QIcon renderer."""

import pytest
from PySide6.QtCore import QByteArray, QSize
from PySide6.QtGui import QColor, QIcon
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
