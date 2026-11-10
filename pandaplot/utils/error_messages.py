"""Plain-language descriptions of exceptions for error dialogs.

This module has no GUI imports and is safe to call from a worker thread.
"""

import errno
import json
import types
import zipfile
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd
import requests

from pandaplot.utils.errors import UserFacingError


@dataclass(frozen=True)
class ErrorDescription:
    """A user-readable account of a failure.

    Attributes:
        reason: Plain-language cause, one or two short sentences.
        next_step: What to try next, one sentence ("" if none).
        details: "ExceptionType: original text" ("" for non-exception failures and for
            messages written for the user).
    """

    reason: str
    next_step: str
    details: str

    @property
    def text(self) -> str:
        """The reason, then a blank line and the next step if there is one: for dialogs and result boxes."""
        return f"{self.reason}\n\n{self.next_step}" if self.next_step else self.reason

    @property
    def inline_text(self) -> str:
        """The reason and next step on one line, for inline status texts in panels."""
        return f"{self.reason} {self.next_step}".strip()


def describe_failure(reason: str, next_step: str = "") -> ErrorDescription:
    """Describe a failure that is not an exception.

    Args:
        reason: Plain-language cause.
        next_step: What to try next, if anything.

    Returns:
        An ErrorDescription with empty details.
    """
    return ErrorDescription(reason=reason, next_step=next_step, details="")


def _innermost_module(exc: BaseException) -> str:
    """Return the module name of the innermost traceback frame, or "" if unknown."""
    tb: types.TracebackType | None = exc.__traceback__
    if tb is None:
        return ""
    while tb.tb_next is not None:
        tb = tb.tb_next
    return str(tb.tb_frame.f_globals.get("__name__", ""))


def _is_pandas_key_error(exc: BaseException) -> bool:
    return isinstance(exc, KeyError) and _innermost_module(exc).startswith("pandas.")


def _is_network_error(exc: BaseException) -> bool:
    return isinstance(exc, requests.RequestException)


def _raised_in_evaluated_code(exc: BaseException) -> bool:
    """True when the innermost frame runs code compiled from a string (a user formula), not a source file."""
    tb: types.TracebackType | None = exc.__traceback__
    if tb is None:
        return False
    while tb.tb_next is not None:
        tb = tb.tb_next
    return tb.tb_frame.f_code.co_filename.startswith("<")


def _is_formula_syntax_error(exc: BaseException) -> bool:
    # A formula compiled from a string has a pseudo file name such as "<string>" or "<unknown>".
    return isinstance(exc, SyntaxError) and (exc.filename or "<").startswith("<")


def _is_formula_name_error(exc: BaseException) -> bool:
    # UnboundLocalError and undefined names in PandaPlot's own code are bugs, not formula typos.
    return isinstance(exc, NameError) and not isinstance(exc, UnboundLocalError) and _raised_in_evaluated_code(exc)


def _is_disk_full(exc: BaseException) -> bool:
    return isinstance(exc, OSError) and exc.errno == errno.ENOSPC


