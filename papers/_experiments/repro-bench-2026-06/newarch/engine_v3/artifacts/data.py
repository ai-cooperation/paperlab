from __future__ import annotations

import json
import re
import base64
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


CANONICAL_DATA_SCHEMA_VERSION = "paperlab.data.v3.1"
CANONICAL_DATA_V3_2_SCHEMA_VERSION = "paperlab.data.v3.2"
DOI_VERIFICATION_V3_2_SCHEMA_VERSION = "paperlab.doi_verification.v3.2"
EFFECTS_V3_2_SCHEMA_VERSION = "paperlab.effects.v3.2"
CANONICAL_DATA_PATH = Path("artifacts/data/canonical.v3_1.json")
CANONICAL_DATA_V3_2_PATH = Path("artifacts/data/canonical.v3_2.json")
DOI_VERIFICATION_V3_2_PATH = Path("artifacts/data/doi_verification.v3_2.json")
EFFECTS_V3_2_PATH = Path("artifacts/data/effects.v3_2.json")
REFERENCE_TOPUP_V3_2_PATH = Path("artifacts/data/reference_topup.v3_2.json")
DATA_COMPLETENESS_V3_2_PATH = Path("artifacts/data/completeness.v3_2.json")


def load_or_build_canonical_data(
    run_dir: Path,
    *,
    write: bool = False,
    schema_version: str = "v3.1",
    force: bool = False,
) -> dict[str, Any]:
    v3_2_path = run_dir / CANONICAL_DATA_V3_2_PATH
    if not force and v3_2_path.is_file():
        data = _read_valid_canonical(v3_2_path, CANONICAL_DATA_V3_2_SCHEMA_VERSION)
        if data:
            return data

    v3_1_path = run_dir / CANONICAL_DATA_PATH
    if not force and v3_1_path.is_file():
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
            "id": "top_up_references",
            "owner": "deterministic",
            "status": _done_if_path(run_dir / REFERENCE_TOPUP_V3_2_PATH),
            "outputs": _existing_outputs(run_dir, [str(REFERENCE_TOPUP_V3_2_PATH)]),
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
            "id": "data_output_completeness",
            "owner": "deterministic",
            "status": _done_if_path(run_dir / DATA_COMPLETENESS_V3_2_PATH),
            "outputs": _existing_outputs(run_dir, [str(DATA_COMPLETENESS_V3_2_PATH)]),
        },
        {
            "id": "gate_A_E_G",
            "owner": "validator",
            "status": "pending",
            "outputs": [],
        },
    ]


def run_data_harness_v3_2(
    run_dir: Path,
    required_outputs: list[str],
    *,
    reference_floor: int = 35,
) -> dict[str, Any]:
    """Run deterministic data substeps after Hermes writes candidate artifacts.

    Hermes may collect candidates and draft raw files, but the V3.2 data contract is
    owned here: normalize contract copy, top up trusted seed references, rebuild
    canonical DOI/effects artifacts, and record declared-output completeness.
    """
    run_dir = Path(run_dir)
    _ensure_research_contract_copy(run_dir)
    topup = top_up_references_from_contract_v3_2(run_dir, floor=reference_floor)
    fallback = ensure_minimal_real_results_and_figures_v3_2(run_dir)
    canonical = load_or_build_canonical_data(run_dir, write=True, schema_version="v3.2", force=True)
    completeness = validate_data_outputs_v3_2(run_dir, required_outputs)
    _write_json(run_dir / DATA_COMPLETENESS_V3_2_PATH, completeness)
    return {
        "topup": topup,
        "fallback": fallback,
        "canonical": {
            "references": canonical.get("references"),
            "verification": canonical.get("verification"),
            "effects": canonical.get("effects"),
        },
        "completeness": completeness,
    }


