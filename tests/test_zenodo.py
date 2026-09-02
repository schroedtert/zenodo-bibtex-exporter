"""Tests for the Zenodo client."""

import logging
import re
from urllib.parse import parse_qs, urlparse

import pytest
import requests
import responses
from helpers import SAMPLE_BIBTEX, record_payload

from zenodo_bibtex_exporter.exceptions import (
    ConceptNotFoundError,
    VersionNotFoundError,
    ZenodoUnavailableError,
)
from zenodo_bibtex_exporter.zenodo import BIBTEX_MEDIA_TYPE, ZenodoClient

CONCEPT_ID = "7194992"
RECORD_ID = "21476844"


@responses.activate
def test_latest_record_reads_id_concept_and_version(client: ZenodoClient, base_url: str) -> None:
    responses.get(
        f"{base_url}/records/{CONCEPT_ID}/versions/latest",
        json=record_payload(RECORD_ID, CONCEPT_ID, "v1.5.1"),
    )

    record = client.latest_record(CONCEPT_ID)

    assert record.record_id == RECORD_ID
    assert record.concept_id == CONCEPT_ID
    assert record.version == "v1.5.1"


@responses.activate
def test_latest_record_raises_for_unknown_concept(client: ZenodoClient, base_url: str) -> None:
    responses.get(f"{base_url}/records/999999999/versions/latest", status=404, json={"status": 404})

    with pytest.raises(ConceptNotFoundError, match="999999999"):
        client.latest_record("999999999")


@responses.activate
def test_a_404_is_not_retried(client: ZenodoClient, base_url: str) -> None:
    responses.get(f"{base_url}/records/999999999/versions/latest", status=404, json={"status": 404})

    with pytest.raises(ConceptNotFoundError):
        client.latest_record("999999999")

    assert len(responses.calls) == 1


