from pandaplot.gui.components.common.snapshot_dpi_combo_box import CHART_DEFAULT_LABEL, SnapshotDpiComboBox


def test_defaults_to_the_chart_default(qapp):
    box = SnapshotDpiComboBox()

    assert box.value() is None
    assert box.currentText() == CHART_DEFAULT_LABEL


def test_offers_the_presets(qapp):
    box = SnapshotDpiComboBox()

    assert [box.itemText(i) for i in range(box.count())] == [CHART_DEFAULT_LABEL, "72", "100", "150", "300", "600"]


def test_set_value_selects_a_preset(qapp):
    box = SnapshotDpiComboBox()

    box.set_value(300)

    assert box.value() == 300
    assert box.currentText() == "300"


def test_set_value_none_returns_to_the_chart_default(qapp):
    box = SnapshotDpiComboBox()
    box.set_value(300)

    box.set_value(None)

    assert box.value() is None
    assert box.currentText() == CHART_DEFAULT_LABEL


def test_set_value_shows_a_custom_value(qapp):
    box = SnapshotDpiComboBox()

    box.set_value(220)

    assert box.value() == 220
    assert box.currentText() == "220"


def test_set_value_clamps_to_the_supported_range(qapp):
    box = SnapshotDpiComboBox()

    box.set_value(5000)
    assert box.value() == 600
    box.set_value(5)
    assert box.value() == 30


def test_typed_text_is_parsed_and_clamped(qapp):
    box = SnapshotDpiComboBox()

    box.setEditText(" 220 ")
    assert box.value() == 220
    box.setEditText("1000")
    assert box.value() == 600
    box.setEditText("10")
    assert box.value() == 30


def test_unparseable_text_means_the_chart_default(qapp):
    box = SnapshotDpiComboBox()

    box.setEditText("abc")
    assert box.value() is None
    box.setEditText("")
    assert box.value() is None


def test_finishing_an_edit_shows_the_normalized_value(qapp):
    box = SnapshotDpiComboBox()
    box.setEditText("1000")

    box.lineEdit().editingFinished.emit()

    assert box.currentText() == "600"


def test_set_value_none_discards_text_typed_while_on_the_chart_default_entry(qapp):
    box = SnapshotDpiComboBox()
    box.setEditText("220")

    box.set_value(None)

    assert box.value() is None
    assert box.currentText() == CHART_DEFAULT_LABEL


def test_set_value_replaces_text_typed_over_the_same_preset(qapp):
    box = SnapshotDpiComboBox()
    box.set_value(300)
    box.setEditText("250")

    box.set_value(300)

    assert box.value() == 300
    assert box.currentText() == "300"
