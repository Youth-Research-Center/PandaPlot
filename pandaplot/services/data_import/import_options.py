"""
Parse options describing how to interpret a structured data file.

The :class:`ImportOptions` dataclass is the single contract shared between the
import wizard UI (which builds it interactively) and the importer service
(which turns it into a DataFrame). Keeping it a plain dataclass means the
parsing logic stays free of Qt and is easy to unit-test.
"""

from dataclasses import dataclass

# Logical file formats. These are format *families*, not file extensions:
# a ``.txt`` file is still the CSV/delimited-text family.
CSV_FORMAT = "csv"
EXCEL_FORMAT = "excel"
JSON_FORMAT = "json"

# Named delimiters offered in the wizard, mapped to the actual separator string
# passed to pandas. "Auto-detect" is handled separately (see DataImporter).
NAMED_DELIMITERS = {
    "Comma  (,)": ",",
    "Tab  (\\t)": "\t",
    "Semicolon  (;)": ";",
    "Pipe  (|)": "|",
    "Whitespace": r"\s+",
}


@dataclass
class ImportOptions:
    """
    A fully-resolved description of how to parse a data file.

    ``delimiter``, ``skip_rows``, and ``encoding`` apply only to delimited
    text; ``sheet_name`` only to Excel. ``delimiter`` may be a regex (e.g.
    ``r"\\s+"``) rather than a literal separator. When ``has_header`` is
    False, synthetic ``Column 1..N`` names are generated instead.
    """

    file_format: str = CSV_FORMAT
    delimiter: str = ","
    has_header: bool = True
    skip_rows: int = 0
    encoding: str = "utf-8"
    sheet_name: "str | int" = 0
