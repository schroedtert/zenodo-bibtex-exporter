# zenodo-bibtex-exporter

Print the BibTeX citation entry of a Zenodo record, from the command line or
from Python.

Give it the **concept id** of a project — the id that stays the same across all
releases — and it returns the BibTeX entry for either the latest version or one
specific version. The entry is the only thing written to stdout, so the output
can be redirected straight into a file from a CI job.

```console
$ zenodo-bibtex 1234567 --latest
@software{doe_2026_7654321,
  author       = {Doe, Jane and
                  The Example Development Team},
  title        = {Example Software},
  month        = jul,
  year         = 2026,
  publisher    = {Zenodo},
  version      = {v2.1.0},
  doi          = {10.5281/zenodo.7654321},
  url          = {https://doi.org/10.5281/zenodo.7654321},
}
```

## Why a concept id

Zenodo gives every project two kinds of identifier. A **record id** points at
one specific published version and changes with every release. A **concept id**
points at the project as a whole and never changes. This tool takes the concept
id, and resolves it to a record itself.

The obvious alternative is to search Zenodo for the project's name. That is
unreliable in two ways, and both fail quietly.

**A name is not an identifier.** Full text search matches titles, descriptions,
keywords and author names, so any record that merely mentions the project can
outrank the project itself. A short or common name makes this likely, and a name
that is also an ordinary word or a person's surname makes it near certain. The
result is a citation for somebody else's work, rendered without any error.

**Search results are paged.** A search returns one page, and Zenodo caps the
page size at 25 records for unauthenticated requests. A project with more
releases than fit on that page loses the oldest ones from the results, so
looking up an older version reports that it does not exist. The problem grows
with every release, and appears long after the code that causes it was written.

A concept id has neither problem. It is an exact identifier, so it cannot match
a name, and the lookup filters on it server side, so there is nothing to page
through.

### Finding the concept id

It is the number in the project's *concept DOI* — the DOI that always resolves
to the newest version, usually the one advertised in a project's README or
citation file. A concept DOI of `10.5281/zenodo.1234567` means the concept id is
`1234567`.

You can also pass the DOI or a Zenodo URL directly, and let the tool extract it.

## Install

```console
python3 -m pip install zenodo-bibtex-exporter
```

To install the latest development version from the repository:

```console
python3 -m pip install --force-reinstall git+https://github.com/schroedtert/zenodo-bibtex-exporter.git
```

> [!IMPORTANT]
> The latest repository version may be unstable. Use with caution.

To run it without installing anything permanently:

```console
uvx zenodo-bibtex 1234567 --latest
```

## Command line

```
usage: zenodo-bibtex [-h] (--latest | --version VERSION) [--base-url BASE_URL]
                     [--timeout TIMEOUT] [--retries RETRIES] [-v | -q]
                     [--tool-version]
                     CONCEPT_ID
```

Exactly one of `--latest` or `--version` is required.

`--version` is matched **verbatim** against the version string as published on
Zenodo. It is never parsed as a semantic version, because Zenodo's version field
is free text rather than a validated version number. Projects publish two
component versions, zero padded ones, and occasionally a release code name, none
of which survive being treated as numbers — under numeric comparison `v0.10`
becomes indistinguishable from `v0.1`. Pass the string exactly as Zenodo shows
it, usually including the leading `v`.

Note that `--version` selects the *Zenodo record's* version. This tool's own
version is `--tool-version`.

### Accepted forms of CONCEPT_ID

All of these mean the same thing:

```
1234567
zenodo.1234567
10.5281/zenodo.1234567
https://doi.org/10.5281/zenodo.1234567
https://zenodo.org/doi/10.5281/zenodo.1234567
https://zenodo.org/records/1234567
```

### Exit codes

| Code | Meaning | What a CI job should do |
| ---- | ------- | ----------------------- |
| 0 | Success | — |
| 1 | Unexpected error | Fail, and report a bug |
| 2 | Usage error, or an unrecognised concept id | Fix the invocation |
| 3 | No such concept id on Zenodo | Fail, the id is wrong |
| 4 | The concept has no such version | Fail, or fall back to `--latest` |
| 5 | Zenodo unreachable after all retries | Retry later |

Code 5 is the only one worth retrying; everything else stays broken until
something changes.

### Options

| Option | Default | Purpose |
| ------ | ------- | ------- |
| `--base-url` | `https://zenodo.org/api` | Point at Zenodo Sandbox or another instance |
| `--timeout` | `10` | Per-request timeout in seconds |
| `--retries` | `3` | Attempts for connection errors and 429/5xx. A 404 is never retried |
| `-v`, `-vv` | — | Log progress, then debug output, on stderr |
| `-q` | — | Log only errors |

Set `ZENODO_TOKEN` in the environment to authenticate, which raises Zenodo's
rate and page size limits. It is optional and not needed for public records.

## Python API

The same functionality is importable, which is the better fit for a Sphinx
`conf.py` or any other script that is already running Python.

```python
from zenodo_bibtex_exporter import ZenodoBibtexError, get_bibtex, resolve

# The latest version, or one exact version.
entry = get_bibtex("1234567")
entry = get_bibtex("1234567", version="v2.1.0")

# Resolve without fetching the entry, to inspect what a concept id points at.
record = resolve("1234567")
```

```pycon
>>> record
Record(record_id='7654321', concept_id='1234567', version='v2.1.0')
```

`record_id` identifies the one specific version, `concept_id` is the id that
stays stable across releases.

Both functions accept the same id spellings as the CLI, and the same `base_url`,
`timeout`, `retries` and `token` options. Pass a pre-built `ZenodoClient` as
`client=` to reuse a session.

Every failure raises a subclass of `ZenodoBibtexError`
(`InvalidConceptIdError`, `ConceptNotFoundError`, `VersionNotFoundError`,
`ZenodoUnavailableError`). Nothing is returned as a placeholder, so a caller can
always tell a failed lookup from a real result.

### Citing your own project in its docs

A documentation build usually wants to degrade rather than fail when Zenodo is
briefly unreachable:

```python
import logging

import mypackage
from zenodo_bibtex_exporter import ZenodoBibtexError, get_bibtex

CONCEPT_ID = "1234567"

try:
    citation = get_bibtex(CONCEPT_ID, version=f"v{mypackage.__version__}")
except ZenodoBibtexError as error:
    logging.warning("No citation information: %s", error)
    citation = get_bibtex(CONCEPT_ID)  # or static fallback text
```

Between releases `__version__` is something like `2.1.1.dev3+gabc1234`, which has
no Zenodo record, so this path is taken on every development build. That is
expected, and is why the fallback matters.

Nothing in the API configures logging or writes to a stream, so importing it
cannot disturb the host application's logging setup.

## Use in GitHub Actions

```yaml
- name: Write citation file
  run: uvx zenodo-bibtex "${{ vars.ZENODO_CONCEPT_ID }}" --latest > CITATION.bib
```

Because logging goes to stderr, the redirect captures the entry and nothing
else, at any verbosity.

## Development

```console
uv sync                       # create the environment
uv run pytest                 # offline suite, makes no network calls
uv run pytest -m network      # contract tests against the live Zenodo API
uv run pre-commit run --all-files
```

The `network` marked tests are deselected by default. They are the only tests
that can catch Zenodo changing its API, since everything else is mocked, so CI
runs them on a weekly schedule rather than on every pull request.

## License

MIT. See [LICENSE](LICENSE).
