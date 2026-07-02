from __future__ import annotations

import json
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path

from engine_v3 import review_provenance
from typing import Any, Mapping


REQUIRED_PHASES = {
    "data",
    "gap",
    "structure",
    "write",
    "claim_evidence",
    "render_gates",
    "review_heal",
    "format_repair",
}
REQUIRED_REVIEW_DIMENSIONS = {
    "academic_rigor",
    "novelty_positioning",
    "experimental_completeness",
    "writing_quality",
    "practical_feasibility",
    "citation_accuracy",
    "format_compliance",
}
REQUIRED_DELIVERY_FILES = {
    "artifact_manifest.json",
    "dossier.v3.json",
    "paper_draft_v0.pdf",
    "quality_review_round1.json",
    "quality_review_log.md",
}
# Size is only a corruption guard. Delivery quality is validated by Gate Z
# (citations resolved, sections numbered, tables checked), not by byte size.
MIN_PDF_BYTES = 50_000


@dataclass(frozen=True)
class AcceptanceDecision:
    status: str
    passed: bool
    reason: str
    findings: list[str]
    checks: dict[str, bool]
    floor_100: float | None
    delivery: str

    def to_public_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_run_acceptance(
    run_dir: Path,
    *,
    dossier: Mapping[str, Any] | Any | None = None,
    min_floor: float = 80.0,
) -> AcceptanceDecision:
    run_dir = Path(run_dir)
    dossier_data = _dossier_mapping(dossier) if dossier is not None else _read_json(run_dir / "dossier.v3.json")
    findings: list[str] = []
    if not dossier_data:
        return _decision(
            "failed_repairable",
            False,
            "missing or invalid dossier",
            ["missing or invalid dossier.v3.json"],
            _empty_checks(),
            None,
            "",
        )

    phases_ok, phase_findings = _validate_phases(dossier_data)
    findings.extend(phase_findings)
    gates_ok, gate_findings = _validate_gates(dossier_data)
    findings.extend(gate_findings)
    review_ok, floor_100, delivery, review_findings = _validate_review(run_dir, min_floor=min_floor)
    findings.extend(review_findings)
    manifest_ok, manifest_findings = _validate_manifest(run_dir, dossier_data)
    findings.extend(manifest_findings)
    pdf_ok, pdf_findings = _validate_pdf_contract(run_dir, dossier_data)
    findings.extend(pdf_findings)

    checks = {
        "phases_done": phases_ok,
        "gates_done": gates_ok,
        "review_ok": review_ok,
        "manifest_ok": manifest_ok,
        "pdf_ok": pdf_ok,
    }
    passed = all(checks.values())
    if passed:
        return _decision("done_pass", True, "acceptable PDF delivered", [], checks, floor_100, delivery)
    if _needs_human(dossier_data):
        return _decision(
            "failed_needs_human",
            False,
            "failed acceptance and needs human decision",
            findings,
            checks,
            floor_100,
            delivery,
        )
    return _decision(
        "failed_repairable",
        False,
        "failed acceptance and must be repaired",
        findings,
        checks,
        floor_100,
        delivery,
    )


def write_artifact_manifest(run_dir: Path, dossier: Mapping[str, Any] | Any) -> Path:
    run_dir = Path(run_dir)
    data = _dossier_mapping(dossier)
    artifacts = dict(data.get("artifacts") if isinstance(data.get("artifacts"), dict) else {})
    for rel in sorted(REQUIRED_DELIVERY_FILES - {"artifact_manifest.json", "dossier.v3.json"}):
        path = run_dir / rel
        if rel not in artifacts and path.is_file():
            artifacts[rel] = {"path": rel, "sha256": _hash_file(path)}
    manifest = {
        "schema_version": "paperlab.artifact_manifest.v3.2",
        "job_id": data.get("job_id"),
        "domain": data.get("domain"),
        "generated_from": "dossier.v3.json",
        "artifacts": artifacts,
    }
    path = run_dir / "artifact_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def _decision(
    status: str,
    passed: bool,
    reason: str,
    findings: list[str],
    checks: dict[str, bool],
    floor_100: float | None,
    delivery: str,
) -> AcceptanceDecision:
    return AcceptanceDecision(
        status=status,
        passed=passed,
        reason=reason,
        findings=findings,
        checks=checks,
        floor_100=floor_100,
        delivery=delivery,
    )


def _empty_checks() -> dict[str, bool]:
    return {
        "phases_done": False,
        "gates_done": False,
        "review_ok": False,
        "manifest_ok": False,
        "pdf_ok": False,
    }


