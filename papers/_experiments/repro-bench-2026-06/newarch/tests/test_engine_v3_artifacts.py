from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine_v3.artifacts import (
    CANONICAL_DATA_PATH,
    CANONICAL_DATA_V3_2_PATH,
    DOI_VERIFICATION_V3_2_PATH,
    EFFECTS_V3_2_PATH,
    build_canonical_data,
    build_canonical_data_v3_2,
    load_or_build_canonical_data,
)

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


def test_build_canonical_data_v3_2_accepts_entries_two_of_three_schema(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "references.bib").write_text(
        "\n".join("@article{ref%s,title={T%s}}" % (idx, idx) for idx in range(44)),
        encoding="utf-8",
    )
    (run_dir / "doi_audit.json").write_text(
        json.dumps(
            {
                "summary": {
                    "total": 44,
                    "passes_two_of_three": 41,
                    "fails_two_of_three": 3,
                },
                "entries": [
                    {"doi": "10.1000/%s" % idx, "passes_two_of_three": idx < 41}
                    for idx in range(44)
                ],
            }
        ),
        encoding="utf-8",
    )

    data = build_canonical_data_v3_2(run_dir)

    assert data["references"] == {"count": 44, "two_source_verified": 41}
    assert data["verification"]["two_source_rate"] == 41 / 44


def test_build_canonical_data_v3_2_accepts_entries_source_flags_schema(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "doi_audit.json").write_text(
        json.dumps(
            {
                "summary": {
                    "included_entries": 40,
                    "crossref_verified": 40,
                    "openalex_verified": 40,
                    "semantic_scholar_checked_positive": 6,
                },
                "entries": [
                    {
                        "doi": "10.1000/%s" % idx,
                        "crossref_verified": True,
                        "openalex_verified": True,
                        "semantic_scholar_checked": idx < 6,
                        "included_in_references": True,
                    }
                    for idx in range(40)
                ],
            }
        ),
        encoding="utf-8",
    )

    data = build_canonical_data_v3_2(run_dir)

    assert data["references"] == {"count": 40, "two_source_verified": 40}
    assert data["verification"]["two_source_rate"] == 1.0


def test_build_canonical_data_v3_2_accepts_nested_source_audit_schema(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "doi_audit.json").write_text(
        json.dumps(
            {
                "schema": "paperlab.doi_audit.v3",
                "summary": {
                    "total_entries": 36,
                    "crossref_valid": 36,
                    "openalex_valid": 36,
                    "semantic_scholar_valid": 5,
                    "entries_meeting_two_source_verification": 36,
                },
                "entries": [
                    {
                        "doi": "10.1000/%s" % idx,
                        "crossref": {"ok": True},
                        "openalex": {"ok": True},
                        "semantic_scholar": {"ok": idx < 5},
                        "metadata_quality": {
                            "doi_resolves_crossref": True,
                            "doi_resolves_openalex": True,
                            "doi_resolves_semantic_scholar": idx < 5,
                        },
                    }
                    for idx in range(36)
                ],
            }
        ),
        encoding="utf-8",
    )

    data = build_canonical_data_v3_2(run_dir)

    assert data["references"] == {"count": 36, "two_source_verified": 36}
    assert data["verification"]["two_source_rate"] == 1.0
    assert data["_doi_verification"]["total_candidates"] == 36
    assert data["_doi_verification"]["sources"] == ["crossref", "openalex", "semantic_scholar"]


def test_build_canonical_data_v3_2_accepts_top_level_two_source_rule_schema(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "doi_audit.json").write_text(
        json.dumps(
            {
                "total_records": 41,
                "passed_two_source_rule": 41,
                "failed_two_source_rule": [],
                "records": [
                    {
                        "doi": "10.1000/%s" % idx,
                        "crossref": True,
                        "openalex": True,
                        "semanticscholar": False,
                        "verified_source_count": 2,
                        "passes_two_source_rule": True,
                    }
                    for idx in range(41)
                ],
            }
        ),
        encoding="utf-8",
    )

    data = build_canonical_data_v3_2(run_dir)

    assert data["references"] == {"count": 41, "two_source_verified": 41}
    assert data["verification"]["two_source_rate"] == 1.0
    assert data["_doi_verification"]["total_candidates"] == 41


def test_build_canonical_data_v3_2_accepts_legacy_source_bootstrap_doi_schema(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "doi_audit.json").write_text(
        json.dumps(
            {
                "total_references": 41,
                "crossref_verified_count": 41,
                "two_or_more_source_verified_count": 41,
                "doi_real_rate_crossref": 1.0,
                "records": [
                    {
                        "doi": "10.1000/%s" % idx,
                        "verification": {
                            "crossref": True,
                            "openalex": True,
                            "semantic_scholar": False,
                        },
                    }
                    for idx in range(41)
                ],
            }
        ),
        encoding="utf-8",
    )

    data = build_canonical_data_v3_2(run_dir)

    assert data["references"] == {"count": 41, "two_source_verified": 41}
    assert data["verification"]["two_source_rate"] == 1.0
    assert data["_doi_verification"]["total_candidates"] == 41


