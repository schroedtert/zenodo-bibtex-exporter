"""Contract tests against the live Zenodo API.

These are the only tests that can catch Zenodo changing its API underneath us.
Everything else in the suite is mocked, so a schema or format change would pass
CI and fail in users' hands. They are marked ``network`` and deselected by
default; CI runs them on the weekly schedule.

Two kinds of assertion live here, and the distinction matters:

* Pinned versions are immutable enough to assert on exactly. They are asserted
  on stable identifiers only, not byte-for-byte, because Zenodo lets record
  metadata be edited after publication.
* The latest version of anything changes whenever one of these projects makes a
  release, so it is only checked for shape. Asserting its content would turn
  this suite red every time somebody does their job.
"""

import re

import pytest
import requests

from zenodo_bibtex_exporter import (
    ConceptNotFoundError,
    VersionNotFoundError,
    get_bibtex,
    resolve,
)
from zenodo_bibtex_exporter.cli import main
from zenodo_bibtex_exporter.zenodo import DEFAULT_BASE_URL

pytestmark = pytest.mark.network

RAW_TIMEOUT = 30

PEDPY = "7194992"
JUPEDSIM = "1293771"
PETRACK = "5078176"

ALL_CONCEPTS = [
    pytest.param(PEDPY, id="pedpy"),
    pytest.param(JUPEDSIM, id="jupedsim"),
    pytest.param(PETRACK, id="petrack"),
]

# concept id, version, expected record id. Published releases, so these do not move.
PINNED = [
    pytest.param(PEDPY, "v1.3.2", "15337052", id="pedpy-v1.3.2"),
    pytest.param(JUPEDSIM, "v0.9.0", "6223495", id="jupedsim-v0.9.0"),
    # v0.10 would collide with v0.1 under any numeric normalisation.
    pytest.param(PETRACK, "v0.10", "14056465", id="petrack-v0.10"),
]


def field(entry: str, name: str) -> str:
    """Read one field out of a BibTeX entry.

    Zenodo braces most values but renders month and year bare, so both spellings
    have to be understood. Braced values may span lines, as author does.
    """
    braced = re.search(rf"^\s*{name}\s*=\s*\{{(.*?)\}},?\s*$", entry, re.MULTILINE | re.DOTALL)
    if braced is not None:
        return " ".join(braced.group(1).split())

    bare = re.search(rf"^\s*{name}\s*=\s*([^{{,\n]+?),?\s*$", entry, re.MULTILINE)
    assert bare is not None, f"no {name} field in:\n{entry}"
    return bare.group(1).strip()


@pytest.mark.parametrize(("concept_id", "version", "record_id"), PINNED)
def test_a_pinned_version_resolves_to_its_record(concept_id: str, version: str, record_id: str) -> None:
    record = resolve(concept_id, version=version)

    assert record.record_id == record_id
    assert record.concept_id == concept_id
    assert record.version == version


@pytest.mark.parametrize(("concept_id", "version", "record_id"), PINNED)
def test_a_pinned_version_renders_the_expected_bibtex(concept_id: str, version: str, record_id: str) -> None:
    entry = get_bibtex(concept_id, version=version)

    assert entry.startswith("@software{")
    assert entry.endswith("}\n")
    assert field(entry, "doi") == f"10.5281/zenodo.{record_id}"
    assert field(entry, "version") == version
    assert field(entry, "url").endswith(record_id)


@pytest.mark.parametrize("concept_id", ALL_CONCEPTS)
def test_the_latest_version_has_the_expected_shape(concept_id: str) -> None:
    # Deliberately no assertion on the content: it changes with every release.
    record = resolve(concept_id)
    entry = get_bibtex(concept_id)

    assert record.concept_id == concept_id
    assert record.record_id
    assert record.version
    assert entry.startswith("@")
    assert field(entry, "doi") == f"10.5281/zenodo.{record.record_id}"
    assert field(entry, "version") == record.version
    assert field(entry, "year").isdigit()
    assert field(entry, "author")


