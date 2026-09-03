"""Tests for ErrorBarConfig.without_column_bindings() (#268)."""

from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.error_direction import ErrorDirection


class TestWithoutColumnBindings:
    def test_clears_all_eight_column_binding_fields(self):
        config = ErrorBarConfig(
            x_error_column_id="x-id", y_error_column_id="y-id",
            x_error_minus_column_id="xm-id", y_error_minus_column_id="ym-id",
            x_error_column="x_err", y_error_column="y_err",
            x_error_minus_column="x_err_minus", y_error_minus_column="y_err_minus",
        )

        cleared = config.without_column_bindings()

        assert cleared.x_error_column_id == ""
        assert cleared.y_error_column_id == ""
        assert cleared.x_error_minus_column_id == ""
        assert cleared.y_error_minus_column_id == ""
        assert cleared.x_error_column == ""
        assert cleared.y_error_column == ""
        assert cleared.x_error_minus_column == ""
        assert cleared.y_error_minus_column == ""

    def test_keeps_pure_visual_config(self):
        config = ErrorBarConfig(
            y_error_column_id="y-id",
            error_symmetric=False,
            error_direction=ErrorDirection.PLUS,
            error_color="#ff0000",
            error_cap_size=5.0,
        )

        cleared = config.without_column_bindings()

        assert cleared.error_symmetric is False
        assert cleared.error_direction == ErrorDirection.PLUS
        assert cleared.error_color == "#ff0000"
        assert cleared.error_cap_size == 5.0

    def test_has_error_data_is_false_after_clearing(self):
        config = ErrorBarConfig(y_error_column_id="y-id")
        assert config.has_error_data is True

        cleared = config.without_column_bindings()

        assert cleared.has_error_data is False

    def test_returns_a_new_instance_not_the_same_object(self):
        config = ErrorBarConfig(y_error_column_id="y-id")
        cleared = config.without_column_bindings()
        assert cleared is not config
        assert config.y_error_column_id == "y-id"
