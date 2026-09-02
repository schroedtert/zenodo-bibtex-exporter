"""Errors raised by this package.

Every error carries the process exit code the CLI reports for it, so that
callers in CI can distinguish a typo in the arguments from Zenodo being
temporarily unreachable.
"""


class ZenodoBibtexError(Exception):
    """Base class for every error raised by this package."""

    exit_code = 1


class InvalidConceptIdError(ZenodoBibtexError):
    """The given concept id is not in any recognised form."""

    exit_code = 2


class ConceptNotFoundError(ZenodoBibtexError):
    """Zenodo has no record for the given concept id."""

    exit_code = 3


class VersionNotFoundError(ZenodoBibtexError):
    """The concept exists on Zenodo, but not in the requested version."""

    exit_code = 4


class ZenodoUnavailableError(ZenodoBibtexError):
    """Zenodo could not be reached, or kept answering with server errors."""

    exit_code = 5
