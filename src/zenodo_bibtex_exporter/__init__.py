"""Export BibTeX citation information from Zenodo records."""

from importlib.metadata import PackageNotFoundError as _PackageNotFoundError
from importlib.metadata import version as _distribution_version

from .api import get_bibtex, resolve
from .exceptions import (
    ConceptNotFoundError,
    InvalidConceptIdError,
    VersionNotFoundError,
    ZenodoBibtexError,
    ZenodoUnavailableError,
)
from .zenodo import Record, ZenodoClient

try:
    __version__ = _distribution_version("zenodo-bibtex-exporter")
except _PackageNotFoundError:  # pragma: no cover - only hit when running from a source tree
    __version__ = "0.0.0"

__all__ = [
    "ConceptNotFoundError",
    "InvalidConceptIdError",
    "Record",
    "VersionNotFoundError",
    "ZenodoBibtexError",
    "ZenodoClient",
    "ZenodoUnavailableError",
    "__version__",
    "get_bibtex",
    "resolve",
]
