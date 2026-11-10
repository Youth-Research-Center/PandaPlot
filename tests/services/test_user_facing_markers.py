"""Messages written for users are marked with UserFacingError."""

import numpy as np
import pandas as pd
import pytest

from pandaplot.analysis.descriptive_engine import DescriptiveStatsEngine
from pandaplot.analysis.signal.methods import psd
from pandaplot.gui.components.tabs.sketch.sketch_export import SketchExportError
from pandaplot.services.data_import.data_importer import UnsupportedFileError
from pandaplot.services.fit.fit_service import FitService
from pandaplot.services.note_search.note_search_service import QueryError, compile_query
from pandaplot.services.transform.expression_engine import UnsafeExpressionError
from pandaplot.services.transform.formula_engine import CircularFormulaDependencyError
from pandaplot.utils.errors import UserFacingError


@pytest.mark.parametrize(
    "error_class",
    [UnsupportedFileError, UnsafeExpressionError, CircularFormulaDependencyError, QueryError, SketchExportError],
)
def test_existing_error_classes_are_user_facing(error_class):
    assert issubclass(error_class, UserFacingError)
    assert issubclass(error_class, ValueError)


def test_invalid_regex_raises_query_error_that_is_user_facing():
    with pytest.raises(UserFacingError):
        compile_query("(", use_regex=True)


def test_psd_rejects_a_non_positive_sampling_rate_with_a_user_facing_error():
    with pytest.raises(UserFacingError, match="Sampling rate must be greater than zero"):
        psd.run(pd.Series(np.arange(8, dtype=float)), sampling_rate=0)


def test_descriptive_statistics_without_columns_raise_user_facing_error():
    with pytest.raises(UserFacingError, match="at least one column"):
        DescriptiveStatsEngine.describe([])


def test_internal_unknown_fit_type_stays_a_plain_value_error():
    with pytest.raises(ValueError, match="Unknown fit type") as info:
        FitService()._get_fit_func("nope")
    assert not isinstance(info.value, UserFacingError)


def test_invalid_regex_message_is_plain_and_points_at_the_problem():
    with pytest.raises(QueryError) as info:
        compile_query("(", use_regex=True)

    message = str(info.value)
    assert message.startswith("The search text is not a valid regular expression (near character 1).")
    assert "unterminated" not in message


def test_disallowed_formula_constructs_are_named_in_plain_words():
    from pandaplot.services.transform.expression_engine import compile_expression

    with pytest.raises(UnsafeExpressionError) as info:
        compile_expression("(y := x)")

    assert str(info.value) == "Formulas cannot use assignments with :=."
