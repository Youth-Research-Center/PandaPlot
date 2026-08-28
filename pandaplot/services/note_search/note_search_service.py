"""Full-text search across the notes in a project.

Pure, Qt-free logic so it can be unit tested and reused headlessly. Searches
both a note's title and its content, returning per-note results with enough
positional information for the UI to render highlighted snippets and to jump
the editor to a specific match.
"""

import re
from dataclasses import dataclass, field

# Match-count guard so a broad query against a huge note can't produce an
# unbounded results list (and freeze the UI building rows for it).
_MAX_MATCHES_PER_NOTE = 200


@dataclass(frozen=True)
class NoteMatch:
    """A single occurrence of the query within one note."""

    line_number: int  # 1-based line within the content; 0 marks a title match
    line_text: str  # the full line the match sits on (title text for titles)
    match_start: int  # match offset within line_text
    match_end: int  # exclusive end offset within line_text
    in_title: bool = False


@dataclass(frozen=True)
class NoteSearchResult:
    """All matches found in a single note."""

    note_id: str
    note_name: str
    matches: list[NoteMatch] = field(default_factory=list)
    truncated: bool = False  # True if matches were capped at the per-note limit

    @property
    def match_count(self) -> int:
        return len(self.matches)


class QueryError(ValueError):
    """Raised when a user-supplied regular expression fails to compile."""


def compile_query(
    query: str,
    *,
    case_sensitive: bool = False,
    whole_word: bool = False,
    use_regex: bool = False,
) -> re.Pattern:
    """Compile a search ``query`` into a regex pattern.

    Plain queries are escaped so regex metacharacters are treated literally.
    Raises :class:`QueryError` if ``use_regex`` is set and the pattern is
    invalid, so callers can surface a friendly message.
    """
    pattern = query if use_regex else re.escape(query)
    if whole_word:
        pattern = rf"\b{pattern}\b"
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        return re.compile(pattern, flags)
    except re.error as exc:
        raise QueryError(str(exc)) from exc


def _find_in_line(
    pattern: re.Pattern, line: str, line_number: int, *, in_title: bool, remaining: int
) -> tuple[list[NoteMatch], bool]:
    """Collect up to ``remaining`` matches on a single line.

    Returns the matches and whether the per-note cap was hit while scanning.
    """
    matches: list[NoteMatch] = []
    for m in pattern.finditer(line):
        if m.start() == m.end():
            # Zero-width match (e.g. an empty/optional regex) -- skip so we
            # neither loop forever nor emit meaningless highlights.
            continue
        if len(matches) >= remaining:
            return matches, True
        matches.append(
            NoteMatch(
                line_number=line_number,
                line_text=line,
                match_start=m.start(),
                match_end=m.end(),
                in_title=in_title,
            )
        )
    return matches, False


def search_note(pattern: re.Pattern, note_id: str, note_name: str, content: str) -> NoteSearchResult | None:
    """Search a single note. Returns ``None`` when there are no matches."""
    matches: list[NoteMatch] = []
    truncated = False

    def _remaining() -> int:
        return _MAX_MATCHES_PER_NOTE - len(matches)

    # Title first, so title hits sort to the top of a note's match list.
    title_matches, title_truncated = _find_in_line(
        pattern, note_name or "", 0, in_title=True, remaining=_remaining()
    )
    matches.extend(title_matches)
    truncated = truncated or title_truncated

    if not truncated:
        for i, line in enumerate(content.splitlines(), start=1):
            if _remaining() <= 0:
                truncated = True
                break
            line_matches, line_truncated = _find_in_line(
                pattern, line, i, in_title=False, remaining=_remaining()
            )
            matches.extend(line_matches)
            if line_truncated:
                truncated = True
                break

    if not matches:
        return None
    return NoteSearchResult(note_id=note_id, note_name=note_name, matches=matches, truncated=truncated)


def search_notes(
    notes,
    query: str,
    *,
    case_sensitive: bool = False,
    whole_word: bool = False,
    use_regex: bool = False,
) -> list[NoteSearchResult]:
    """Search a collection of notes.

    ``notes`` is any iterable of objects exposing ``id``, ``name`` and
    ``content`` (i.e. :class:`~pandaplot.models.project.items.note.Note`).
    An empty or whitespace-only ``query`` yields no results. Results are
    ordered by descending match count, then by note name.
    """
    if not query.strip():
        return []

    pattern = compile_query(
        query,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
        use_regex=use_regex,
    )

    results: list[NoteSearchResult] = []
    for note in notes:
        result = search_note(
            pattern, note_id=note.id, note_name=note.name, content=getattr(note, "content", "") or ""
        )
        if result is not None:
            results.append(result)

    results.sort(key=lambda r: (-r.match_count, r.note_name.lower()))
    return results


def build_snippet(match: NoteMatch, context: int = 40) -> tuple[str, int, int]:
    """Build a trimmed one-line snippet around a match for display.

    Returns ``(snippet_text, highlight_start, highlight_end)`` where the
    highlight offsets index into ``snippet_text``. Up to ``context`` characters
    on each side of the match are kept; trimmed ends are marked with an
    ellipsis. Leading whitespace on the line is dropped so snippets align.
    """
    line = match.line_text
    start, end = match.match_start, match.match_end

    # Drop leading indentation, keeping match offsets consistent.
    stripped = line.lstrip()
    removed = len(line) - len(stripped)
    start = max(0, start - removed)
    end = max(start, end - removed)
    line = stripped

    left = max(0, start - context)
    right = min(len(line), end + context)

    prefix = "…" if left > 0 else ""
    suffix = "…" if right < len(line) else ""

    snippet = prefix + line[left:right] + suffix
    hl_start = len(prefix) + (start - left)
    hl_end = len(prefix) + (end - left)
    return snippet, hl_start, hl_end
