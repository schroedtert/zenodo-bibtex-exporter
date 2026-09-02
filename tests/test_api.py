"""Tests for the importable API."""

import pytest
import responses
from helpers import SAMPLE_BIBTEX, record_payload

import zenodo_bibtex_exporter
from zenodo_bibtex_exporter import (
    ConceptNotFoundError,
    InvalidConceptIdError,
    Record,
    VersionNotFoundError,
    ZenodoBibtexError,
    ZenodoClient,
    get_bibtex,
    resolve,
)
from zenodo_bibtex_exporter.zenodo import DEFAULT_BASE_URL

CONCEPT_ID = "7194992"
RECORD_ID = "21476844"

pytestmark = pytest.mark.usefixtures("no_sleep")


def _mock_latest() -> None:
    responses.get(
        f"{DEFAULT_BASE_URL}/records/{CONCEPT_ID}/versions/latest",
        json=record_payload(RECORD_ID, CONCEPT_ID, "v1.5.1"),
    )
    responses.get(f"{DEFAULT_BASE_URL}/records/{RECORD_ID}", body=SAMPLE_BIBTEX)


@responses.activate
def test_get_bibtex_defaults_to_the_latest_version() -> None:
    _mock_latest()

    assert get_bibtex(CONCEPT_ID) == SAMPLE_BIBTEX


@responses.activate
def test_get_bibtex_for_an_exact_version() -> None:
    responses.get(
        f"{DEFAULT_BASE_URL}/records",
        json={"hits": {"total": 1, "hits": [record_payload("15337052", CONCEPT_ID, "v1.3.2")]}},
    )
    responses.get(f"{DEFAULT_BASE_URL}/records/15337052", body=SAMPLE_BIBTEX)

    assert get_bibtex(CONCEPT_ID, version="v1.3.2") == SAMPLE_BIBTEX


@responses.activate
def test_resolve_returns_the_record_metadata() -> None:
    _mock_latest()

    record = resolve(CONCEPT_ID)

    assert isinstance(record, Record)
    assert record == Record(record_id=RECORD_ID, concept_id=CONCEPT_ID, version="v1.5.1")


@pytest.mark.parametrize(
    "raw",
    ["7194992", "10.5281/zenodo.7194992", "https://zenodo.org/records/7194992"],
)
@responses.activate
def test_the_same_id_spellings_as_the_cli_are_accepted(raw: str) -> None:
    _mock_latest()

    assert resolve(raw).record_id == RECORD_ID


def test_an_unparseable_id_raises_before_any_request() -> None:
    with pytest.raises(InvalidConceptIdError):
        resolve("PedPy")


@responses.activate
def test_an_unknown_concept_raises() -> None:
    responses.get(f"{DEFAULT_BASE_URL}/records/999999999/versions/latest", status=404, json={"status": 404})

    with pytest.raises(ConceptNotFoundError):
        get_bibtex("999999999")


@responses.activate
def test_an_unknown_version_raises() -> None:
    responses.get(f"{DEFAULT_BASE_URL}/records", json={"hits": {"total": 0, "hits": []}})
    responses.get(
        f"{DEFAULT_BASE_URL}/records/{CONCEPT_ID}/versions/latest",
        json=record_payload(RECORD_ID, CONCEPT_ID, "v1.5.1"),
    )

    with pytest.raises(VersionNotFoundError):
        get_bibtex(CONCEPT_ID, version="v9.9.9")


@responses.activate
def test_every_failure_is_catchable_as_one_base_class() -> None:
    # This is the pattern a docs build uses to degrade instead of failing.
    responses.get(f"{DEFAULT_BASE_URL}/records/999999999/versions/latest", status=404, json={"status": 404})

    try:
        entry = get_bibtex("999999999")
    except ZenodoBibtexError:
        entry = "fallback"

    assert entry == "fallback"


@responses.activate
def test_an_injected_client_takes_precedence_over_the_options() -> None:
    _mock_latest()
    client = ZenodoClient(token="secret")

    get_bibtex(CONCEPT_ID, client=client, token="ignored")

    assert responses.calls[0].request.headers["Authorization"] == "Bearer secret"


@responses.activate
def test_options_are_passed_through_to_the_client() -> None:
    responses.get(
        "https://example.test/api/records/7194992/versions/latest",
        json=record_payload(RECORD_ID, CONCEPT_ID, "v1.5.1"),
    )
    responses.get("https://example.test/api/records/21476844", body=SAMPLE_BIBTEX)

    assert get_bibtex(CONCEPT_ID, base_url="https://example.test/api", token="secret") == SAMPLE_BIBTEX
    assert responses.calls[0].request.headers["Authorization"] == "Bearer secret"


def test_the_public_surface_is_what_all_advertises() -> None:
    for name in zenodo_bibtex_exporter.__all__:
        assert hasattr(zenodo_bibtex_exporter, name), name


def test_importlib_helpers_do_not_leak_into_the_namespace() -> None:
    public = {name for name in dir(zenodo_bibtex_exporter) if not name.startswith("_")}

    assert "version" not in public
    assert "PackageNotFoundError" not in public