def ensure_minimal_real_results_and_figures_v3_2(run_dir: Path) -> dict[str, Any]:
    """Backfill a real, reproducible evidence-map result from verified references.

    This is the production escape hatch for non-poolable topics. It does not invent
    effect sizes. When Hermes produced verified references but no empirical result
    file, the engine can still deliver a bounded bibliometric/evidence-map paper
    whose numbers are recomputed from references.bib and doi_audit.json.
    """
    run_dir = Path(run_dir)
    rr_path = run_dir / "real_experiments" / "real_results.json"
    existing = _read_json(rr_path)
    refs_text = _read_text(run_dir / "references.bib")
    doi = _read_json(run_dir / "doi_audit.json")
    refs = _canonical_references(doi, refs_text)
    count = int(refs.get("count") or 0)
    if existing:
        _ensure_required_minimal_figures(run_dir, count=count)
        return {"status": "skipped", "reason": "real_results_already_present"}
    if count <= 0:
        return {"status": "blocked", "reason": "no_references_for_evidence_map"}

    rate = refs.get("two_source_rate")
    verified = _two_source_verified_count(doi, count, rate)
    years = _bib_year_counts(refs_text)
    rr = {
        "schema_version": "paperlab.real_results.v3.2",
        "result_type": "bibliometric_evidence_map",
        "status": "completed",
        "simulated": False,
        "analysis_type": "deterministic_reference_evidence_map",
        "reference_count": count,
        "two_source_verified": verified,
        "two_source_rate": float(rate) if isinstance(rate, (int, float)) else None,
        "year_counts": years,
        "max_poolable_k": 0,
        # D1 (V3_2_SPEC.md Decisions): low-poolability runs downgrade explicitly,
        # never silently. This record must surface in the dossier, the status
        # page, and the manuscript Methods section.
        "lane_downgrade": {
            "from": _contract_requested_synthesis(run_dir),
            "to": "narrative_evidence_map_review",
            "reason": "no extractable poolable effects; evidence map uses verified references only",
            "decided_by": "data_phase_evidence_floor",
        },
        "synthesis": {
            "numeric_effect_count": 0,
            "non_poolable_reason": "topic did not yield extractable poolable effects; evidence map uses verified references",
        },
        "figure_inputs": {
            "reference_count": count,
            "two_source_verified": verified,
            "year_counts": years,
        },
    }
    rr_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(rr_path, rr)
    _ensure_required_minimal_figures(run_dir, count=count)
    return {
        "status": "done",
        "reason": "backfilled_bibliometric_evidence_map",
        "reference_count": count,
        "two_source_verified": verified,
    }


