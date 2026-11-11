"""Exception types shared across PandaPlot."""


class UserFacingError(ValueError):
    """An error whose message is written for the user and can be shown as is.

    Raise this (instead of a plain ``ValueError``) when the message is a complete sentence a
    user can act on, such as "Sampling rate must be greater than zero.". Never embed library
    exception text in the message; write the sentence and chain the original with ``from e``.
    Internal or programmer-invariant checks stay plain ``ValueError``.

    It subclasses ``ValueError`` so existing ``except ValueError`` handlers and
    ``pytest.raises(ValueError)`` keep working.
    """