def test_build_canonical_data_v3_2_accepts_included_validation_summary(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "doi_audit.json").write_text(
        json.dumps(
            {
                "summary": {
                    "candidates_seen": 69,
                    "included_references": 35,
                    "included_with_two_or_more_validations": 35,
                    "included_with_abstract": 35,
                    "failed_or_excluded_candidates": 34,
                },
                "included": [
                    {
                        "doi": "10.1000/%s" % idx,
                        "validations": {
                            "crossref": True,
                            "openalex": True,
                            "semantic_scholar": True,
                        },
                        "validation_count": 3,
                    }
                    for idx in range(35)
                ],
            }
        ),
        encoding="utf-8",
    )

    data = build_canonical_data_v3_2(run_dir)

    assert data["references"] == {"count": 35, "two_source_verified": 35}
    assert data["verification"]["two_source_rate"] == 1.0


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


def test_load_or_build_canonical_data_writes_v3_2_artifact_bundle(tmp_path: Path):
    run_dir = tmp_path / "run"
    (run_dir / "real_experiments").mkdir(parents=True)
    (run_dir / "doi_audit.json").write_text(
        json.dumps(
            {
                "audit_summary": {
                    "total": 40,
                    "verified_at_least_two_sources": 38,
                }
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "real_experiments" / "real_results.json").write_text(
        json.dumps({"effects": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}),
        encoding="utf-8",
    )

    data = load_or_build_canonical_data(run_dir, write=True, schema_version="v3.2")

    assert data["schema_version"] == "paperlab.data.v3.2"
    assert data["references"] == {"count": 40, "two_source_verified": 38}
    assert data["verification"] == {
        "two_source_rate": 0.95,
        "source_artifact": str(DOI_VERIFICATION_V3_2_PATH),
    }
    assert data["effects"] == {
        "poolable_k": 3,
        "abstract_level_count": 3,
        "interpretation": "abstract_level",
        "source_artifact": str(EFFECTS_V3_2_PATH),
    }
    assert (run_dir / CANONICAL_DATA_V3_2_PATH).is_file()
    assert (run_dir / DOI_VERIFICATION_V3_2_PATH).is_file()
    assert (run_dir / EFFECTS_V3_2_PATH).is_file()


def test_load_or_build_canonical_data_prefers_existing_v3_2_over_v3_1(tmp_path: Path):
    run_dir = tmp_path / "run"
    (run_dir / "artifacts" / "data").mkdir(parents=True)
    (run_dir / CANONICAL_DATA_PATH).write_text(
        json.dumps(
            {
                "schema_version": "paperlab.data.v3.1",
                "references": {"count": 35},
                "verification": {"two_source_rate": 0.8},
                "effects": {"poolable_k": 1, "abstract_level_count": 1},
                "figures": [],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / CANONICAL_DATA_V3_2_PATH).write_text(
        json.dumps(
            {
                "schema_version": "paperlab.data.v3.2",
                "references": {"count": 42, "two_source_verified": 42},
                "verification": {
                    "two_source_rate": 1.0,
                    "source_artifact": str(DOI_VERIFICATION_V3_2_PATH),
                },
                "effects": {
                    "poolable_k": 7,
                    "abstract_level_count": 7,
                    "source_artifact": str(EFFECTS_V3_2_PATH),
                },
                "figures": [],
                "human_checkpoint": None,
            }
        ),
        encoding="utf-8",
    )

    data = load_or_build_canonical_data(run_dir)

    assert data["schema_version"] == "paperlab.data.v3.2"
    assert data["references"]["count"] == 42
    assert data["verification"]["two_source_rate"] == 1.0


def test_build_data_substeps_v3_2_reports_deterministic_data_loop(tmp_path: Path):
    from engine_v3.artifacts import build_data_substeps_v3_2

    run_dir = tmp_path / "run"
    (run_dir / "artifacts" / "data").mkdir(parents=True)
    (run_dir / "research_contract.json").write_text("{}", encoding="utf-8")
    (run_dir / "references.bib").write_text("@article{one}\n", encoding="utf-8")
    (run_dir / DOI_VERIFICATION_V3_2_PATH).write_text(
        json.dumps({"schema_version": "paperlab.doi_verification.v3.2"}),
        encoding="utf-8",
    )
    (run_dir / EFFECTS_V3_2_PATH).write_text(
        json.dumps({"schema_version": "paperlab.effects.v3.2"}),
        encoding="utf-8",
    )
    (run_dir / CANONICAL_DATA_V3_2_PATH).write_text(
        json.dumps({"schema_version": "paperlab.data.v3.2", "figures": [{"name": "fig_prisma_flow"}]}),
        encoding="utf-8",
    )
    (run_dir / "figures").mkdir()
    (run_dir / "figures" / "fig_prisma_flow.svg").write_text("<svg/>", encoding="utf-8")
    (run_dir / "figures" / "fig_prisma_flow.png").write_bytes(b"png")

    substeps = build_data_substeps_v3_2(run_dir)

    assert [step["id"] for step in substeps] == [
        "normalize_contract",
        "collect_reference_candidates",
        "verify_doi_two_sources",
        "extract_abstract_level_effects",
        "write_canonical_data",
        "generate_figures",
        "gate_A_E",
    ]
    assert {step["id"]: step["status"] for step in substeps} == {
        "normalize_contract": "done",
        "collect_reference_candidates": "done",
        "verify_doi_two_sources": "done",
        "extract_abstract_level_effects": "done",
        "write_canonical_data": "done",
        "generate_figures": "done",
        "gate_A_E": "pending",
    }
    assert substeps[2]["owner"] == "deterministic"
    assert substeps[3]["owner"] == "hermes_bounded"
