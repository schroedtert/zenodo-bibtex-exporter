"""Entry point for ``python -m zenodo_bibtex_exporter``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
