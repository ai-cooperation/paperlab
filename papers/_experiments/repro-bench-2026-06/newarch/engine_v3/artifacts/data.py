from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


CANONICAL_DATA_SCHEMA_VERSION = "paperlab.data.v3.1"
CANONICAL_DATA_V3_2_SCHEMA_VERSION = "paperlab.data.v3.2"
DOI_VERIFICATION_V3_2_SCHEMA_VERSION = "paperlab.doi_verification.v3.2"
EFFECTS_V3_2_SCHEMA_VERSION = "paperlab.effects.v3.2"
CANONICAL_DATA_PATH = Path("artifacts/data/canonical.v3_1.json")
CANONICAL_DATA_V3_2_PATH = Path("artifacts/data/canonical.v3_2.json")
DOI_VERIFICATION_V3_2_PATH = Path("artifacts/data/doi_verification.v3_2.json")
EFFECTS_V3_2_PATH = Path("artifacts/data/effects.v3_2.json")


def load_or_build_canonical_data(
    run_dir: Path,
    *,
    write: bool = False,
    schema_version: str = "v3.1",
) -> dict[str, Any]:
    v3_2_path = run_dir / CANONICAL_DATA_V3_2_PATH
    if v3_2_path.is_file():
        data = _read_valid_canonical(v3_2_path, CANONICAL_DATA_V3_2_SCHEMA_VERSION)
        if data:
            return data

    v3_1_path = run_dir / CANONICAL_DATA_PATH
    if v3_1_path.is_file():
        data = _read_valid_canonical(v3_1_path, CANONICAL_DATA_SCHEMA_VERSION)
        if data:
            return data

    if schema_version == "v3.2":
        data = build_canonical_data_v3_2(run_dir)
        if write and data:
            write_canonical_data_v3_2(run_dir, data)
        return data

    data = build_canonical_data(run_dir)
    if write and data:
        write_canonical_data(run_dir, data)
    return data


def _read_valid_canonical(path: Path, schema_version: str) -> dict[str, Any]:
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        if isinstance(data, dict) and data.get("schema_version") == schema_version:
            return data
    return {}


def write_canonical_data(run_dir: Path, data: dict[str, Any]) -> Path:
    path = run_dir / CANONICAL_DATA_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def write_canonical_data_v3_2(run_dir: Path, data: dict[str, Any]) -> Path:
    doi = data.get("_doi_verification")
    effects = data.get("_effects")
    public_data = {k: v for k, v in data.items() if k not in {"_doi_verification", "_effects"}}
    if isinstance(doi, dict):
        _write_json(run_dir / DOI_VERIFICATION_V3_2_PATH, doi)
    if isinstance(effects, dict):
        _write_json(run_dir / EFFECTS_V3_2_PATH, effects)
    return _write_json(run_dir / CANONICAL_DATA_V3_2_PATH, public_data)


def _write_json(path: Path, data: dict[str, Any]) -> Path:
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


def build_canonical_data_v3_2(run_dir: Path) -> dict[str, Any]:
    doi = _read_json(run_dir / "doi_audit.json")
    real_results = _read_json(run_dir / "real_experiments" / "real_results.json")
    references_bib = _read_text(run_dir / "references.bib")
    figures = _scan_figures(run_dir)

    doi_verification = build_doi_verification_v3_2(doi, references_bib)
    effects = build_effects_v3_2(real_results)
    return {
        "schema_version": CANONICAL_DATA_V3_2_SCHEMA_VERSION,
        "references": {
            "count": doi_verification["retained_references"],
            "two_source_verified": doi_verification["two_source_verified"],
        },
        "verification": {
            "two_source_rate": doi_verification["two_source_rate"],
            "source_artifact": str(DOI_VERIFICATION_V3_2_PATH),
        },
        "effects": {
            "poolable_k": effects["poolable_k"],
            "abstract_level_count": effects["abstract_level_count"],
            "interpretation": effects["interpretation"],
            "source_artifact": str(EFFECTS_V3_2_PATH),
        },
        "figures": figures,
        "human_checkpoint": None,
        "source_files": {
            "doi_audit": "doi_audit.json" if doi else None,
            "real_results": "real_experiments/real_results.json" if real_results else None,
            "references_bib": "references.bib" if references_bib else None,
        },
        "_doi_verification": doi_verification,
        "_effects": effects,
    }


