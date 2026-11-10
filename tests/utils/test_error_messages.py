"""Tests for describe_error / describe_failure, using really raised exceptions."""

import errno
import io
import json
import zipfile
from collections.abc import Callable

import numpy as np
import pandas as pd
import pytest

from pandaplot.utils.error_messages import ErrorDescription, describe_error, describe_failure
from pandaplot.utils.errors import UserFacingError

_GENERIC_VALUE_REASON = "PandaPlot could not process this data with these settings."
_FALLBACK_REASON = "Something went wrong that PandaPlot did not expect."


def _raised(fn: Callable[[], object]) -> BaseException:
    try:
        fn()
    except BaseException as exc:  # noqa: BLE001 - the helper captures whatever the callable raises
        return exc
    raise AssertionError("callable did not raise")


def _float_of_text() -> float:
    return float("abc")


def _raise_import_error() -> None:
    raise ImportError("No module named 'openpyxl'")


def _divide() -> float:
    return 1 / 0


def _raise_memory() -> None:
    raise MemoryError


def _own_key_error() -> object:
    return {}["b"]


def _pandas_key_error() -> object:
    return pd.DataFrame({"a": [1]})["b"]


def _raise_no_arg_key_error() -> None:
    raise KeyError


def _raise(exc: BaseException) -> Callable[[], None]:
    def _fn() -> None:
        raise exc

    return _fn


# (id, callable that raises, expected reason fragment, expected next-step fragment)
_ROWS = [
    ("file_not_found", _raise(FileNotFoundError("x")), "could not be found", "still there"),
    ("permission", _raise(PermissionError(errno.EACCES, "denied")), "not allowed to open or change", "folder"),
    ("is_a_directory", _raise(IsADirectoryError("x")), "A folder was used", "Choose the file again."),
    ("not_a_directory", _raise(NotADirectoryError("x")), "A folder was used", "Choose the file again."),
    ("disk_full", _raise(OSError(errno.ENOSPC, "x")), "not enough free disk space", "Free some space"),
    ("other_os_error", _raise(OSError(errno.EIO, "x")), "could not read or write", "file name and location"),
    ("bad_zip", lambda: zipfile.ZipFile(io.BytesIO(b"x")), "damaged or is not the type", "backup copy"),
    ("json", lambda: json.loads("x"), "Part of this file is damaged", "backup copy"),
    ("unicode", lambda: b"\xff".decode("utf-8"), "different encoding", "Latin-1"),
    ("empty_data", lambda: pd.read_csv(io.StringIO("")), "no data to read", "right file"),
    ("parser", lambda: pd.read_csv(io.StringIO("a,b\n1,2,3\n4,5,6,7")), "do not match its columns", "delimiter"),
    ("import_error", _raise_import_error, "not installed", "another format"),
    ("pandas_key_error", _pandas_key_error, "no longer in the dataset", "choose the columns again"),
    ("lin_alg", lambda: np.linalg.inv(np.zeros((2, 2))), "cannot be solved", "more varied data"),
    ("zero_division", _divide, "too large or undefined", "zeros or extreme"),
    ("overflow", _raise(OverflowError("x")), "too large or undefined", "zeros or extreme"),
    ("floating_point", _raise(FloatingPointError("x")), "too large or undefined", "zeros or extreme"),
    ("memory", _raise_memory, "not enough memory", "less data"),
    ("c_level_value_error", _float_of_text, _GENERIC_VALUE_REASON, "for example numbers"),
    ("type_error", _raise(TypeError("x")), _GENERIC_VALUE_REASON, "for example numbers"),
    ("fallback", _raise(RuntimeError("x")), _FALLBACK_REASON, "report it"),
    ("own_key_error", _own_key_error, _FALLBACK_REASON, "report it"),
]


@pytest.mark.parametrize(("fn", "reason", "next_step"), [row[1:] for row in _ROWS], ids=[row[0] for row in _ROWS])
def test_rule_table_row(fn, reason, next_step):
    exc = _raised(fn)
    description = describe_error(exc)
    assert reason in description.reason
    assert next_step in description.next_step
    assert description.details.startswith(f"{type(exc).__name__}: ")


def test_user_facing_error_passes_through_unchanged():
    description = describe_error(UserFacingError("Pick a column."))
    assert description == ErrorDescription(reason="Pick a column.", next_step="", details="")


def test_c_level_value_error_is_not_treated_as_ours():
    description = describe_error(_raised(_float_of_text))
    assert description.reason == _GENERIC_VALUE_REASON
    assert "could not convert string to float: 'abc'" in description.details


def test_pandas_key_error_details_do_not_double_quote_the_name():
    description = describe_error(_raised(_pandas_key_error))
    assert description.details == "KeyError: b"


def test_key_error_without_args_has_empty_text():
    description = describe_error(_raised(_raise_no_arg_key_error))
    assert description.reason == _FALLBACK_REASON
    assert description.details == "KeyError: "


def test_file_not_found_is_matched_before_os_error():
    assert "could not be found" in describe_error(FileNotFoundError("x")).reason


def test_unicode_decode_error_is_matched_before_value_error():
    assert "different encoding" in describe_error(_raised(lambda: b"\xff".decode("utf-8"))).reason


def test_details_keep_the_original_text_for_unexpected_errors():
    assert describe_error(RuntimeError("boom")).details == "RuntimeError: boom"


def test_describe_failure_has_no_details():
    assert describe_failure("The selected file is empty.") == ErrorDescription(
        reason="The selected file is empty.", next_step="", details=""
    )
    assert describe_failure("Nope.", "Try again.").next_step == "Try again."


def test_formula_typo_and_unknown_name_get_formula_wording():
    try:
        compile("x +* 2", "<formula>", "eval")
    except SyntaxError as exc:
        syntax = describe_error(exc)
    try:
        eval("x + foo", {"__builtins__": {}}, {"x": 1})
    except NameError as exc:
        name = describe_error(exc)

    assert syntax.reason == "The formula has a typo, for example a missing bracket, quote or operator."
    assert name.reason == "The formula uses a name that PandaPlot does not know."
    assert name.details == "NameError: name 'foo' is not defined"


def test_inline_text_joins_reason_and_next_step():
    assert describe_failure("It failed.", "Try again.").inline_text == "It failed. Try again."
    assert describe_failure("It failed.").inline_text == "It failed."


def test_download_failures_are_not_described_as_local_file_problems():
    import requests

    try:
        raise requests.ConnectionError("Max retries exceeded with url: /x.png")
    except requests.ConnectionError as exc:
        description = describe_error(exc)

    assert description.reason == "PandaPlot could not download this from the internet."
    assert description.next_step == "Check the address and your internet connection, then try again."


def _uses_a_local_before_assignment() -> int:
    if False:
        value = 1
    return value


def test_name_errors_in_our_own_code_are_not_blamed_on_a_formula():
    try:
        _uses_a_local_before_assignment()
    except UnboundLocalError as exc:
        unbound = describe_error(exc)
    try:
        undefined_in_source()
    except NameError as exc:
        undefined = describe_error(exc)

    assert unbound.reason == "Something went wrong that PandaPlot did not expect."
    assert undefined.reason == "Something went wrong that PandaPlot did not expect."