def _validate_phases(dossier: Mapping[str, Any]) -> tuple[bool, list[str]]:
    findings: list[str] = []
    phases = dossier.get("phases") if isinstance(dossier.get("phases"), dict) else {}
    missing = sorted(REQUIRED_PHASES - set(phases))
    non_done = sorted(phase for phase in REQUIRED_PHASES if phases.get(phase) != "done")
    if missing:
        findings.append("missing phases: %s" % ", ".join(missing))
    if non_done:
        findings.append("non-done phases: %s" % ", ".join("%s=%s" % (p, phases.get(p)) for p in non_done))
    return not missing and not non_done, findings


def _validate_gates(dossier: Mapping[str, Any]) -> tuple[bool, list[str]]:
    findings: list[str] = []
    latest = _latest_gate_reports_by_phase(dossier)
    for phase in ("claim_evidence", "render_gates", "review_heal", "format_repair"):
        report = latest.get(phase)
        if not report:
            findings.append("missing latest gate report for %s" % phase)
            continue
        if report.get("blocked"):
            findings.append("latest gate report blocked for %s: %s" % (phase, report.get("failed_blocks")))
    z_validation = _z_pdf_validation(dossier)
    if not isinstance(z_validation, dict):
        findings.append("Z gate delivery PDF validation missing")
    elif not z_validation.get("valid"):
        z_findings = z_validation.get("findings") if isinstance(z_validation.get("findings"), list) else []
        findings.append("Z gate delivery PDF validation failed: %s" % ("; ".join(str(item) for item in z_findings) or "invalid"))
    return not findings, findings


def _validate_review(run_dir: Path, *, min_floor: float) -> tuple[bool, float | None, str, list[str]]:
    findings: list[str] = []
    review = _read_json(run_dir / "quality_review_round1.json")
    if not isinstance(review, dict):
        return False, None, "", ["missing or invalid quality_review_round1.json"]

    delivery = str(review.get("delivery") or "").lower()
    floor = review.get("floor_100")
    floor_100 = float(floor) if isinstance(floor, (int, float)) and not isinstance(floor, bool) else None
    if delivery not in {"pass", "passed", "ok"}:
        findings.append("review delivery is not pass: %s" % (delivery or None))
    if floor_100 is None or floor_100 < min_floor:
        findings.append("review floor_100 below %.1f: %s" % (min_floor, floor))
    if int(review.get("p0_count") or 0) != 0:
        findings.append("review p0_count is not zero")

    loop = review.get("review_loop") if isinstance(review.get("review_loop"), dict) else {}
    # Function-level import: engine_v3.packs.__init__ -> packs.paper ->
    # engine_v3.core.dossier imports this module back (write_artifact_manifest),
    # so a module-level import here would be a circular import.
    from engine_v3.packs import paper_artifacts

    findings.extend(review_provenance.validate_review_artifacts(
        run_dir,
        review_file=paper_artifacts.REVIEW_FILE,
        review_log_file=paper_artifacts.REVIEW_LOG_FILE,
        manuscript_files=paper_artifacts.MANUSCRIPT_FILES,
    ))
    if loop.get("independent_reviewer") is not True:
        findings.append("review_loop.independent_reviewer must be boolean true")
    if str(loop.get("status") or "").lower() not in {"pass", "passed", "ok", "done"}:
        findings.append("review_loop.status is not pass-like: %s" % loop.get("status"))

    dimensions = review.get("dimensions") if isinstance(review.get("dimensions"), dict) else {}
    missing_dimensions = sorted(REQUIRED_REVIEW_DIMENSIONS - set(dimensions))
    if missing_dimensions:
        findings.append("missing review dimensions: %s" % ", ".join(missing_dimensions))
    for key in sorted(REQUIRED_REVIEW_DIMENSIONS & set(dimensions)):
        value = dimensions.get(key)
        score = value.get("score") if isinstance(value, dict) else value
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            findings.append("dimension score is not numeric: %s" % key)
        elif score < 0 or score > 10:
            findings.append("dimension score outside 0-10: %s=%s" % (key, score))

    log = run_dir / "quality_review_log.md"
    if not log.is_file() or log.stat().st_size < 500:
        findings.append("quality_review_log.md missing or too small")
    return not findings, floor_100, delivery, findings


def _validate_manifest(run_dir: Path, dossier: Mapping[str, Any]) -> tuple[bool, list[str]]:
    findings: list[str] = []
    for rel in sorted(REQUIRED_DELIVERY_FILES):
        if not (run_dir / rel).is_file():
            findings.append("%s missing" % rel)
    manifest = _read_json(run_dir / "artifact_manifest.json")
    if not isinstance(manifest, dict):
        return False, findings
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    indexed = dossier.get("artifacts") if isinstance(dossier.get("artifacts"), dict) else {}
    for required in ("paper_draft_v0.pdf", "quality_review_round1.json", "quality_review_log.md"):
        if required not in artifacts and required not in indexed:
            findings.append("%s missing from artifact manifest" % required)
    return not findings, findings


