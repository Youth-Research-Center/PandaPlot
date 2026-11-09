"""Catalog-wide checks that need every help content module at once."""

import importlib

import pytest

from pandaplot.gui.dialogs.help.help_html import render_help_topic_html
from pandaplot.services.help.help_catalog import CONTENT_MODULES, build_help_catalog
from pandaplot.services.help.help_types import PANEL_TOPIC_IDS, WIZARD_TOPIC_IDS, HelpCategory


@pytest.fixture(scope="module")
def catalog():
    return build_help_catalog()


def test_every_related_id_resolves(catalog):
    unresolved = [(topic.id, related) for topic in catalog.topics() for related in topic.related if catalog.get(related) is None]
    assert unresolved == []


def test_every_category_is_used(catalog):
    assert set(catalog.by_category()) == set(HelpCategory)


def test_every_panel_topic_exists(catalog):
    assert [topic_id for topic_id in PANEL_TOPIC_IDS if catalog.get(topic_id) is None] == []


def test_every_wizard_topic_exists(catalog):
    assert [topic_id for topic_id in WIZARD_TOPIC_IDS if catalog.get(topic_id) is None] == []


def test_every_mapped_topic_id_exists(catalog):
    missing = []
    for module_name in CONTENT_MODULES:
        module = importlib.import_module(module_name)
        mappings = {name: value for name, value in vars(module).items() if name.endswith("_TOPIC_IDS") and isinstance(value, dict)}
        for name, mapping in mappings.items():
            missing.extend(f"{module_name}.{name}: {topic_id}" for topic_id in mapping.values() if catalog.get(topic_id) is None)
    assert missing == []


def test_content_modules_expose_mappings():
    names = {name for module_name in CONTENT_MODULES for name in vars(importlib.import_module(module_name)) if name.endswith("_TOPIC_IDS")}
    expected = {"STAT_TEST_TOPIC_IDS", "PREPROCESSING_TOPIC_IDS", "SIGNAL_TOPIC_IDS", "FIT_MODEL_TOPIC_IDS", "ANALYSIS_TOPIC_IDS",
                "SMOOTHING_TOPIC_IDS", "DERIVATIVE_TOPIC_IDS", "INTERPOLATION_TOPIC_IDS",
                "CHART_TYPE_TOPIC_IDS"}
    assert expected <= names


def test_every_topic_renders(catalog):
    palette = {"base_fg": "#000000", "secondary_fg": "#555555", "accent": "#0055aa", "card_bg": "#ffffff", "card_border": "#dddddd"}
    for topic in catalog.topics():
        html = render_help_topic_html(topic, palette, lambda topic_id: (found.title if (found := catalog.get(topic_id)) else None))
        assert topic.title.split()[0] in html or "&" in topic.title