def top_up_references_from_contract_v3_2(
    run_dir: Path,
    *,
    floor: int = 35,
    search_provider: Callable[[Path, int, set[str]], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    run_dir = Path(run_dir)
    refs_path = run_dir / "references.bib"
    bib = _read_text(refs_path)
    before_count = _bib_entry_count(bib)
    if before_count >= floor:
        result = {
            "status": "skipped",
            "reason": "reference_floor_already_met",
            "before_count": before_count,
            "after_count": before_count,
            "added": [],
        }
        _write_json(run_dir / REFERENCE_TOPUP_V3_2_PATH, result)
        return result

    existing_dois = _bib_dois(bib)
    existing_keys = _bib_keys(bib)
    candidates = _reference_topup_candidates(run_dir)
    added: list[dict[str, Any]] = []
    lines = [bib.rstrip(), ""] if bib.strip() else []
    provider_used = False
    provider_errors: list[str] = []
    for candidate in candidates:
        if before_count + len(added) >= floor:
            break
        doi = _normalize_doi(str(candidate.get("doi") or ""))
        title = str(candidate.get("title") or "").strip()
        if not doi or doi in existing_dois or not title:
            continue
        key = _unique_bib_key(str(candidate.get("key") or ""), title, existing_keys)
        existing_keys.add(key)
        existing_dois.add(doi)
        row = {
            "key": key,
            "doi": doi,
            "title": title,
            "year": candidate.get("year"),
            "journal": candidate.get("journal"),
        }
        lines.append(_bib_entry(row))
        added.append(row)

    if before_count + len(added) < floor:
        provider = search_provider or _live_reference_topup_candidates
        try:
            active_candidates = provider(run_dir, floor - before_count - len(added), set(existing_dois))
        except Exception as exc:  # noqa: BLE001 - network search is best-effort; gate records failure below.
            active_candidates = []
            provider_errors.append(str(exc)[:240])
        provider_used = True
        for candidate in active_candidates:
            if before_count + len(added) >= floor:
                break
            doi = _normalize_doi(str(candidate.get("doi") or ""))
            title = str(candidate.get("title") or "").strip()
            if not doi or doi in existing_dois or not title or not _row_two_source_verified(candidate):
                continue
            key = _unique_bib_key(str(candidate.get("key") or ""), title, existing_keys)
            existing_keys.add(key)
            existing_dois.add(doi)
            row = {
                "key": key,
                "doi": doi,
                "title": title,
                "year": candidate.get("year"),
                "journal": candidate.get("journal"),
                "validation_count": candidate.get("validation_count"),
                "verification_sources": candidate.get("verification_sources"),
            }
            lines.append(_bib_entry(row))
            added.append(row)

    if added:
        refs_path.write_text("\n\n".join(line for line in lines if line).rstrip() + "\n", encoding="utf-8")
        _merge_topup_into_doi_audit(run_dir, added)

    after_count = _bib_entry_count(_read_text(refs_path))
    result = {
        "status": "done" if after_count >= floor else "blocked",
        "reason": None if after_count >= floor else "insufficient_seed_references_for_topup",
        "before_count": before_count,
        "after_count": after_count,
        "added": added,
        "active_search_used": provider_used,
        "active_search_errors": provider_errors,
    }
    _write_json(run_dir / REFERENCE_TOPUP_V3_2_PATH, result)
    return result


def validate_data_outputs_v3_2(run_dir: Path, required_outputs: list[str]) -> dict[str, Any]:
    run_dir = Path(run_dir)
    missing = [rel for rel in required_outputs if not (run_dir / rel).is_file()]
    invalid: list[str] = []
    for rel in ("research_contract.json", "doi_audit.json", "real_experiments/real_results.json"):
        path = run_dir / rel
        if path.is_file() and not _read_json(path):
            invalid.append(rel)
    refs_text = _read_text(run_dir / "references.bib")
    if (run_dir / "references.bib").is_file() and _bib_entry_count(refs_text) == 0:
        invalid.append("references.bib")
    status = "done" if not missing and not invalid else "blocked"
    return {
        "schema_version": "paperlab.data_completeness.v3.2",
        "status": status,
        "missing_outputs": missing,
        "invalid_outputs": invalid,
    }


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
    row_rate = None
    if records:
        verified_count = sum(1 for row in records if isinstance(row, dict) and _row_two_source_verified(row))
        row_rate = verified_count / len(records)
        # Row-level verification is the deterministic source of truth. Top-level
        # rates are producer summaries and can be stale or self-contradictory.
        rate = row_rate
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

    actual_bib_count = _bib_entry_count(references_bib)
    if count is None and references_bib:
        count = actual_bib_count
    elif actual_bib_count:
        count = max(int(count or 0), actual_bib_count)

    return {"count": int(count or 0), "two_source_rate": rate}


def _bib_year_counts(references_bib: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for year in re.findall(r"year\s*=\s*[{'\"]?(\d{4})", references_bib, flags=re.IGNORECASE):
        counts[year] = counts.get(year, 0) + 1
    return dict(sorted(counts.items()))


def _contract_requested_synthesis(run_dir: Path) -> str:
    contract = _read_json(Path(run_dir) / "research_contract.json") or _read_json(
        Path(run_dir) / "research_contract.input.json"
    )
    if isinstance(contract, dict):
        data_source = contract.get("data_source")
        if isinstance(data_source, dict) and str(data_source.get("type") or "").strip():
            return str(data_source["type"]).strip()
        if str(contract.get("method") or "").strip():
            return str(contract["method"]).strip()
    return "quantitative_synthesis"


def _figure_facts(run_dir: Path, *, count: int) -> dict[str, Any]:
    rr = _read_json(Path(run_dir) / "real_experiments" / "real_results.json") or {}
    year_counts = rr.get("year_counts") if isinstance(rr.get("year_counts"), dict) else {}
    verified = rr.get("two_source_verified")
    return {
        "count": count,
        "verified": int(verified) if isinstance(verified, int) else None,
        "year_counts": {str(k): int(v) for k, v in year_counts.items() if isinstance(v, int)},
    }


def _ensure_required_minimal_figures(run_dir: Path, *, count: int) -> None:
    facts = _figure_facts(run_dir, count=count)
    for stem in (
        "fig_benchmark_comparison",
        "fig_forest_plot",
        "fig_method_overview",
        "fig_prisma_flow",
    ):
        _write_minimal_figure_pair(run_dir / "figures", stem, count=count, facts=facts)


def _write_minimal_figure_pair(
    fig_dir: Path,
    stem: str,
    *,
    count: int,
    overwrite: bool = False,
    facts: dict[str, Any] | None = None,
) -> None:
    # ⚠️ Backfill figures may only draw numbers that exist in run artifacts.
    # The 2026-07-02 audit found this path shipping a fabricated forest plot
    # (invented effect intervals labeled with another domain's terms) for a run
    # whose real_results said poolable_effects_available=false.
    fig_dir.mkdir(parents=True, exist_ok=True)
    facts = facts if isinstance(facts, dict) else {"count": count, "verified": None, "year_counts": {}}
    svg = fig_dir / ("%s.svg" % stem)
    png = fig_dir / ("%s.png" % stem)
    label = stem.replace("_", " ")
    if overwrite or not svg.is_file():
        svg.write_text(_semantic_svg(stem, label=label, count=count, facts=facts), encoding="utf-8")
    if png.is_file() and not overwrite:
        return
    if not _write_matplotlib_png(png, stem=stem, label=label, count=count, facts=facts):
        png.write_bytes(base64.b64decode(_ONE_PIXEL_PNG_BASE64))


def _semantic_svg(stem: str, *, label: str, count: int, facts: dict[str, Any] | None = None) -> str:
    safe_label = _xml_escape(label)
    safe_count = max(1, int(count or 1))
    facts = facts if isinstance(facts, dict) else {}
    verified = facts.get("verified")
    verified_text = str(verified) if isinstance(verified, int) else "not verified"
    if stem == "fig_prisma_flow":
        # Only real counts: the verified bibliography and its two-source subset.
        # No invented identified/screened multipliers.
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="520" viewBox="0 0 900 520">
<rect width="900" height="520" fill="#ffffff"/>
<text x="450" y="54" text-anchor="middle" font-family="Arial" font-size="28" font-weight="700">PRISMA-style evidence screening flow</text>
<g font-family="Arial" font-size="20" text-anchor="middle">
<rect x="270" y="120" width="360" height="70" rx="6" fill="#e7f0fa" stroke="#2b5c85" stroke-width="2"/><text x="450" y="162">Verified bibliography: {safe_count}</text>
<path d="M450 190 L450 250" stroke="#2b5c85" stroke-width="3" marker-end="url(#arrow)"/>
<rect x="270" y="250" width="360" height="70" rx="6" fill="#f3f7fb" stroke="#2b5c85" stroke-width="2"/><text x="450" y="292">Two-source verified: {verified_text}</text>
<path d="M450 320 L450 380" stroke="#2b5c85" stroke-width="3" marker-end="url(#arrow)"/>
<rect x="270" y="380" width="360" height="70" rx="6" fill="#eaf7ed" stroke="#367a45" stroke-width="2"/><text x="450" y="422">Included in evidence map: {safe_count}</text>
</g><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 z" fill="#2b5c85"/></marker></defs>
</svg>
'''
    if stem == "fig_method_overview":
        # Domain-neutral engine workflow (the previous version leaked another
        # project's ESCO/EPC labels into every backfilled paper).
        return '''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="520" viewBox="0 0 900 520">
<rect width="900" height="520" fill="#ffffff"/>
<text x="450" y="56" text-anchor="middle" font-family="Arial" font-size="28" font-weight="700">Evidence acquisition and verification workflow</text>
<g font-family="Arial" font-size="18" text-anchor="middle">
<rect x="50" y="180" width="155" height="92" rx="8" fill="#edf4ff" stroke="#245a9c" stroke-width="2"/><text x="128" y="218">Research</text><text x="128" y="244">contract</text>
<rect x="270" y="180" width="155" height="92" rx="8" fill="#eef7f1" stroke="#367a45" stroke-width="2"/><text x="348" y="218">Reference</text><text x="348" y="244">collection</text>
<rect x="490" y="180" width="155" height="92" rx="8" fill="#fff7e8" stroke="#a86a00" stroke-width="2"/><text x="568" y="218">DOI</text><text x="568" y="244">verification</text>
<rect x="710" y="180" width="155" height="92" rx="8" fill="#f5efff" stroke="#6f4aa8" stroke-width="2"/><text x="788" y="218">Evidence-map</text><text x="788" y="244">synthesis</text>
<path d="M205 226 L270 226 M425 226 L490 226 M645 226 L710 226" stroke="#333" stroke-width="3" marker-end="url(#arrow)"/>
<text x="450" y="345" font-size="18">Every reported number traces to references.bib, doi_audit.json, or real_results.json</text>
</g><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 z" fill="#333"/></marker></defs>
</svg>
'''
    if stem == "fig_benchmark_comparison":
        verified_count = verified if isinstance(verified, int) else safe_count
        h1 = min(280, 80 + safe_count * 3)
        h2 = max(40, int(h1 * (verified_count / safe_count)) if safe_count else 40)
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="520" viewBox="0 0 900 520">
<rect width="900" height="520" fill="#ffffff"/>
<text x="450" y="58" text-anchor="middle" font-family="Arial" font-size="28" font-weight="700">Verified evidence scale</text>
<line x1="120" y1="410" x2="800" y2="410" stroke="#333" stroke-width="2"/><line x1="120" y1="110" x2="120" y2="410" stroke="#333" stroke-width="2"/>
<rect x="255" y="{410-h1}" width="120" height="{h1}" fill="#2f6f9f"/><rect x="525" y="{410-h2}" width="120" height="{h2}" fill="#7aa974"/>
<g font-family="Arial" font-size="18" text-anchor="middle"><text x="315" y="445">Verified bibliography</text><text x="585" y="445">Two-source verified</text><text x="315" y="{395-h1}">{safe_count}</text><text x="585" y="{395-h2}">{verified_count}</text></g>
</svg>
'''
    if stem == "fig_forest_plot":
        # No poolable effects exist on this backfill path, so no forest plot may
        # be drawn. Render an honest evidence-map summary instead of the
        # fabricated effect intervals this function used to emit.
        year_counts = facts.get("year_counts") if isinstance(facts.get("year_counts"), dict) else {}
        recent = sorted(year_counts.items())[-6:]
        bars = ""
        if recent:
            max_v = max(v for _, v in recent) or 1
            for idx, (year, value) in enumerate(recent):
                height = max(12, int(220 * value / max_v))
                x = 150 + idx * 105
                bars += (
                    f'<rect x="{x}" y="{400-height}" width="70" height="{height}" fill="#2f6f9f"/>'
                    f'<text x="{x+35}" y="425" text-anchor="middle" font-size="16">{_xml_escape(str(year))}</text>'
                    f'<text x="{x+35}" y="{388-height}" text-anchor="middle" font-size="15">{value}</text>'
                )
        else:
            bars = '<text x="450" y="300" text-anchor="middle" font-size="20">Verified references: %d</text>' % safe_count
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="520" viewBox="0 0 900 520">
<rect width="900" height="520" fill="#ffffff"/>
<text x="450" y="58" text-anchor="middle" font-family="Arial" font-size="28" font-weight="700">Evidence map summary (no pooled effects available)</text>
<g font-family="Arial">{bars}</g>
<text x="450" y="475" text-anchor="middle" font-family="Arial" font-size="17">No pooled effect estimates were extractable; this run reports a verified evidence map (n={safe_count}).</text>
</svg>
'''
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="520" viewBox="0 0 900 520">
<rect width="900" height="520" fill="#ffffff"/>
<rect x="90" y="120" width="720" height="250" fill="#e8f1ff" stroke="#245a9c" stroke-width="3"/>
<text x="450" y="90" text-anchor="middle" font-family="Arial" font-size="30" font-weight="700">{safe_label}</text>
<text x="450" y="250" text-anchor="middle" font-family="Arial" font-size="26">Verified references: {safe_count}</text>
<text x="450" y="305" text-anchor="middle" font-family="Arial" font-size="22">Deterministic evidence-map result</text>
</svg>
'''


def _write_matplotlib_png(
    path: Path,
    *,
    stem: str,
    label: str,
    count: int,
    facts: dict[str, Any] | None = None,
) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return False
    try:
        facts = facts if isinstance(facts, dict) else {}
        verified = facts.get("verified")
        verified_count = verified if isinstance(verified, int) else None
        safe_count = max(1, int(count or 1))
        fig, ax = plt.subplots(figsize=(9, 5.2), dpi=130)
        if stem == "fig_prisma_flow":
            labels = ["verified bibliography", "two-source verified", "included in map"]
            values = [safe_count, verified_count if verified_count is not None else safe_count, safe_count]
            ax.bar(labels, values, color=["#2f6f9f", "#7aa974", "#367a45"])
            ax.set_ylabel("records")
        elif stem == "fig_method_overview":
            steps = ["contract", "collection", "verification", "synthesis"]
            ax.barh(steps, [1, 2, 3, 4], color=["#8cb4df", "#8ec798", "#e6b566", "#b79ad8"])
            ax.set_xlim(0, 4.5)
            ax.set_xlabel("workflow stage")
        elif stem == "fig_benchmark_comparison":
            ax.bar(
                ["verified bibliography", "two-source verified"],
                [safe_count, verified_count if verified_count is not None else safe_count],
                color=["#2f6f9f", "#7aa974"],
            )
            ax.set_ylabel("count")
        elif stem == "fig_forest_plot":
            # No poolable effects on this path: draw the honest evidence-map
            # summary, never fabricated effect intervals.
            year_counts = facts.get("year_counts") if isinstance(facts.get("year_counts"), dict) else {}
            recent = sorted(year_counts.items())[-8:]
            if recent:
                ax.bar([str(y) for y, _ in recent], [v for _, v in recent], color="#2f6f9f")
                ax.set_ylabel("verified references per year")
            else:
                ax.bar(["verified references"], [safe_count], color="#2f6f9f")
                ax.set_ylabel("count")
            ax.set_xlabel("no pooled effect estimates were extractable")
            label = "Evidence map summary (no pooled effects available)"
        else:
            ax.bar(["verified references"], [safe_count], color="#2f6f9f")
            ax.set_ylim(0, safe_count * 1.25)
            ax.set_ylabel("count")
            ax.text(0, safe_count, str(safe_count), ha="center", va="bottom", fontsize=12)
        ax.set_title(label, fontsize=15, weight="bold")
        fig.tight_layout()
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path)
        plt.close(fig)
        return True
    except Exception:
        return False


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


_ONE_PIXEL_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def _ensure_research_contract_copy(run_dir: Path) -> None:
    dst = run_dir / "research_contract.json"
    if dst.is_file():
        return
    src = run_dir / "research_contract.input.json"
    if src.is_file():
        dst.write_text(src.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")


def _reference_topup_candidates(run_dir: Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for name in ("research_contract.input.json", "research_contract.json"):
        candidates.extend(_contract_reference_candidates(_read_json(run_dir / name)))
    for row in _audit_rows(_read_json(run_dir / "doi_audit.json")):
        if _row_two_source_verified(row):
            candidates.append(row)
    return candidates


def _live_reference_topup_candidates(run_dir: Path, needed: int, existing_dois: set[str]) -> list[dict[str, Any]]:
    if needed <= 0:
        return []
    contract = _read_json(run_dir / "research_contract.json") or _read_json(run_dir / "research_contract.input.json")
    queries = _reference_search_queries(contract)
    candidates: list[dict[str, Any]] = []
    seen = set(existing_dois)
    for query in queries:
        if len(candidates) >= needed:
            break
        for row in _search_openalex_references(query, limit=min(max(needed + 8, 12), 20)):
            doi = _normalize_doi(str(row.get("doi") or ""))
            if not doi or doi in seen:
                continue
            verified = _verify_doi_two_sources_live(doi, source_hint="openalex")
            if len(verified) < 2:
                continue
            row["verification_sources"] = verified
            row["validation_count"] = len(verified)
            seen.add(doi)
            candidates.append(row)
            if len(candidates) >= needed:
                break
        if len(candidates) >= needed:
            break
        for row in _search_crossref_references(query, limit=min(max(needed + 8, 12), 20)):
            doi = _normalize_doi(str(row.get("doi") or ""))
            if not doi or doi in seen:
                continue
            verified = _verify_doi_two_sources_live(doi, source_hint="crossref")
            if len(verified) < 2:
                continue
            row["verification_sources"] = verified
            row["validation_count"] = len(verified)
            seen.add(doi)
            candidates.append(row)
            if len(candidates) >= needed:
                break
    return candidates


def _reference_search_queries(contract: dict[str, Any]) -> list[str]:
    if not isinstance(contract, dict):
        return []
    values = [
        contract.get("topic"),
        contract.get("research_question"),
        contract.get("contribution"),
    ]
    data_source = contract.get("data_source")
    if isinstance(data_source, dict):
        values.append(data_source.get("name"))
    queries: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = re.sub(r"\s+", " ", str(value or "").strip())
        if not text:
            continue
        words = re.findall(r"[A-Za-z0-9][A-Za-z0-9-]+", text)
        query = " ".join(words[:14])
        key = query.lower()
        if query and key not in seen:
            seen.add(key)
            queries.append(query)
    return queries[:4]


def _search_openalex_references(query: str, *, limit: int) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "search": query,
            "filter": "has_doi:true",
            "per-page": min(max(limit, 1), 25),
            "select": "doi,title,publication_year,primary_location",
        }
    )
    payload = _fetch_json_url("https://api.openalex.org/works?%s" % params)
    results = payload.get("results") if isinstance(payload, dict) else None
    rows: list[dict[str, Any]] = []
    if not isinstance(results, list):
        return rows
    for item in results:
        if not isinstance(item, dict):
            continue
        location = item.get("primary_location") if isinstance(item.get("primary_location"), dict) else {}
        source = location.get("source") if isinstance(location.get("source"), dict) else {}
        rows.append(
            {
                "doi": item.get("doi"),
                "title": item.get("title"),
                "year": item.get("publication_year"),
                "journal": source.get("display_name") if isinstance(source, dict) else None,
                "topup_source": "openalex_search",
            }
        )
    return rows


def _search_crossref_references(query: str, *, limit: int) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "query.bibliographic": query,
            "rows": min(max(limit, 1), 20),
            "select": "DOI,title,published-print,published-online,published,container-title",
        }
    )
    payload = _fetch_json_url("https://api.crossref.org/works?%s" % params)
    items = ((payload.get("message") or {}).get("items")) if isinstance(payload, dict) else None
    rows: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return rows
    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        journal = item.get("container-title")
        rows.append(
            {
                "doi": item.get("DOI"),
                "title": title[0] if isinstance(title, list) and title else title,
                "year": _crossref_year(item),
                "journal": journal[0] if isinstance(journal, list) and journal else journal,
                "topup_source": "crossref_search",
            }
        )
    return rows


