"""Tests for concept id normalisation."""

import pytest

from zenodo_bibtex_exporter.exceptions import InvalidConceptIdError
from zenodo_bibtex_exporter.identifiers import normalize_concept_id


@pytest.mark.parametrize(
    "raw",
    [
        "7194992",
        "  7194992  ",
        "zenodo.7194992",
        "10.5281/zenodo.7194992",
        "https://doi.org/10.5281/zenodo.7194992",
        "http://doi.org/10.5281/zenodo.7194992",
        "doi.org/10.5281/zenodo.7194992",
        "https://dx.doi.org/10.5281/zenodo.7194992",
        "https://zenodo.org/doi/10.5281/zenodo.7194992",
        "https://zenodo.org/records/7194992",
        "https://zenodo.org/record/7194992",
        "https://zenodo.org/records/7194992/",
        "https://www.zenodo.org/records/7194992",
        "https://sandbox.zenodo.org/records/7194992",
        "zenodo.org/records/7194992",
    ],
)
def test_accepted_forms_all_normalize_to_the_bare_id(raw: str) -> None:
    assert normalize_concept_id(raw) == "7194992"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "PedPy",
        "v1.3.2",
        "10.1234/not-zenodo.7194992",
        "https://example.org/records/7194992",
        "https://zenodo.org/communities/pedpy",
        "7194992abc",
        "-7194992",
    ],
)
def test_unrecognised_forms_are_rejected(raw: str) -> None:
    with pytest.raises(InvalidConceptIdError):
        normalize_concept_id(raw)


def test_error_message_names_the_offending_input() -> None:
    with pytest.raises(InvalidConceptIdError, match="PedPy"):
        normalize_concept_id("PedPy")