def build_doi_verification_v3_2(doi: dict[str, Any], references_bib: str) -> dict[str, Any]:
    refs = _canonical_references(doi, references_bib)
    count = int(refs["count"] or 0)
    rate = refs["two_source_rate"]
    verified = _two_source_verified_count(doi, count, rate)
    return {
        "schema_version": DOI_VERIFICATION_V3_2_SCHEMA_VERSION,
        "total_candidates": _total_candidate_count(doi, count),
        "retained_references": count,
        "two_source_verified": verified,
        "two_source_rate": rate,
        "sources": _verification_sources(doi),
        "unverified": _unverified_rows(doi),
    }


def build_effects_v3_2(real_results: dict[str, Any]) -> dict[str, Any]:
    effects = _canonical_effects(real_results)
    return {
        "schema_version": EFFECTS_V3_2_SCHEMA_VERSION,
        "poolable_k": effects["poolable_k"],
        "abstract_level_count": effects["abstract_level_count"],
        "interpretation": effects["interpretation"],
        "effect_rows": _effect_rows(real_results),
        "non_poolable_reason": None if effects["poolable_k"] else "missing_or_unextractable",
    }


def build_data_substeps_v3_2(run_dir: Path) -> list[dict[str, Any]]:
    canonical = _read_json(run_dir / CANONICAL_DATA_V3_2_PATH)
    figures = canonical.get("figures") if isinstance(canonical.get("figures"), list) else []
    figure_outputs = [
        "figures/%s.%s" % (figure.get("name"), ext)
        for figure in figures
        if isinstance(figure, dict) and figure.get("name")
        for ext in ("svg", "png")
        if (run_dir / "figures" / ("%s.%s" % (figure.get("name"), ext))).is_file()
    ]
    return [
        {
            "id": "normalize_contract",
            "owner": "deterministic",
            "status": _done_if_any(run_dir, ["research_contract.json", "research_contract.input.json"]),
            "outputs": _existing_outputs(run_dir, ["research_contract.json", "research_contract.input.json"]),
        },
        {
            "id": "collect_reference_candidates",
            "owner": "hermes_bounded",
            "status": _done_if_any(run_dir, ["references.bib", "doi_audit.json"]),
            "outputs": _existing_outputs(run_dir, ["references.bib", "doi_audit.json"]),
        },
        {
            "id": "verify_doi_two_sources",
            "owner": "deterministic",
            "status": _done_if_path(run_dir / DOI_VERIFICATION_V3_2_PATH),
            "outputs": _existing_outputs(run_dir, [str(DOI_VERIFICATION_V3_2_PATH)]),
        },
        {
            "id": "extract_abstract_level_effects",
            "owner": "hermes_bounded",
            "status": _done_if_path(run_dir / EFFECTS_V3_2_PATH),
            "outputs": _existing_outputs(run_dir, [str(EFFECTS_V3_2_PATH)]),
        },
        {
            "id": "write_canonical_data",
            "owner": "deterministic",
            "status": _done_if_path(run_dir / CANONICAL_DATA_V3_2_PATH),
            "outputs": _existing_outputs(run_dir, [str(CANONICAL_DATA_V3_2_PATH)]),
        },
        {
            "id": "generate_figures",
            "owner": "deterministic",
            "status": "done" if figure_outputs else "pending",
            "outputs": figure_outputs,
        },
        {
            "id": "gate_A_E",
            "owner": "validator",
            "status": "pending",
            "outputs": [],
        },
    ]


