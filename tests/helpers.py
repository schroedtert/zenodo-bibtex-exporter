"""Shared test data and payload builders."""

SAMPLE_BIBTEX = """@software{schrodter_2026_21476844,
  author       = {Schrödter, Tobias and
                  The PedPy Development Team},
  title        = {PedPy - Pedestrian Trajectory Analyzer},
  month        = jul,
  year         = 2026,
  publisher    = {Zenodo},
  version      = {v1.5.1},
  doi          = {10.5281/zenodo.21476844},
  url          = {https://doi.org/10.5281/zenodo.21476844},
}
"""


def record_payload(record_id: str, concept_id: str, version: str) -> dict[str, object]:
    """Build a minimal Zenodo record payload."""
    return {"id": int(record_id), "conceptrecid": concept_id, "metadata": {"version": version}}
