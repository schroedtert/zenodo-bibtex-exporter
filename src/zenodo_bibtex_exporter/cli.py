"""Command line interface.

The BibTeX entry is the only thing written to stdout. Every diagnostic goes to
stderr, so that the output can be redirected straight into a file or a pipe from
a CI job.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import TYPE_CHECKING

from . import __version__
from .exceptions import ZenodoBibtexError
from .identifiers import normalize_concept_id
from .zenodo import DEFAULT_BASE_URL, Record, ZenodoClient

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

_EPILOG = """\
exit codes:
  0  success
  2  usage error, or an unrecognised concept id
  3  no such concept id on Zenodo
  4  the concept has no such version
  5  Zenodo unreachable after all retries
  1  unexpected error

examples:
  zenodo-bibtex 7194992 --latest
  zenodo-bibtex 10.5281/zenodo.7194992 --version v1.3.2
  zenodo-bibtex https://zenodo.org/records/7194992 --latest > CITATION.bib
"""


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="zenodo-bibtex",
        description="Print the BibTeX entry of a Zenodo record.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "concept_id",
        metavar="CONCEPT_ID",
        help="Zenodo concept id, concept DOI, or record URL.",
    )

    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--latest",
        action="store_true",
        help="Use the most recent published version.",
    )
    selection.add_argument(
        "--version",
        metavar="VERSION",
        help="Use this exact version, as published on Zenodo, for example v1.3.2.",
    )

    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Root of the Zenodo API (default: {DEFAULT_BASE_URL}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-request timeout in seconds (default: 10).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Attempts for retryable failures (default: 3).",
    )

    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Log more on stderr; repeat for debug output.",
    )
    verbosity.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Log only errors on stderr.",
    )

    parser.add_argument(
        "--tool-version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show the version of this tool and exit.",
    )
    return parser


def _write_entry(entry: str) -> None:
    """Write the entry to stdout as UTF-8, whatever the ambient locale is.

    Redirecting stdout gives a stream encoded with the platform's preferred
    encoding, which on Windows is the ANSI code page. That cannot represent
    every author name Zenodo serves, and the write then fails outright rather
    than degrading. Writing bytes keeps the output byte identical everywhere,
    which is also what a .bib file is expected to be.
    """
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        # A replaced stream, such as the one pytest's capsys installs.
        sys.stdout.write(entry)
        return

    sys.stdout.flush()
    buffer.write(entry.encode("utf-8"))
    buffer.flush()


def _configure_logging(*, verbose: int, quiet: bool) -> None:
    """Send logging to stderr, keeping stdout free for the BibTeX entry."""
    if quiet:
        level = logging.ERROR
    elif verbose >= 2:  # noqa: PLR2004
        level = logging.DEBUG
    elif verbose == 1:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        stream=sys.stderr,
        format="%(levelname)s: %(message)s",
        force=True,
    )


def _resolve(client: ZenodoClient, concept_id: str, version: str | None) -> Record:
    """Resolve the requested version to a single Zenodo record."""
    if version is None:
        return client.latest_record(concept_id)
    return client.record_for_version(concept_id, version)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line interface.

    Args:
        argv: Arguments to parse, defaulting to ``sys.argv[1:]``.

    Returns:
        The process exit code.
    """
    args = build_parser().parse_args(argv)
    _configure_logging(verbose=args.verbose, quiet=args.quiet)

    try:
        concept_id = normalize_concept_id(args.concept_id)
        client = ZenodoClient(
            base_url=args.base_url,
            timeout=args.timeout,
            retries=args.retries,
            token=os.environ.get("ZENODO_TOKEN"),
        )
        record = _resolve(client, concept_id, args.version)
        logger.info("Resolved concept %s to record %s (version %s).", concept_id, record.record_id, record.version)
        entry = client.bibtex(record.record_id)
    except ZenodoBibtexError as error:
        logger.error("%s", error)
        return error.exit_code
    except Exception:
        logger.exception("Unexpected error.")
        return 1

    _write_entry(entry)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
