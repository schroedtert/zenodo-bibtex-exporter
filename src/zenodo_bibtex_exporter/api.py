"""The importable interface of this package.

These functions are the counterpart of the command line interface, for callers
that are already running Python. They raise on failure rather than returning a
placeholder, so a caller can tell a lookup failure from a genuine result. A
documentation build that would rather degrade than fail should catch
:class:`~zenodo_bibtex_exporter.exceptions.ZenodoBibtexError` and substitute its
own fallback text.

Nothing here configures logging or writes to a stream; that is left to the
caller.
"""

from __future__ import annotations

from .identifiers import normalize_concept_id
from .zenodo import (
    DEFAULT_BASE_URL,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    Record,
    ZenodoClient,
)


def _client(
    base_url: str,
    timeout: float,
    retries: int,
    token: str | None,
    client: ZenodoClient | None,
) -> ZenodoClient:
    """Return the caller's client, or build one from the given options."""
    if client is not None:
        return client
    return ZenodoClient(base_url=base_url, timeout=timeout, retries=retries, token=token)


def resolve(
    concept_id: str,
    *,
    version: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    token: str | None = None,
    client: ZenodoClient | None = None,
) -> Record:
    """Resolve a concept id to one specific published record.

    Args:
        concept_id: Concept id, concept DOI, or Zenodo record URL.
        version: Exact version string as published on Zenodo, for example
            ``v1.3.2``. Matched verbatim. Defaults to the latest version.
        base_url: Root of the Zenodo API.
        timeout: Per-request timeout in seconds.
        retries: Attempts for retryable failures.
        token: Optional Zenodo personal access token.
        client: A pre-built client, which takes precedence over the options above.

    Returns:
        The matching record.

    Raises:
        InvalidConceptIdError: If ``concept_id`` is in no recognised form.
        ConceptNotFoundError: If Zenodo knows no such concept.
        VersionNotFoundError: If the concept has no such version.
        ZenodoUnavailableError: If Zenodo could not be reached.
    """
    zenodo = _client(base_url, timeout, retries, token, client)
    normalized = normalize_concept_id(concept_id)
    if version is None:
        return zenodo.latest_record(normalized)
    return zenodo.record_for_version(normalized, version)


def get_bibtex(
    concept_id: str,
    *,
    version: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    token: str | None = None,
    client: ZenodoClient | None = None,
) -> str:
    """Fetch the BibTeX entry of a Zenodo record.

    Args:
        concept_id: Concept id, concept DOI, or Zenodo record URL.
        version: Exact version string as published on Zenodo. Matched verbatim.
            Defaults to the latest version.
        base_url: Root of the Zenodo API.
        timeout: Per-request timeout in seconds.
        retries: Attempts for retryable failures.
        token: Optional Zenodo personal access token.
        client: A pre-built client, which takes precedence over the options above.

    Returns:
        The BibTeX entry, with a single trailing newline.

    Raises:
        InvalidConceptIdError: If ``concept_id`` is in no recognised form.
        ConceptNotFoundError: If Zenodo knows no such concept.
        VersionNotFoundError: If the concept has no such version.
        ZenodoUnavailableError: If Zenodo could not be reached.
    """
    zenodo = _client(base_url, timeout, retries, token, client)
    record = resolve(concept_id, version=version, client=zenodo)
    return zenodo.bibtex(record.record_id)