@pytest.mark.parametrize("concept_id", ALL_CONCEPTS)
def test_a_concept_lookup_never_returns_a_foreign_record(concept_id: str) -> None:
    """A free-text search for a project name can return somebody else's record.

    That is what a name search does to PeTrack, whose top text match is an
    unrelated paper by an author of that surname. A concept id cannot do this,
    and this test is what proves it stays true.
    """
    record = resolve(concept_id)

    assert record.concept_id == concept_id


@pytest.mark.parametrize("concept_id", ALL_CONCEPTS)
def test_bibtex_is_utf8_and_not_mojibake(concept_id: str) -> None:
    entry = get_bibtex(concept_id)

    assert "Ã" not in entry, "response was decoded as latin-1 somewhere"


def test_an_older_version_outside_the_first_search_page_is_reachable() -> None:
    """JuPedSim has more versions than one anonymous search page returns.

    Its own script reads a single page and silently reports no citation for
    anything past the cap. Concept id lookup filters server side instead.
    """
    record = resolve(JUPEDSIM, version="v0.9.0")

    assert record.record_id == "6223495"


def test_an_unknown_concept_is_reported_as_such() -> None:
    with pytest.raises(ConceptNotFoundError):
        resolve("999999999")


def test_an_unknown_version_of_a_real_concept_is_reported_as_such() -> None:
    with pytest.raises(VersionNotFoundError):
        resolve(PEDPY, version="v0.0.0-nope")


def test_a_development_version_fails_the_way_a_docs_build_expects() -> None:
    # Between releases every project's __version__ looks like this.
    with pytest.raises(VersionNotFoundError):
        get_bibtex(PEDPY, version="v1.5.2.dev3+g1234567")


@pytest.mark.parametrize(
    "raw",
    [
        PEDPY,
        f"10.5281/zenodo.{PEDPY}",
        f"https://doi.org/10.5281/zenodo.{PEDPY}",
        f"https://zenodo.org/records/{PEDPY}",
    ],
)
def test_every_accepted_id_spelling_works_against_the_real_api(raw: str) -> None:
    assert resolve(raw, version="v1.3.2").record_id == "15337052"


def test_the_cli_prints_only_the_entry(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([PETRACK, "--version", "v0.10", "-vv"]) == 0

    captured = capsys.readouterr()
    assert captured.out.startswith("@software{")
    assert captured.out.endswith("}\n")
    assert "14056465" in captured.out
    assert captured.err, "verbose logging should have gone to stderr"


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["999999999", "--latest"], 3),
        ([PEDPY, "--version", "v0.0.0-nope"], 4),
    ],
)
def test_the_cli_exit_codes_hold_against_the_real_api(argv: list[str], expected: int) -> None:
    assert main(argv) == expected


def test_the_record_payload_still_has_the_fields_we_read() -> None:
    """Name the field that changed, rather than leaving it to be inferred.

    Every other contract test breaks too if Zenodo renames one of these, but
    only indirectly: a missing conceptrecid surfaces as a concept id that does
    not match, which says nothing about the cause. This asserts on the raw
    payload, before any of our own parsing touches it.
    """
    payload = requests.get(f"{DEFAULT_BASE_URL}/records/{PEDPY}/versions/latest", timeout=RAW_TIMEOUT).json()

    assert isinstance(payload["id"], int)
    assert isinstance(payload["conceptrecid"], str)
    assert isinstance(payload["metadata"]["version"], str)


def test_the_search_payload_still_has_the_fields_we_read() -> None:
    """The search endpoint returns a different shape from the record endpoint."""
    payload = requests.get(
        f"{DEFAULT_BASE_URL}/records",
        params={"q": f'conceptrecid:{PEDPY} AND metadata.version:"v1.3.2"', "all_versions": "true"},
        timeout=RAW_TIMEOUT,
    ).json()

    hits = payload["hits"]["hits"]
    assert len(hits) == 1
    assert isinstance(hits[0]["id"], int)
    assert hits[0]["metadata"]["version"] == "v1.3.2"