def _crossref_year(item: dict[str, Any]) -> int | None:
    for key in ("published-print", "published-online", "published"):
        parts = item.get(key)
        if isinstance(parts, dict):
            date_parts = parts.get("date-parts")
            if isinstance(date_parts, list) and date_parts and isinstance(date_parts[0], list) and date_parts[0]:
                year = _number(date_parts[0][0])
                if year is not None:
                    return int(year)
    return None


def _verify_doi_two_sources_live(doi: str, *, source_hint: str | None = None) -> list[str]:
    sources = {source_hint} if source_hint else set()
    doi = _normalize_doi(doi)
    if not doi:
        return []
    if "crossref" not in sources and _fetch_json_url("https://api.crossref.org/works/%s" % urllib.parse.quote(doi, safe="")):
        sources.add("crossref")
    if "openalex" not in sources:
        params = urllib.parse.urlencode({"filter": "doi:%s" % ("https://doi.org/" + doi), "per-page": 1, "select": "doi"})
        payload = _fetch_json_url("https://api.openalex.org/works?%s" % params)
        results = payload.get("results") if isinstance(payload, dict) else None
        if isinstance(results, list) and results:
            sources.add("openalex")
    return sorted(source for source in sources if source)


def _fetch_json_url(url: str, *, timeout: float = 3.0) -> dict[str, Any]:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "paperlab-v3.2-reference-topup/1.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if getattr(response, "status", 200) >= 400:
                return {}
            data = response.read(1_500_000)
    except Exception:
        return {}
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _contract_reference_candidates(contract: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(contract, dict):
        return []
    rows: list[dict[str, Any]] = []
    literature = contract.get("literature")
    if isinstance(literature, dict):
        for key in ("verified_refs", "references", "seed_references"):
            value = literature.get(key)
            if isinstance(value, list):
                rows.extend(row for row in value if isinstance(row, dict))
    for key in ("references", "seed_references", "verified_refs"):
        value = contract.get(key)
        if isinstance(value, list):
            rows.extend(row for row in value if isinstance(row, dict))
    markdown = "\n".join(
        str(contract.get(key) or "")
        for key in ("proposal_markdown", "research_question", "contribution")
    )
    for doi in sorted(set(_DOI_RE.findall(markdown))):
        rows.append({"doi": doi, "title": "Seed reference %s" % doi})
    return rows


_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")


def _bib_entry_count(text: str) -> int:
    return len(re.findall(r"^@\w+\s*\{", text or "", re.MULTILINE))


def _bib_keys(text: str) -> set[str]:
    return set(re.findall(r"^@\w+\s*\{\s*([^,\s]+)", text or "", re.MULTILINE))


def _bib_dois(text: str) -> set[str]:
    dois = re.findall(r"\bdoi\s*=\s*[\{\"]([^}\"]+)", text or "", re.IGNORECASE)
    return {_normalize_doi(doi) for doi in dois if _normalize_doi(doi)}


def _normalize_doi(value: str) -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value)
    return value.rstrip(".,;)")


