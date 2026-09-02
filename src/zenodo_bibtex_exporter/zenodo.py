"""A small client for the parts of the Zenodo API this tool needs."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Final

import requests

from .exceptions import (
    ConceptNotFoundError,
    VersionNotFoundError,
    ZenodoUnavailableError,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL: Final = "https://zenodo.org/api"
BIBTEX_MEDIA_TYPE: Final = "application/x-bibtex"
DEFAULT_TIMEOUT: Final = 10.0
DEFAULT_RETRIES: Final = 3

#: Responses worth trying again. A 404 is a definitive answer and is never retried.
RETRYABLE_STATUS: Final = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class Record:
    """A single published version of a Zenodo record."""

    record_id: str
    concept_id: str
    version: str | None


def _escape_query_value(value: str) -> str:
    """Escape a value for safe interpolation into a quoted Lucene query term."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


class ZenodoClient:
    """Reads record metadata and BibTeX entries from Zenodo."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        backoff: float = 1.0,
        token: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        """Initialise the client.

        Args:
            base_url: Root of the Zenodo API, without a trailing slash.
            timeout: Per-request timeout in seconds.
            retries: Number of attempts for retryable failures.
            backoff: Base delay in seconds, doubled after every failed attempt.
            token: Optional Zenodo personal access token.
            session: Optional pre-built session, mainly to simplify testing.
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = max(1, retries)
        self.backoff = backoff
        self.session = session if session is not None else requests.Session()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def _get(self, path: str, *, params: dict[str, str] | None = None, accept: str | None = None) -> requests.Response:
        """Perform a GET request, retrying only failures that may be transient.

        Args:
            path: Path below the API root, starting with a slash.
            params: Optional query parameters.
            accept: Optional value for the Accept header.

        Returns:
            The successful response, or the final 404 response.

        Raises:
            ZenodoUnavailableError: If every attempt failed.
        """
        url = f"{self.base_url}{path}"
        headers = {"accept": accept} if accept else None
        last_problem = "unknown error"

        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
            except requests.RequestException as error:
                last_problem = str(error)
                logger.warning("Attempt %d/%d for %s failed: %s", attempt, self.retries, url, error)
            else:
                if response.status_code not in RETRYABLE_STATUS:
                    return response
                last_problem = f"HTTP {response.status_code}"
                logger.warning(
                    "Attempt %d/%d for %s returned HTTP %d",
                    attempt,
                    self.retries,
                    url,
                    response.status_code,
                )

            if attempt < self.retries:
                time.sleep(self.backoff * (2 ** (attempt - 1)))

        msg = f"Could not reach Zenodo at {url} after {self.retries} attempts: {last_problem}"
        raise ZenodoUnavailableError(msg)

    def _to_record(self, payload: dict[str, Any]) -> Record:
        """Build a :class:`Record` from a Zenodo record payload."""
        return Record(
            record_id=str(payload["id"]),
            concept_id=str(payload.get("conceptrecid", "")),
            version=payload.get("metadata", {}).get("version"),
        )

    def latest_record(self, concept_id: str) -> Record:
        """Look up the most recent published version of a concept.

        Args:
            concept_id: Bare numeric concept id.

        Returns:
            The latest version of that concept.

        Raises:
            ConceptNotFoundError: If Zenodo knows no such id.
        """
        response = self._get(f"/records/{concept_id}/versions/latest")
        if response.status_code == HTTPStatus.NOT_FOUND:
            msg = f"Zenodo has no record for concept id {concept_id}."
            raise ConceptNotFoundError(msg)
        response.raise_for_status()

        record = self._to_record(response.json())
        if record.concept_id and record.concept_id != concept_id:
            # /versions/latest accepts a version-specific record id too, and
            # silently answers with the latest version of its concept.
            logger.warning(
                "%s is a record id, not a concept id; returning the latest version of concept %s instead.",
                concept_id,
                record.concept_id,
            )
        return record

    def record_for_version(self, concept_id: str, version: str) -> Record:
        """Look up one specific version of a concept, matched exactly.

        The version string is compared verbatim. Zenodo's version field is free
        text, so it is never parsed as a semantic version.

        Args:
            concept_id: Bare numeric concept id.
            version: Version string as published on Zenodo, for example ``v1.3.2``.

        Returns:
            The matching version of that concept.

        Raises:
            ConceptNotFoundError: If Zenodo knows no such concept id.
            VersionNotFoundError: If the concept has no such version.
        """
        query = f'conceptrecid:{concept_id} AND metadata.version:"{_escape_query_value(version)}"'
        response = self._get("/records", params={"q": query, "all_versions": "true"})
        response.raise_for_status()

        hits = response.json().get("hits", {}).get("hits", [])
        if hits:
            return self._to_record(hits[0])

        # An unknown concept and an unknown version both come back as zero hits,
        # so ask whether the concept exists at all to tell the two apart.
        self.latest_record(concept_id)
        msg = f"Concept {concept_id} has no version {version!r} on Zenodo."
        raise VersionNotFoundError(msg)

    def bibtex(self, record_id: str) -> str:
        """Fetch the BibTeX entry Zenodo renders for a record.

        Args:
            record_id: Id of a specific published version.

        Returns:
            The BibTeX entry, with a single trailing newline.

        Raises:
            ConceptNotFoundError: If Zenodo has no such record.
        """
        response = self._get(f"/records/{record_id}", accept=BIBTEX_MEDIA_TYPE)
        if response.status_code == HTTPStatus.NOT_FOUND:
            msg = f"Zenodo has no record {record_id}."
            raise ConceptNotFoundError(msg)
        response.raise_for_status()

        response.encoding = "utf-8"
        return response.text.strip() + "\n"
