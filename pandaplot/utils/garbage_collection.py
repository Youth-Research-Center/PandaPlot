"""Control over Python's cyclic garbage collector around Qt calls that walk every widget."""

import gc
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def paused_garbage_collection() -> Iterator[None]:
    """Keep the automatic cyclic GC from running inside the block.

    ``QApplication.setStyleSheet`` (and other calls that visit every live widget) work from a snapshot of widget
    pointers and run Python ``changeEvent`` overrides while iterating it. An automatic GC pass started inside one of
    those callbacks can free a parentless widget that is already in the snapshot, and Qt then crashes on the dangling
    pointer. Pausing the collector for the duration of the call removes that window; garbage is collected afterwards.

    GC is re-enabled on exit only if it was enabled on entry, so nesting and callers that disabled it stay correct.

    Yields:
        Nothing; use as ``with paused_garbage_collection(): ...``.
    """
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if was_enabled:
            gc.enable()
