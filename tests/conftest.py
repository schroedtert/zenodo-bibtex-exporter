"""Shared fixtures."""

import pytest

from zenodo_bibtex_exporter.zenodo import DEFAULT_BASE_URL, ZenodoClient


@pytest.fixture
def base_url() -> str:
    return DEFAULT_BASE_URL


@pytest.fixture
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make retry backoff instant, so retry tests stay fast."""
    monkeypatch.setattr("zenodo_bibtex_exporter.zenodo.time.sleep", lambda _seconds: None)


@pytest.fixture
def client(no_sleep: None) -> ZenodoClient:
    """A client with backoff disabled."""
    return ZenodoClient(retries=3, backoff=0.0)
