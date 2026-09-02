"""Tests for the command line interface.

The load-bearing property here is that stdout carries the BibTeX entry and
nothing else, whatever the verbosity.
"""

import io
import subprocess
import sys

import pytest
import responses
from helpers import SAMPLE_BIBTEX, record_payload

from zenodo_bibtex_exporter.cli import _write_entry, main
from zenodo_bibtex_exporter.zenodo import DEFAULT_BASE_URL

CONCEPT_ID = "7194992"
RECORD_ID = "21476844"

pytestmark = pytest.mark.usefixtures("no_sleep")


def _mock_latest(version: str = "v1.5.1") -> None:
    responses.get(
        f"{DEFAULT_BASE_URL}/records/{CONCEPT_ID}/versions/latest",
        json=record_payload(RECORD_ID, CONCEPT_ID, version),
    )
    responses.get(f"{DEFAULT_BASE_URL}/records/{RECORD_ID}", body=SAMPLE_BIBTEX)


@responses.activate
def test_latest_writes_the_entry_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    _mock_latest()

    assert main([CONCEPT_ID, "--latest"]) == 0

    captured = capsys.readouterr()
    assert captured.out == SAMPLE_BIBTEX
    assert captured.err == ""


@pytest.mark.parametrize("flags", [[], ["-q"], ["-v"], ["-vv"]])
@responses.activate
def test_stdout_stays_clean_at_every_verbosity(capsys: pytest.CaptureFixture[str], flags: list[str]) -> None:
    _mock_latest()

    assert main([CONCEPT_ID, "--latest", *flags]) == 0

    assert capsys.readouterr().out == SAMPLE_BIBTEX


@responses.activate
def test_verbose_logging_goes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    _mock_latest()

    main([CONCEPT_ID, "--latest", "-v"])

    captured = capsys.readouterr()
    assert captured.out == SAMPLE_BIBTEX
    assert "Resolved concept" in captured.err


@responses.activate
def test_a_specific_version_is_looked_up_verbatim(capsys: pytest.CaptureFixture[str]) -> None:
    responses.get(
        f"{DEFAULT_BASE_URL}/records",
        json={"hits": {"total": 1, "hits": [record_payload("14056465", "5078176", "v0.10")]}},
    )
    responses.get(f"{DEFAULT_BASE_URL}/records/14056465", body=SAMPLE_BIBTEX)

    assert main(["5078176", "--version", "v0.10"]) == 0

    assert capsys.readouterr().out == SAMPLE_BIBTEX
    assert "metadata.version%3A%22v0.10%22" in responses.calls[0].request.url


@pytest.mark.parametrize(
    "raw",
    ["7194992", "10.5281/zenodo.7194992", "https://zenodo.org/records/7194992"],
)
@responses.activate
def test_concept_id_spellings_are_accepted(capsys: pytest.CaptureFixture[str], raw: str) -> None:
    _mock_latest()

    assert main([raw, "--latest"]) == 0
    assert capsys.readouterr().out == SAMPLE_BIBTEX


@responses.activate
def test_unrecognised_concept_id_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["PedPy", "--latest"]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "PedPy" in captured.err


@responses.activate
def test_unknown_concept_exits_3(capsys: pytest.CaptureFixture[str]) -> None:
    responses.get(f"{DEFAULT_BASE_URL}/records/999999999/versions/latest", status=404, json={"status": 404})

    assert main(["999999999", "--latest"]) == 3
    assert capsys.readouterr().out == ""


@responses.activate
def test_unknown_version_exits_4(capsys: pytest.CaptureFixture[str]) -> None:
    responses.get(f"{DEFAULT_BASE_URL}/records", json={"hits": {"total": 0, "hits": []}})
    responses.get(
        f"{DEFAULT_BASE_URL}/records/{CONCEPT_ID}/versions/latest",
        json=record_payload(RECORD_ID, CONCEPT_ID, "v1.5.1"),
    )

    assert main([CONCEPT_ID, "--version", "v9.9.9"]) == 4
    assert capsys.readouterr().out == ""


@responses.activate
def test_unreachable_zenodo_exits_5(capsys: pytest.CaptureFixture[str]) -> None:
    for _ in range(2):
        responses.get(f"{DEFAULT_BASE_URL}/records/{CONCEPT_ID}/versions/latest", status=503)

    assert main([CONCEPT_ID, "--latest", "--retries", "2"]) == 5
    assert capsys.readouterr().out == ""


@responses.activate
def test_unexpected_errors_exit_1(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr("zenodo_bibtex_exporter.cli.resolve", boom)

    assert main([CONCEPT_ID, "--latest"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Unexpected error" in captured.err


@responses.activate
def test_the_record_id_warning_goes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    responses.get(
        f"{DEFAULT_BASE_URL}/records/{RECORD_ID}/versions/latest",
        json=record_payload(RECORD_ID, CONCEPT_ID, "v1.5.1"),
    )
    responses.get(f"{DEFAULT_BASE_URL}/records/{RECORD_ID}", body=SAMPLE_BIBTEX)

    assert main([RECORD_ID, "--latest"]) == 0

    captured = capsys.readouterr()
    assert captured.out == SAMPLE_BIBTEX
    assert "record id, not a concept id" in captured.err


@responses.activate
def test_a_zenodo_token_from_the_environment_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZENODO_TOKEN", "secret")
    _mock_latest()

    main([CONCEPT_ID, "--latest"])

    assert responses.calls[0].request.headers["Authorization"] == "Bearer secret"


@pytest.mark.parametrize(
    "argv",
    [
        [CONCEPT_ID],
        [CONCEPT_ID, "--latest", "--version", "v1.0"],
        [CONCEPT_ID, "--latest", "-q", "-v"],
        [],
    ],
)
def test_usage_errors_exit_2(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(argv)

    assert excinfo.value.code == 2


def test_tool_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--tool-version"])

    assert excinfo.value.code == 0
    assert "zenodo-bibtex" in capsys.readouterr().out


def test_help_documents_the_exit_codes(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])

    assert "exit codes:" in capsys.readouterr().out


def test_the_module_is_runnable_with_dash_m() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "zenodo_bibtex_exporter", "--tool-version"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "zenodo-bibtex" in result.stdout


@pytest.mark.parametrize("encoding", ["ascii", "cp1252", "utf-8"])
def test_the_entry_survives_a_stdout_that_cannot_encode_it(monkeypatch: pytest.MonkeyPatch, encoding: str) -> None:
    # Redirecting stdout on Windows yields an ANSI code page stream. Author
    # names outside it must not turn a successful lookup into a crash.
    entry = "@software{x_2026_1,\n  author = {Zaïd, Łukasz and 山田, 太郎},\n}\n"
    raw = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(raw, encoding=encoding, newline=""))

    _write_entry(entry)

    assert raw.getvalue().decode("utf-8") == entry


def test_a_stdout_without_a_buffer_still_receives_the_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    # Some hosts replace stdout with a text only stream, IPython among them.
    entry = "@software{x_2026_1,\n}\n"
    replaced = io.StringIO()
    assert not hasattr(replaced, "buffer")
    monkeypatch.setattr(sys, "stdout", replaced)

    _write_entry(entry)

    assert replaced.getvalue() == entry