def _validate_pdf_contract(run_dir: Path, dossier: Mapping[str, Any]) -> tuple[bool, list[str]]:
    findings: list[str] = []
    pdf = run_dir / "paper_draft_v0.pdf"
    artifacts = dossier.get("artifacts") if isinstance(dossier.get("artifacts"), dict) else {}
    if "paper_draft_v0.pdf" not in artifacts:
        findings.append("paper_draft_v0.pdf missing from artifact index")
    if not pdf.is_file():
        findings.append("paper_draft_v0.pdf missing")
        return False, findings
    if pdf.stat().st_size < MIN_PDF_BYTES:
        findings.append("paper_draft_v0.pdf too small: %s" % pdf.stat().st_size)
    try:
        if not pdf.read_bytes()[:5] == b"%PDF-":
            findings.append("paper_draft_v0.pdf does not start with a PDF header")
    except OSError as exc:
        findings.append("paper_draft_v0.pdf is unreadable: %s" % exc)

    validation = _z_pdf_validation(dossier)
    if not isinstance(validation, dict):
        findings.append("Z gate delivery PDF validation missing")
        return False, findings
    if validation.get("valid") is not True:
        findings.extend(str(item) for item in validation.get("findings") or [])
    if validation.get("raw_citation_count") not in {0, 0.0}:
        findings.append("PDF raw citation count is not zero: %s" % validation.get("raw_citation_count"))
    if validation.get("unresolved_marker_count") not in {0, 0.0}:
        findings.append("PDF unresolved marker count is not zero: %s" % validation.get("unresolved_marker_count"))
    if validation.get("numbered_section_detected") is not True:
        findings.append("PDF numbered sections not detected")
    table_widths = validation.get("table_widths") if isinstance(validation.get("table_widths"), dict) else {}
    if table_widths.get("valid") is not True:
        findings.extend(str(item) for item in table_widths.get("findings") or [])
        if not table_widths.get("findings"):
            findings.append("PDF table width validation did not pass")
    content_quality = validation.get("content_quality") if isinstance(validation.get("content_quality"), dict) else {}
    if content_quality.get("valid") is not True:
        findings.extend(str(item) for item in content_quality.get("findings") or [])
        if not content_quality.get("findings"):
            findings.append("PDF content-quality validation missing")
    return not findings, findings


def _latest_gate_reports_by_phase(dossier: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    reports = dossier.get("gate_reports")
    if not isinstance(reports, list):
        return latest
    for report in reports:
        if isinstance(report, dict) and isinstance(report.get("phase"), str):
            latest[report["phase"]] = report
    return latest


def _z_pdf_validation(dossier: Mapping[str, Any]) -> dict[str, Any] | None:
    for report in reversed(dossier.get("gate_reports") or []):
        if not isinstance(report, dict):
            continue
        for result in report.get("results") or []:
            if not isinstance(result, dict) or result.get("gate_id") != "Z":
                continue
            evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
            validation = evidence.get("validation")
            return validation if isinstance(validation, dict) else None
    evidence = dossier.get("evidence") if isinstance(dossier.get("evidence"), dict) else {}
    validation = evidence.get("delivery_pdf_validation")
    return validation if isinstance(validation, dict) else None


def _needs_human(dossier: Mapping[str, Any]) -> bool:
    evidence = dossier.get("evidence") if isinstance(dossier.get("evidence"), dict) else {}
    checkpoint = evidence.get("human_checkpoint")
    if isinstance(checkpoint, dict):
        return bool(checkpoint)
    return bool(checkpoint)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _dossier_mapping(dossier: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(dossier, Mapping):
        return dict(dossier)
    artifacts = {}
    for name, ref in getattr(dossier, "artifacts", {}).items():
        artifacts[name] = {
            "path": getattr(ref, "path", ""),
            "sha256": getattr(ref, "sha256", ""),
        }
    return {
        "version": getattr(dossier, "version", 3),
        "job_id": getattr(dossier, "job_id", None),
        "domain": getattr(dossier, "domain", None),
        "phases": dict(getattr(dossier, "phases", {}) or {}),
        "artifacts": artifacts,
        "evidence": dict(getattr(dossier, "evidence", {}) or {}),
        "gate_reports": list(getattr(dossier, "gate_reports", []) or []),
        "delegations": list(getattr(dossier, "delegations", []) or []),
    }
