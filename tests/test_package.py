"""Tests for the package metadata."""

import zenodo_bibtex_exporter


def test_package_exposes_a_version() -> None:
    assert isinstance(zenodo_bibtex_exporter.__version__, str)
    assert zenodo_bibtex_exporter.__version__
