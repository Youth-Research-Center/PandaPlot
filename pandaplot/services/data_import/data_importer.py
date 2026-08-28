"""
Format-agnostic reader that turns a file + :class:`ImportOptions` into a
pandas DataFrame, plus the auto-detection helpers the wizard uses to pick
sensible defaults.

All logic here is pure (no Qt, no application state) so it can be unit-tested
directly and reused by both the interactive wizard preview and the background
full-file import.
"""

import csv
import os
from dataclasses import replace
from typing import List, Optional

import pandas as pd

from pandaplot.services.data_import.import_options import (
    CSV_FORMAT,
    EXCEL_FORMAT,
    JSON_FORMAT,
    ImportOptions,
)

# File extensions mapped to their logical format family.
CSV_EXTENSIONS = {".csv", ".txt", ".tsv", ".tab", ".dat"}
EXCEL_EXTENSIONS = {".xlsx", ".xls", ".xlsm"}
JSON_EXTENSIONS = {".json"}
SUPPORTED_EXTENSIONS = CSV_EXTENSIONS | EXCEL_EXTENSIONS | JSON_EXTENSIONS

# Encodings tried, in order, when reading text. Covers UTF-8, UTF-8 with a BOM
# (common for files exported by Excel), and the usual Windows/Latin fallbacks.
ENCODING_FALLBACKS = ("utf-8", "utf-8-sig", "cp1252", "latin-1")

# Candidate delimiters offered to csv.Sniffer during auto-detection.
_SNIFF_DELIMITERS = ",\t;|"

# How many bytes of a text file to sample for delimiter/header sniffing.
_SNIFF_SAMPLE_BYTES = 64 * 1024


class UnsupportedFileError(ValueError):
    """Raised when a file's extension maps to no known format."""


def get_extension(file_path: str) -> str:
    """Return the lower-cased extension of ``file_path`` (including the dot)."""
    return os.path.splitext(file_path)[1].lower()


def is_supported(file_path: str) -> bool:
    """Return True when the file's extension is one we know how to import."""
    return get_extension(file_path) in SUPPORTED_EXTENSIONS


def detect_format(file_path: str) -> str:
    """
    Map a file path to its logical format family.

    Raises:
        UnsupportedFileError: if the extension is not recognised.
    """
    extension = get_extension(file_path)
    if extension in CSV_EXTENSIONS:
        return CSV_FORMAT
    if extension in EXCEL_EXTENSIONS:
        return EXCEL_FORMAT
    if extension in JSON_EXTENSIONS:
        return JSON_FORMAT
    supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
    raise UnsupportedFileError(f"Unsupported file type '{extension}'. Supported types: {supported}")


def list_excel_sheets(file_path: str) -> List[str]:
    """Return the worksheet names of an Excel workbook, in workbook order."""
    with pd.ExcelFile(file_path) as excel_file:
        return list(excel_file.sheet_names)


def _read_text_sample(file_path: str, encoding: str, max_bytes: int = _SNIFF_SAMPLE_BYTES) -> str:
    """
    Read up to ``max_bytes`` of text from ``file_path``, trying ``encoding``
    first and then the standard fallbacks. Returns "" if the file can't be
    decoded by any of them (detection then falls back to defaults).
    """
    tried = [encoding] + [enc for enc in ENCODING_FALLBACKS if enc != encoding]
    for enc in tried:
        try:
            with open(file_path, "r", encoding=enc) as handle:
                return handle.read(max_bytes)
        except (UnicodeDecodeError, LookupError):
            continue
    return ""


def sniff_delimiter(file_path: str, encoding: str = "utf-8") -> str:
    """
    Best-effort detection of the field separator for a delimited-text file.

    Uses :class:`csv.Sniffer` on a sample of the file and falls back to the
    extension (``.tsv``/``.tab`` -> tab) or a comma when sniffing is
    inconclusive.
    """
    extension = get_extension(file_path)
    extension_default = "\t" if extension in {".tsv", ".tab"} else ","

    sample = _read_text_sample(file_path, encoding)
    if not sample.strip():
        return extension_default

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=_SNIFF_DELIMITERS)
        return dialect.delimiter
    except csv.Error:
        return extension_default


def detect_has_header(file_path: str, delimiter: str, encoding: str = "utf-8") -> bool:
    """
    Heuristically decide whether the first row is a header, the way a
    spreadsheet app does: a header row is typically all text while the data
    rows below contain numbers.

    Falls back to :meth:`csv.Sniffer.has_header`, and finally to True (assume a
    header) when the sample is too small to judge.
    """
    sample = _read_text_sample(file_path, encoding)
    if not sample.strip():
        return True

    # Primary heuristic: compare the first row against the block of rows below
    # it. If the first row is entirely non-numeric but later rows introduce
    # numeric fields, the first row is almost certainly a header.
    try:
        reader = csv.reader(sample.splitlines(), delimiter=("\t" if delimiter == r"\s+" else delimiter))
        rows = [row for row in reader if row]
    except csv.Error:
        rows = []

    if len(rows) >= 2:
        first, rest = rows[0], rows[1:6]
        first_has_number = any(_looks_numeric(cell) for cell in first)
        rest_has_number = any(_looks_numeric(cell) for row in rest for cell in row)
        if not first_has_number and rest_has_number:
            return True
        if first_has_number and rest_has_number:
            # First row already looks like data.
            return False

    # Fall back to the standard-library sniffer for ambiguous cases.
    try:
        return csv.Sniffer().has_header(sample)
    except csv.Error:
        return True