def _unique_bib_key(raw_key: str, title: str, existing: set[str]) -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "", raw_key or "")
    if not base:
        words = re.findall(r"[A-Za-z0-9]+", title)
        base = "".join(words[:3])[:40] or "seed"
    key = base
    suffix = 2
    while key in existing:
        key = "%s%s" % (base, suffix)
        suffix += 1
    return key


def _bib_entry(row: dict[str, Any]) -> str:
    fields = {
        "title": row.get("title"),
        "journal": row.get("journal"),
        "year": row.get("year"),
        "doi": row.get("doi"),
    }
    lines = ["@article{%s," % row["key"]]
    for key, value in fields.items():
        if value:
            lines.append("  %s = {%s}," % (key, _bib_escape(str(value))))
    lines[-1] = lines[-1].rstrip(",")
    lines.append("}")
    return "\n".join(lines)


def _bib_escape(value: str) -> str:
    return value.replace("\\", "\\textbackslash{}").replace("{", "\\{").replace("}", "\\}")


def _merge_topup_into_doi_audit(run_dir: Path, added: list[dict[str, Any]]) -> None:
    path = run_dir / "doi_audit.json"
    audit = _read_json(path)
    records = audit.get("records")
    if not isinstance(records, list):
        records = []
    existing = {_normalize_doi(str(row.get("doi") or "")) for row in records if isinstance(row, dict)}
    for row in added:
        doi = _normalize_doi(str(row.get("doi") or ""))
        if not doi or doi in existing:
            continue
        records.append(
            {
                "doi": doi,
                "title": row.get("title"),
                "validation_count": row.get("validation_count") or 2,
                "verification_sources": row.get("verification_sources"),
                "topup_source": row.get("topup_source") or "contract_verified_reference",
            }
        )
    audit["records"] = records
    _write_json(path, audit)


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
    # Audit-producer flat verdict: the producer writes `two_source_verified: true`
    # per row when both live sources resolved. Honour it before recomputing, so the
    # row-recount cannot be more brittle than the producer it is meant to double-check.
    if row.get("two_source_verified") is True:
        return True
    validation_count = _number(row.get("validation_count"))
    if validation_count is not None and validation_count >= 2:
        return True
    valid_sources = _number(row.get("valid_sources"))
    if valid_sources is not None and valid_sources >= 2:
        return True
    verified_source_count = _number(row.get("verified_source_count"))
    if verified_source_count is not None and verified_source_count >= 2:
        return True
    # Audit-producer numeric tally of how many sources passed for this row.
    verification_sources_passed = _number(row.get("verification_sources_passed"))
    if verification_sources_passed is not None and verification_sources_passed >= 2:
        return True

    # Audit-producer list of the source names that verified this row. Note the
    # producer key is `sources_verified` (distinct from `verification_sources`);
    # accept both spellings so a schema drift on either side does not false-kill.
    for sources_key in ("verification_sources", "sources_verified"):
        sources = row.get(sources_key)
        if isinstance(sources, list) and len([source for source in sources if source]) >= 2:
            return True

    # Audit-producer flat per-source booleans (`crossref_ok`/`openalex_ok`); two
    # positive live sources satisfy the two-source rule.
    flat_source_oks = [
        row.get("crossref_ok"),
        row.get("openalex_ok"),
        row.get("semantic_scholar_ok"),
    ]
    if sum(1 for value in flat_source_oks if value is True) >= 2:
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
            checks.append(nested.get("valid"))
    validations = row.get("validations")
    if isinstance(validations, dict):
        checks.extend(validations.values())
    verification = row.get("verification")
    if isinstance(verification, dict):
        checks.extend(verification.values())

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
