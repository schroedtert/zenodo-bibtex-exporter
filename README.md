# zenodo-bibtex-exporter

Export BibTeX citation information from a Zenodo record.

Given the *concept id* of a project on Zenodo, `zenodo-bibtex` prints the BibTeX
entry for either the latest version or a specific one. The entry goes to stdout
and all logging goes to stderr, so the output can be piped in CI workflows.

Usage documentation follows once the CLI lands.
