"""Normalisation of the forms a Zenodo concept id is commonly written in."""

import re
from typing import Final

from .exceptions import InvalidConceptIdError

_PATTERNS: Final = (
    # 7194992
    re.compile(r"^(?P<id>\d+)$"),
    # zenodo.7194992
    re.compile(r"^zenodo\.(?P<id>\d+)$", re.IGNORECASE),
    # 10.5281/zenodo.7194992
    re.compile(r"^10\.5281/zenodo\.(?P<id>\d+)$", re.IGNORECASE),
    # https://doi.org/10.5281/zenodo.7194992
    re.compile(
        r"^(?:https?://)?(?:dx\.)?doi\.org/10\.5281/zenodo\.(?P<id>\d+)/?$",
        re.IGNORECASE,
    ),
    # https://zenodo.org/doi/10.5281/zenodo.7194992
    re.compile(
        r"^(?:https?://)?(?:www\.)?(?:sandbox\.)?zenodo\.org/doi/10\.5281/zenodo\.(?P<id>\d+)/?$",
        re.IGNORECASE,
    ),
    # https://zenodo.org/records/7194992 and the legacy /record/ form
    re.compile(
        r"^(?:https?://)?(?:www\.)?(?:sandbox\.)?zenodo\.org/records?/(?P<id>\d+)/?$",
        re.IGNORECASE,
    ),
)


def normalize_concept_id(raw: str) -> str:
    """Extract the bare numeric Zenodo id from any of its common spellings.

    Accepts a bare id, a concept DOI, a doi.org URL, or a Zenodo record URL,
    so that whatever the user has on their clipboard tends to work.

    Args:
        raw: The concept id as the user wrote it.

    Returns:
        The bare numeric id, without any prefix.

    Raises:
        InvalidConceptIdError: If ``raw`` matches none of the known forms.
    """
    candidate = raw.strip()
    for pattern in _PATTERNS:
        match = pattern.match(candidate)
        if match is not None:
            return match["id"]

    msg = (
        f"{raw!r} is not a Zenodo concept id. Expected a number such as 7194992, "
        f"a concept DOI such as 10.5281/zenodo.7194992, or a Zenodo record URL."
    )
    raise InvalidConceptIdError(msg)
