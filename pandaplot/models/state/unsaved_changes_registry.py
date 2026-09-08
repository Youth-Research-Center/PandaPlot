"""Generic registry for widgets holding local, not-yet-committed edits.

Replaces the note-specific TabContainer-walking helper that PR #352 first
shipped for issue #318: any widget with a locally-buffered edit that hasn't
made it into the project model yet (e.g. NoteEditorWidget's debounced
auto-save) can opt in by calling WidgetExtension.register_unsaved_changes_source()
once it implements UnsavedChangesSource below, instead of a lifecycle guard
needing to know how to discover every such widget by hand.
"""
from typing import Protocol


class UnsavedChangesSource(Protocol):
    """Documented, duck-typed contract for anything flush_pending_edits()
    should commit before a project-lifecycle transition reads/acts on
    AppState.is_modified. Not runtime-checked (matches this codebase's other
    Protocol uses, e.g. WorkerFuncType) -- registering with
    UnsavedChangesRegistry is itself the conformance guarantee."""

    def has_unsaved_changes(self) -> bool: ...

    def save(self) -> bool: ...


class UnsavedChangesRegistry:
    """Tracks every currently-registered UnsavedChangesSource and flushes
    them on demand. A plain Python object (no Qt/GUI dependency) so it can
    be constructed unconditionally at app startup, unlike TabContainer which
    only exists once the GUI is built."""

    def __init__(self) -> None:
        self._sources: set[UnsavedChangesSource] = set()

    def register(self, source: UnsavedChangesSource) -> None:
        self._sources.add(source)

    def unregister(self, source: UnsavedChangesSource) -> None:
        self._sources.discard(source)

    def flush_all(self) -> bool:
        """Commit every registered source's pending edit. Returns whether
        every dirty source was actually committed -- a source whose save()
        fails (returns False or raises) is left dirty and counted as a
        failure rather than swallowed, since treating it as flushed would
        let a lifecycle guard read an unchanged is_modified and discard an
        edit that was never actually committed. Other sources are still
        attempted even if one fails."""
        all_flushed = True
        for source in list(self._sources):
            try:
                if source.has_unsaved_changes() and not source.save():
                    all_flushed = False
            except Exception:
                all_flushed = False
        return all_flushed
