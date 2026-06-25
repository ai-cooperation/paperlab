from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine_v3.artifacts import CANONICAL_DATA_PATH, build_canonical_data, load_or_build_canonical_data

pytestmark = pytest.mark.unit


def test_build_canonical_data_from_included_two_source_schema(tmp_path: Path):
    run_dir = tmp_path / "run"
    (run_dir / "real_experiments").mkdir(parents=True)
    (run_dir / "figures").mkdir()
    (run_dir / "doi_audit.json").write_text(
        json.dumps(
            {
                "summary": {
                    "included_bib_entries": 35,
                    "included_two_source_verification_rate": 1.0,
                }
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "real_experiments" / "real_results.json").write_text(
        json.dumps(
            {
                "abstract_level_effects_extracted": [
                    {"doi": "10.1000/example.1"},
                    {"doi": "10.1000/example.2"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "figures" / "fig_prisma_flow.svg").write_text("<svg/>", encoding="utf-8")
    (run_dir / "figures" / "fig_prisma_flow.png").write_bytes(b"png")

    data = build_canonical_data(run_dir)

    assert data["schema_version"] == "paperlab.data.v3.1"
    assert data["references"] == {"count": 35}
    assert data["verification"] == {"two_source_rate": 1.0}
    assert data["effects"]["poolable_k"] == 2
    assert data["figures"] == [{"name": "fig_prisma_flow", "svg": True, "png": True}]


def test_load_or_build_canonical_data_writes_artifact(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "references.bib").write_text("@article{one}\n@article{two}\n", encoding="utf-8")

    data = load_or_build_canonical_data(run_dir, write=True)

    assert data["references"]["count"] == 2
    canonical_path = run_dir / CANONICAL_DATA_PATH
    assert canonical_path.is_file()
    saved = json.loads(canonical_path.read_text(encoding="utf-8"))
    assert saved["schema_version"] == "paperlab.data.v3.1"