def _two_source_verified_count(doi: dict[str, Any], count: int, rate: float | int | None) -> int:
    audit_summary = doi.get("audit_summary")
    if isinstance(audit_summary, dict):
        verified = _number(audit_summary.get("verified_at_least_two_sources"))
        if verified is not None:
            return int(verified)

    verified = _number(doi.get("passed_two_source_rule"))
    if verified is not None:
        return int(verified)
    verified = _number(doi.get("two_or_more_source_verified_count"))
    if verified is not None:
        return int(verified)

    summary = doi.get("summary")
    if isinstance(summary, dict):
        for key in (
            "two_source_verified",
            "selected_passing_two_source_rule",
            "verified_included_references",
            "included_with_two_or_more_validations",
            "passes_two_of_three",
            "entries_meeting_two_source_verification",
        ):
            verified = _number(summary.get(key))
            if verified is not None:
                return int(verified)
        total = _first_number(summary, "included_entries", "total_entries", "total")
        source_verified = _summary_two_source_verified_count(summary, total)
        if source_verified is not None:
            return source_verified

    records = _audit_rows(doi)
    if records:
        return sum(
            1
            for row in records
            if isinstance(row, dict) and _row_two_source_verified(row)
        )

    if count and rate is not None:
        return int(round(count * float(rate)))
    return 0


def _total_candidate_count(doi: dict[str, Any], count: int) -> int:
    for key in ("total_candidates", "candidates", "total_references", "total_records", "total", "bib_count"):
        value = _number(doi.get(key))
        if value is not None:
            return int(value)

    audit_summary = doi.get("audit_summary")
    if isinstance(audit_summary, dict):
        total = _number(audit_summary.get("total"))
        if total is not None:
            return int(total)

    summary = doi.get("summary")
    if isinstance(summary, dict):
        total = _first_number(summary, "total_candidates", "candidates_seen", "total_entries", "included_entries", "total")
        if total is not None:
            return int(total)

    records = _audit_rows(doi)
    if records:
        return len(records)
    return count


def _verification_sources(doi: dict[str, Any]) -> list[str]:
    sources = doi.get("sources")
    if isinstance(sources, list):
        return [str(source) for source in sources if source]

    source_counts = doi.get("source_counts")
    if isinstance(source_counts, dict):
        return sorted(str(source) for source, count in source_counts.items() if count)

    checks = doi.get("checks")
    if isinstance(checks, dict):
        return sorted(str(source) for source, passed in checks.items() if passed)

    summary = doi.get("summary")
    if isinstance(summary, dict):
        return sorted(
            source
            for source, key in (
                ("crossref", "crossref_valid"),
                ("openalex", "openalex_valid"),
                ("semantic_scholar", "semantic_scholar_valid"),
            )
            if _number(summary.get(key))
        )

    return []


def _unverified_rows(doi: dict[str, Any]) -> list[dict[str, Any]]:
    records = _audit_rows(doi)
    rows: list[dict[str, Any]] = []
    for row in records:
        if not isinstance(row, dict):
            continue
        if _row_two_source_verified(row):
            continue
        rows.append(
            {
                "title": row.get("title"),
                "doi": row.get("doi"),
                "reason": row.get("reason") or row.get("status") or "not_two_source_verified",
            }
        )
    return rows


def _effect_rows(real_results: dict[str, Any]) -> list[dict[str, Any]]:
    for key in (
        "effects",
        "included_effects",
        "abstract_level_effects",
        "abstract_extracted_effects",
        "abstract_level_outcomes",
        "abstract_level_effects_extracted",
        "abstract_numeric_evidence_index",
        "forest_style_data",
        "poolable_effects",
    ):
        value = real_results.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]

    figure_inputs = real_results.get("figure_inputs")
    if isinstance(figure_inputs, dict) and isinstance(figure_inputs.get("fig_forest_plot"), list):
        return [row for row in figure_inputs["fig_forest_plot"] if isinstance(row, dict)]
    return []


def _done_if_path(path: Path) -> str:
    return "done" if path.is_file() else "pending"


def _done_if_any(run_dir: Path, paths: list[str]) -> str:
    return "done" if any((run_dir / path).is_file() for path in paths) else "pending"


def _existing_outputs(run_dir: Path, paths: list[str]) -> list[str]:
    return [path for path in paths if (run_dir / path).is_file()]