def _looks_numeric(value: str) -> bool:
    """Return True when a raw cell string parses as a real number."""
    text = value.strip()
    if not text:
        return False
    try:
        float(text)
        return True
    except ValueError:
        return False


def default_options(file_path: str) -> ImportOptions:
    """
    Build a sensible starting :class:`ImportOptions` for a file by detecting
    its format and, for delimited text, its delimiter and header presence.
    The wizard presents these as defaults the user can override.
    """
    file_format = detect_format(file_path)
    options = ImportOptions(file_format=file_format)

    if file_format == CSV_FORMAT:
        delimiter = sniff_delimiter(file_path, options.encoding)
        options = replace(
            options,
            delimiter=delimiter,
            has_header=detect_has_header(file_path=file_path, delimiter=delimiter, encoding=options.encoding),
        )
    elif file_format == EXCEL_FORMAT:
        sheets = list_excel_sheets(file_path)
        options = replace(options, sheet_name=sheets[0] if sheets else 0)

    return options


def read_dataframe(file_path: str, options: ImportOptions, nrows: Optional[int] = None) -> pd.DataFrame:
    """
    Read ``file_path`` into a DataFrame according to ``options``.

    Args:
        file_path: Path to the source file.
        options: Fully-resolved parse options.
        nrows: When given, read at most this many data rows. The wizard passes
            a small value for its live preview; the import reads everything.

    Raises:
        UnsupportedFileError: if the format is not recognised.
        ValueError / pandas errors: if the file cannot be parsed with the
            supplied options (surfaced to the user as a friendly message).
    """
    if options.file_format == CSV_FORMAT:
        df = _read_csv(file_path, options, nrows)
    elif options.file_format == EXCEL_FORMAT:
        df = _read_excel(file_path, options, nrows)
    elif options.file_format == JSON_FORMAT:
        df = _read_json(file_path, options, nrows)
    else:
        raise UnsupportedFileError(f"Unsupported file format '{options.file_format}'")

    return _finalize_columns(df, has_header=options.has_header)


def _read_csv(file_path: str, options: ImportOptions, nrows: Optional[int]) -> pd.DataFrame:
    """Read a delimited-text file, trying the requested encoding then fallbacks."""
    # Multi-character / regex separators (e.g. whitespace) require the slower
    # pure-Python parser; single characters use the fast C parser.
    engine = "python" if len(options.delimiter) > 1 else "c"
    header = 0 if options.has_header else None

    tried = [options.encoding] + [enc for enc in ENCODING_FALLBACKS if enc != options.encoding]
    last_error: Optional[UnicodeDecodeError] = None
    for encoding in tried:
        try:
            return pd.read_csv(
                file_path,
                sep=options.delimiter,
                header=header,
                skiprows=options.skip_rows,
                encoding=encoding,
                nrows=nrows,
                engine=engine,
            )
        except UnicodeDecodeError as error:
            last_error = error
            continue
    assert last_error is not None
    raise last_error


def _read_excel(file_path: str, options: ImportOptions, nrows: Optional[int]) -> pd.DataFrame:
    """Read a single worksheet from an Excel workbook."""
    header = 0 if options.has_header else None
    return pd.read_excel(
        file_path,
        sheet_name=options.sheet_name,
        header=header,
        skiprows=options.skip_rows,
        nrows=nrows,
    )


def _read_json(file_path: str, options: ImportOptions, nrows: Optional[int]) -> pd.DataFrame:
    """
    Read a JSON file into a DataFrame, supporting both a top-level array of
    records and newline-delimited JSON (one object per line).
    """
    try:
        df = pd.read_json(file_path, encoding=options.encoding)
    except ValueError:
        # Retry as line-delimited JSON, which the default reader rejects.
        df = pd.read_json(file_path, encoding=options.encoding, lines=True)

    if nrows is not None:
        df = df.head(nrows)
    return df


def _finalize_columns(df: pd.DataFrame, *, has_header: bool) -> pd.DataFrame:
    """
    Give headerless data friendly ``Column 1..N`` names instead of the integer
    positions pandas assigns, so the imported dataset is readable.
    """
    if not has_header:
        df = df.copy()
        df.columns = [f"Column {i + 1}" for i in range(df.shape[1])]
    return df