# Ordered rules: the first matching rule wins.
_Rule = tuple[Callable[[BaseException], bool], str, str]
_RULES: tuple[_Rule, ...] = (
    (
        lambda e: isinstance(e, FileNotFoundError),
        "The file could not be found. It may have been moved, renamed or deleted.",
        "Check that the file is still there, then try again.",
    ),
    (
        lambda e: isinstance(e, PermissionError),
        "PandaPlot is not allowed to open or change this file.",
        "Close it in any other program and check that you can use this folder, then try again.",
    ),
    (
        lambda e: isinstance(e, IsADirectoryError | NotADirectoryError),
        "A folder was used where a file was expected, or the other way round.",
        "Choose the file again.",
    ),
    (
        _is_disk_full,
        "There is not enough free disk space.",
        "Free some space, then try again.",
    ),
    (
        # requests' exceptions subclass OSError, so this must come before the generic file rule.
        _is_network_error,
        "PandaPlot could not download this from the internet.",
        "Check the address and your internet connection, then try again.",
    ),
    (
        lambda e: isinstance(e, OSError),
        "The computer could not read or write the file.",
        "Check the file name and location, then try again.",
    ),
    (
        lambda e: isinstance(e, zipfile.BadZipFile),
        "This file is damaged or is not the type its name suggests.",
        "Check that you chose the right file, or try a backup copy.",
    ),
    (
        lambda e: isinstance(e, json.JSONDecodeError),
        "Part of this file is damaged and cannot be read.",
        "Try a backup copy of the file.",
    ),
    (
        lambda e: isinstance(e, UnicodeDecodeError),
        "The file's text uses a different encoding than expected.",
        "When importing, try another encoding in the import options, such as UTF-8 or Latin-1.",
    ),
    (
        lambda e: isinstance(e, pd.errors.EmptyDataError),
        "The file has no data to read.",
        "Check that you chose the right file.",
    ),
    (
        lambda e: isinstance(e, pd.errors.ParserError),
        "The rows in the file do not match its columns.",
        "Check the delimiter and header settings in the import options.",
    ),
    (
        lambda e: isinstance(e, ImportError),
        "A component needed for this file type is not installed.",
        "Install PandaPlot's full version, or save the file in another format (for example CSV).",
    ),
    (
        _is_pandas_key_error,
        "A column this needs is no longer in the dataset.",
        "It may have been renamed or deleted; choose the columns again.",
    ),
    (
        lambda e: isinstance(e, np.linalg.LinAlgError),
        "The calculation cannot be solved for this data, for example when the values are all the same.",
        "Check the selected columns, or try with more varied data.",
    ),
    (
        _is_formula_syntax_error,
        "The formula has a typo, for example a missing bracket, quote or operator.",
        "Check the formula and try again.",
    ),
    (
        _is_formula_name_error,
        "The formula uses a name that PandaPlot does not know.",
        "Check the spelling of column names and functions in the formula.",
    ),
    (
        lambda e: isinstance(e, ZeroDivisionError | OverflowError | FloatingPointError),
        "The calculation produced a value that is too large or undefined for this data.",
        "Check the selected data for zeros or extreme values.",
    ),
    (
        lambda e: isinstance(e, MemoryError),
        "There is not enough memory for this.",
        "Try with less data, or close other programs.",
    ),
    (
        lambda e: isinstance(e, ValueError | TypeError),
        "PandaPlot could not process this data with these settings.",
        "Check that the selected columns contain the kind of values this needs, for example numbers.",
    ),
)

_FALLBACK_REASON = "Something went wrong that PandaPlot did not expect."
_FALLBACK_NEXT_STEP = "If it keeps happening, please report it."


def _details(exc: BaseException) -> str:
    text = str(exc.args[0]) if isinstance(exc, KeyError) and exc.args else str(exc)
    return f"{type(exc).__name__}: {text}"


def describe_error(exc: BaseException) -> ErrorDescription:
    """Describe an exception in plain language.

    Args:
        exc: The exception to describe.

    Returns:
        An ErrorDescription. A UserFacingError's message is used unchanged as the reason; its
        details hold the chained cause (``raise ... from e``) when there is one, and are empty
        for a standalone validation error. Every other exception is matched against an ordered
        rule table and its original text is kept in ``details``.
    """
    if isinstance(exc, UserFacingError):
        cause = exc.__cause__
        return ErrorDescription(reason=str(exc), next_step="", details=_details(cause) if cause is not None else "")
    for matches, reason, next_step in _RULES:
        if matches(exc):
            return ErrorDescription(reason=reason, next_step=next_step, details=_details(exc))
    return ErrorDescription(reason=_FALLBACK_REASON, next_step=_FALLBACK_NEXT_STEP, details=_details(exc))
