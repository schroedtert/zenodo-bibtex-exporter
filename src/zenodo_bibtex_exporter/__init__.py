"""Export BibTeX citation information from Zenodo records."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("zenodo-bibtex-exporter")
except PackageNotFoundError:  # pragma: no cover - only hit when running from a source tree
    __version__ = "0.0.0"

__all__ = ["__version__"]