@responses.activate
def test_passing_a_record_id_instead_of_a_concept_id_warns(
    client: ZenodoClient, base_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    # Zenodo answers /versions/latest for a version-specific record id too.
    responses.get(
        f"{base_url}/records/{RECORD_ID}/versions/latest",
        json=record_payload(RECORD_ID, CONCEPT_ID, "v1.5.1"),
    )

    with caplog.at_level(logging.WARNING):
        record = client.latest_record(RECORD_ID)

    assert record.concept_id == CONCEPT_ID
    assert "record id, not a concept id" in caplog.text


@responses.activate
def test_record_for_version_queries_the_metadata_version_field(client: ZenodoClient, base_url: str) -> None:
    # A bare `version:` term makes Zenodo answer HTTP 400, it must be qualified.
    responses.get(
        f"{base_url}/records",
        json={"hits": {"total": 1, "hits": [record_payload("15337052", CONCEPT_ID, "v1.3.2")]}},
    )

    record = client.record_for_version(CONCEPT_ID, "v1.3.2")

    assert record.record_id == "15337052"
    query = parse_qs(urlparse(responses.calls[0].request.url).query)
    assert query["q"] == [f'conceptrecid:{CONCEPT_ID} AND metadata.version:"v1.3.2"']
    assert query["all_versions"] == ["true"]


@responses.activate
def test_version_strings_are_matched_verbatim_not_as_semver(client: ZenodoClient, base_url: str) -> None:
    # PeTrack publishes v0.10 and CroMa; neither survives numeric normalisation.
    responses.get(
        f"{base_url}/records",
        json={"hits": {"total": 1, "hits": [record_payload("14056465", "5078176", "v0.10")]}},
    )

    client.record_for_version("5078176", "v0.10")

    query = parse_qs(urlparse(responses.calls[0].request.url).query)
    assert query["q"] == ['conceptrecid:5078176 AND metadata.version:"v0.10"']


@responses.activate
def test_unknown_version_of_a_known_concept(client: ZenodoClient, base_url: str) -> None:
    responses.get(f"{base_url}/records", json={"hits": {"total": 0, "hits": []}})
    responses.get(
        f"{base_url}/records/{CONCEPT_ID}/versions/latest",
        json=record_payload(RECORD_ID, CONCEPT_ID, "v1.5.1"),
    )

    with pytest.raises(VersionNotFoundError, match=re.escape("v9.9.9")):
        client.record_for_version(CONCEPT_ID, "v9.9.9")


@responses.activate
def test_unknown_version_of_an_unknown_concept_reports_the_concept(client: ZenodoClient, base_url: str) -> None:
    responses.get(f"{base_url}/records", json={"hits": {"total": 0, "hits": []}})
    responses.get(f"{base_url}/records/999999999/versions/latest", status=404, json={"status": 404})

    with pytest.raises(ConceptNotFoundError):
        client.record_for_version("999999999", "v1.0.0")


@responses.activate
def test_quotes_in_a_version_cannot_break_out_of_the_query(client: ZenodoClient, base_url: str) -> None:
    responses.get(f"{base_url}/records", json={"hits": {"total": 0, "hits": []}})
    responses.get(
        f"{base_url}/records/{CONCEPT_ID}/versions/latest",
        json=record_payload(RECORD_ID, CONCEPT_ID, "v1.5.1"),
    )

    with pytest.raises(VersionNotFoundError):
        client.record_for_version(CONCEPT_ID, 'v1" OR metadata.version:"v2')

    query = parse_qs(urlparse(responses.calls[0].request.url).query)
    assert query["q"] == [f'conceptrecid:{CONCEPT_ID} AND metadata.version:"v1\\" OR metadata.version:\\"v2"']


@responses.activate
def test_bibtex_requests_the_bibtex_media_type(client: ZenodoClient, base_url: str) -> None:
    responses.get(f"{base_url}/records/{RECORD_ID}", body=SAMPLE_BIBTEX)

    entry = client.bibtex(RECORD_ID)

    assert entry == SAMPLE_BIBTEX
    assert responses.calls[0].request.headers["accept"] == BIBTEX_MEDIA_TYPE


@responses.activate
def test_bibtex_ends_with_exactly_one_newline(client: ZenodoClient, base_url: str) -> None:
    responses.get(f"{base_url}/records/{RECORD_ID}", body=SAMPLE_BIBTEX + "\n\n\n")

    assert client.bibtex(RECORD_ID).endswith("}\n")


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
@responses.activate
def test_transient_failures_are_retried_then_succeed(client: ZenodoClient, base_url: str, status: int) -> None:
    url = f"{base_url}/records/{CONCEPT_ID}/versions/latest"
    responses.get(url, status=status)
    responses.get(url, json=record_payload(RECORD_ID, CONCEPT_ID, "v1.5.1"))

    record = client.latest_record(CONCEPT_ID)

    assert record.record_id == RECORD_ID
    assert len(responses.calls) == 2


@responses.activate
def test_exhausted_retries_raise_unavailable(client: ZenodoClient, base_url: str) -> None:
    url = f"{base_url}/records/{CONCEPT_ID}/versions/latest"
    for _ in range(3):
        responses.get(url, status=503)

    with pytest.raises(ZenodoUnavailableError, match="after 3 attempts"):
        client.latest_record(CONCEPT_ID)

    assert len(responses.calls) == 3


@responses.activate
def test_connection_errors_are_retried(client: ZenodoClient, base_url: str) -> None:
    url = f"{base_url}/records/{CONCEPT_ID}/versions/latest"
    responses.get(url, body=requests.exceptions.ConnectionError("boom"))
    responses.get(url, json=record_payload(RECORD_ID, CONCEPT_ID, "v1.5.1"))

    assert client.latest_record(CONCEPT_ID).record_id == RECORD_ID
    assert len(responses.calls) == 2


def test_a_token_is_sent_as_a_bearer_header() -> None:
    client = ZenodoClient(token="secret")

    assert client.session.headers["Authorization"] == "Bearer secret"


@responses.activate
def test_bibtex_raises_for_an_unknown_record(client: ZenodoClient, base_url: str) -> None:
    responses.get(f"{base_url}/records/999999999", status=404, json={"status": 404})

    with pytest.raises(ConceptNotFoundError, match="999999999"):
        client.bibtex("999999999")