def _canonical_references(doi: dict[str, Any], references_bib: str) -> dict[str, Any]:
    count = _first_number(
        doi,
        "kept",
        "crossref_real",
        "bib_count",
        "retained_verified_references",
        "selected_count",
        "total_references",
        "total_records",
    )
    rate = _first_number(
        doi,
        "doi_real_rate",
        "real_rate",
        "real_existence_rate",
        "selected_pass_rate",
        "doi_real_rate_crossref",
    )
    if rate is None:
        total_records = _number(doi.get("total_records"))
        passed = _number(doi.get("passed_two_source_rule"))
        if total_records and passed is not None:
            rate = passed / total_records

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

    records = _audit_rows(doi)
    if rate is None and records:
        verified_count = sum(1 for row in records if isinstance(row, dict) and _row_two_source_verified(row))
        rate = verified_count / len(records)
    if count is None and records:
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
            selected = _first_number(summary, "selected_references", "included_references", "included_entries", "total")
            passing = _first_number(
                summary,
                "selected_passing_two_source_rule",
                "included_with_two_or_more_validations",
                "passes_two_of_three",
            )
            if selected and passing is not None:
                rate = passing / selected
        if rate is None:
            total = _first_number(summary, "included_references", "total_entries", "included_entries", "total")
            passing = _first_number(summary, "entries_meeting_two_source_verification")
            if total and passing is not None:
                rate = passing / total
        if rate is None:
            total = _first_number(summary, "included_references", "included_entries", "total_entries", "total")
            verified = _summary_two_source_verified_count(summary, total)
            if total and verified is not None:
                rate = verified / total
        count = count if count is not None else _first_number(
            summary,
            "included_references",
            "included_entries",
            "total_entries",
            "total",
        )

    if count is None and references_bib:
        count = len(re.findall(r"^@\w+\s*\{", references_bib, re.MULTILINE))

    return {"count": int(count or 0), "two_source_rate": rate}


def _audit_rows(doi: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("records", "entries", "items", "references", "verified_references", "included"):
        value = doi.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def _row_two_source_verified(row: dict[str, Any]) -> bool:
    if row.get("verified") is True or row.get("passed_two_of_three") is True:
        return True
    if row.get("passes_two_of_three") is True or row.get("passes_two_source_rule") is True:
        return True
    validation_count = _number(row.get("validation_count"))
    if validation_count is not None and validation_count >= 2:
        return True
    verified_source_count = _number(row.get("verified_source_count"))
    if verified_source_count is not None and verified_source_count >= 2:
        return True

    sources = row.get("verification_sources")
    if isinstance(sources, list) and len([source for source in sources if source]) >= 2:
        return True

    checks = [
        row.get("crossref_verified"),
        row.get("openalex_verified"),
        row.get("semantic_scholar_verified"),
        row.get("semantic_scholar_checked_positive"),
        row.get("semantic_scholar_checked"),
        row.get("semanticscholar"),
    ]
    for key in ("crossref", "openalex", "semantic_scholar"):
        nested = row.get(key)
        if isinstance(nested, dict):
            checks.append(nested.get("ok"))
    validations = row.get("validations")
    if isinstance(validations, dict):
        checks.extend(validations.values())

    metadata_quality = row.get("metadata_quality")
    if isinstance(metadata_quality, dict):
        checks.extend(
            [
                metadata_quality.get("doi_resolves_crossref"),
                metadata_quality.get("doi_resolves_openalex"),
                metadata_quality.get("doi_resolves_semantic_scholar"),
            ]
        )
    return sum(1 for value in checks if value is True) >= 2


def _summary_two_source_verified_count(summary: dict[str, Any], total: float | int | None) -> int | None:
    source_counts = [
        _number(summary.get("crossref_verified")) or _number(summary.get("crossref_valid")) or _number(summary.get("crossref_ok")),
        _number(summary.get("openalex_verified")) or _number(summary.get("openalex_valid")) or _number(summary.get("openalex_ok")),
        _number(summary.get("semantic_scholar_verified"))
        or _number(summary.get("semantic_scholar_valid"))
        or _number(summary.get("semantic_scholar_checked_positive"))
        or _number(summary.get("semantic_scholar_ok")),
    ]
    usable_counts = [int(value) for value in source_counts if value is not None]
    if total is None or not usable_counts:
        return None
    passing_sources_per_entry = sum(usable_counts)
    # Conservative lower bound: if each retained entry needs two independent positive
    # sources, floor(total) is the maximum certifiable all-entry count.
    return min(int(total), passing_sources_per_entry // 2)


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
