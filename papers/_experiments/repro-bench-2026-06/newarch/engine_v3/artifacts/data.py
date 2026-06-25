from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


CANONICAL_DATA_SCHEMA_VERSION = "paperlab.data.v3.1"
CANONICAL_DATA_PATH = Path("artifacts/data/canonical.v3_1.json")


def load_or_build_canonical_data(run_dir: Path, *, write: bool = False) -> dict[str, Any]:
    path = run_dir / CANONICAL_DATA_PATH
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        if isinstance(data, dict) and data.get("schema_version") == CANONICAL_DATA_SCHEMA_VERSION:
            return data

    data = build_canonical_data(run_dir)
    if write and data:
        write_canonical_data(run_dir, data)
    return data


def write_canonical_data(run_dir: Path, data: dict[str, Any]) -> Path:
    path = run_dir / CANONICAL_DATA_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def build_canonical_data(run_dir: Path) -> dict[str, Any]:
    doi = _read_json(run_dir / "doi_audit.json")
    real_results = _read_json(run_dir / "real_experiments" / "real_results.json")
    references_bib = _read_text(run_dir / "references.bib")
    figures = _scan_figures(run_dir)

    refs = _canonical_references(doi, references_bib)
    effects = _canonical_effects(real_results)
    return {
        "schema_version": CANONICAL_DATA_SCHEMA_VERSION,
        "references": {"count": refs["count"]},
        "verification": {"two_source_rate": refs["two_source_rate"]},
        "effects": effects,
        "figures": figures,
        "source_files": {
            "doi_audit": "doi_audit.json" if doi else None,
            "real_results": "real_experiments/real_results.json" if real_results else None,
            "references_bib": "references.bib" if references_bib else None,
        },
    }


def _canonical_references(doi: dict[str, Any], references_bib: str) -> dict[str, Any]:
    count = _first_number(
        doi,
        "kept",
        "crossref_real",
        "bib_count",
        "retained_verified_references",
        "selected_count",
    )
    rate = _first_number(
        doi,
        "doi_real_rate",
        "real_rate",
        "real_existence_rate",
        "selected_pass_rate",
    )

    verification_summary = doi.get("verification_summary")
    if rate is None and isinstance(verification_summary, dict):
        if verification_summary.get("all_retained_verified_by_at_least_two_sources") is True:
            rate = 1.0

    audit_summary = doi.get("audit_summary")
    if isinstance(audit_summary, dict):
        total = _number(audit_summary.get("total"))
        verified = _number(audit_summary.get("verified_at_least_two_sources"))
        if count is None and total is not None:
            count = int(total)
        if rate is None and total and verified is not None:
            rate = verified / total

    records = doi.get("records")
    if rate is None and isinstance(records, list) and records:
        verified_count = sum(
            1
            for row in records
            if isinstance(row, dict) and (row.get("verified") is True or row.get("passed_two_of_three") is True)
        )
        rate = verified_count / len(records)
    if count is None and isinstance(records, list) and records:
        count = len(records)

    summary = doi.get("summary")
    if isinstance(summary, dict):
        rate = rate if rate is not None else _first_number(
            summary,
            "doi_real_rate",
            "real_rate",
            "real_existence_rate",
            "verification_rate_included",
            "two_source_pass_rate",
            "included_two_source_verification_rate",
            "included_two_source_rate",
        )
        if rate is None and summary.get("all_bib_entries_two_source_verified") is True:
            rate = 1.0
        count = count if count is not None else _first_number(
            summary,
            "bib_entries_written",
            "references_selected",
            "selected_references",
            "verified_included_references",
            "included_doi_backed_references",
            "included_bib_entries",
            "included_references",
        )
        if rate is None:
            selected = _number(summary.get("selected_references"))
            passing = _number(summary.get("selected_passing_two_source_rule"))
            if selected and passing is not None:
                rate = passing / selected

    if count is None and references_bib:
        count = len(re.findall(r"^@\w+\s*\{", references_bib, re.MULTILINE))

    return {"count": int(count or 0), "two_source_rate": rate}


def _canonical_effects(real_results: dict[str, Any]) -> dict[str, Any]:
    count = _effect_count(real_results)
    interpretation = "abstract_level" if count else "missing_or_unextractable"
    return {
        "poolable_k": count,
        "abstract_level_count": count,
        "interpretation": interpretation,
    }


def _effect_count(real_results: dict[str, Any]) -> int:
    pooled = (real_results.get("meta") or {}).get("pooled") if isinstance(real_results.get("meta"), dict) else None
    if isinstance(pooled, dict):
        counts = [
            int(value.get("k") or 0)
            for value in pooled.values()
            if isinstance(value, dict) and isinstance(value.get("k"), (int, float))
        ]
        if counts:
            return max(counts)

    max_poolable = real_results.get("max_poolable_k")
    if isinstance(max_poolable, int):
        poolable_effects = real_results.get("poolable_effects")
        return len(poolable_effects) if isinstance(poolable_effects, list) else max_poolable

    for key in (
        "effects",
        "included_effects",
        "abstract_level_effects",
        "abstract_extracted_effects",
        "abstract_level_outcomes",
        "abstract_level_effects_extracted",
        "abstract_numeric_evidence_index",
        "forest_style_data",
    ):
        value = real_results.get(key)
        if isinstance(value, list):
            return len(value)

    pooled_smd = real_results.get("pooled_smd")
    if isinstance(pooled_smd, dict) and isinstance(pooled_smd.get("k"), int):
        return pooled_smd["k"]

    for parent, key in (
        ("synthesis", "numeric_effect_count"),
        ("screening", "abstract_level_numeric_effects_extracted"),
        ("prisma_counts", "abstract_extractable_effects_in_quantitative_synthesis"),
        ("effect_extraction", "records_with_abstract_level_numeric_effects"),
        ("counts", "standardized_effects_with_ci_extracted"),
    ):
        node = real_results.get(parent)
        if isinstance(node, dict) and isinstance(node.get(key), int):
            return node[key]

    figure_inputs = real_results.get("figure_inputs")
    if isinstance(figure_inputs, dict) and isinstance(figure_inputs.get("fig_forest_plot"), list):
        return len(figure_inputs["fig_forest_plot"])

    return 0


def _scan_figures(run_dir: Path) -> list[dict[str, Any]]:
    figdir = run_dir / "figures"
    if not figdir.is_dir():
        return []
    svgs = {p.stem for p in figdir.glob("*.svg")}
    pngs = {p.stem for p in figdir.glob("*.png")}
    return [{"name": stem, "svg": stem in svgs, "png": stem in pngs} for stem in sorted(svgs | pngs)]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _first_number(data: dict[str, Any], *keys: str) -> float | int | None:
    for key in keys:
        value = _number(data.get(key))
        if value is not None:
            return value
    return None


def _number(value: Any) -> float | int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None
