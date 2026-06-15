#!/usr/bin/env python3
"""paperctl — thin CLI over the deterministic engine core (DESIGN §3.4).

PURE WRAPPER: every subcommand imports an EXISTING function and calls it; no
pipeline logic is reimplemented here. Each subcommand prints a JSON result to
stdout and returns exit code 0 (pass) or nonzero (gate block / error).

    paperctl refs build-from-dois|audit --run-dir RUN
    paperctl data meta-analysis        --run-dir RUN
    paperctl figures meta              --run-dir RUN
    paperctl tables inject             --run-dir RUN
    paperctl render                    --run-dir RUN
    paperctl gate phase2|phase3|phase8|phase9|final --run-dir RUN
    paperctl review compile            --run-dir RUN
    paperctl provenance                --run-dir RUN

`main(argv=None)` is importable so tests can drive the CLI in-process
(no shelling out) and inspect/JSON-debug failures directly.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable


def _emit(payload: Any) -> None:
    """Print a JSON result to stdout (single, machine-parseable line block)."""
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def _load_contract(run_dir: Path) -> dict[str, Any]:
    """Read the run's research_contract.json (the per-run subjective inputs).

    The deterministic lanes/gates take the contract as their second argument; the
    pipeline reads it from this canonical path, so the CLI mirrors that exactly.
    """
    for name in ("research_contract.json", "contract.json"):
        path = run_dir / name
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except (json.JSONDecodeError, OSError):
                pass
    return {}


# --------------------------------------------------------------------------- #
# refs — wrap paper_driver.build_refs_from_doi_list / paper_driver.doi_gate
# --------------------------------------------------------------------------- #
def cmd_refs_build_from_dois(run_dir: Path) -> int:
    """Wrap paper_driver.build_refs_from_doi_list over the contract's DOI list.

    The candidate DOI list is the subjective chat input; a-side deterministically
    CrossRef-verifies + completes each one (the function owns that). We pull the
    candidates via the existing contract_doi_candidates helper so behaviour is
    byte-identical to the pipeline's phase-2 call.
    """
    import paper_driver

    contract = _load_contract(run_dir)
    candidates = paper_driver.contract_doi_candidates(contract)
    audit = paper_driver.build_refs_from_doi_list(run_dir, candidates)
    _emit(audit)
    return 0 if audit.get("passed") else 1


def cmd_refs_audit(run_dir: Path) -> int:
    """Wrap paper_driver.doi_gate — the Stage-4 independent CrossRef re-verify."""
    import paper_driver

    audit = paper_driver.doi_gate(run_dir)
    _emit(audit)
    return 0 if audit.get("passed") else 1


# --------------------------------------------------------------------------- #
# data — wrap paper_driver.run_meta_analysis_lane
# --------------------------------------------------------------------------- #
def cmd_data_meta_analysis(run_dir: Path) -> int:
    """Wrap paper_driver.run_meta_analysis_lane (contract from the run dir).

    The lane is deterministic over a fixed corpus: it reads run_dir/_corpus_cache.json
    when present (the pipeline collects once, then caches), so a seeded cache makes
    this offline-reproducible. Emits the slim result (drops the bulky `meta` block
    from stdout) but the full real_results.json is written to disk by the lane.
    """
    import paper_driver

    contract = _load_contract(run_dir)
    result = paper_driver.run_meta_analysis_lane(run_dir, contract)
    slim = {k: v for k, v in result.items() if k != "meta"}
    meta = result.get("meta") or {}
    slim["pooled"] = meta.get("pooled")
    slim["by_measure_counts"] = meta.get("by_measure_counts")
    _emit(slim)
    return 0 if result.get("status") == "completed" else 1


# --------------------------------------------------------------------------- #
# figures — wrap meta_figures.generate
# --------------------------------------------------------------------------- #
def cmd_figures_meta(run_dir: Path) -> int:
    """Wrap meta_figures.generate — deterministic forest/PRISMA/method figures."""
    import meta_figures

    produced = meta_figures.generate(run_dir)
    _emit({"run": run_dir.name, "figures": produced,
           "count": sum(len(v) for v in produced.values())})
    return 0 if produced else 1


# --------------------------------------------------------------------------- #
# tables — wrap tables.inject_figures (the dedup)
# --------------------------------------------------------------------------- #
def cmd_tables_inject(run_dir: Path) -> int:
    """Wrap tables.inject (GENERATED tables) + tables.inject_figures (figure dedup).

    Mirrors the pipeline render step (paper_orchestrator.render), which calls both
    in sequence. Returns the embed/replace counts; idempotent on re-run.
    """
    import tables

    contract = _load_contract(run_dir)
    tables_injected = tables.inject(run_dir, contract)
    figures_injected = tables.inject_figures(run_dir)
    _emit({"run": run_dir.name, "tables_injected": tables_injected,
           "figures_injected": figures_injected})
    return 0


# --------------------------------------------------------------------------- #
# render — wrap paper_driver.render_pdf
# --------------------------------------------------------------------------- #
def cmd_render(run_dir: Path) -> int:
    """Wrap paper_driver.render_pdf (Springer/elsarticle via Quarto, reportlab fallback)."""
    import paper_driver

    ok = paper_driver.render_pdf(run_dir)
    pdf = run_dir / "paper_draft_v0.pdf"
    _emit({"run": run_dir.name, "rendered": bool(ok),
           "pdf": str(pdf) if pdf.is_file() else None,
           "pdf_bytes": pdf.stat().st_size if pdf.is_file() else 0})
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# provenance — wrap paper_driver.write_provenance
# --------------------------------------------------------------------------- #
def cmd_provenance(run_dir: Path) -> int:
    """Wrap paper_driver.write_provenance — the reproducibility record."""
    import paper_driver

    contract = _load_contract(run_dir)
    prov = paper_driver.write_provenance(run_dir, contract)
    _emit(prov)
    return 0


# --------------------------------------------------------------------------- #
# review — wrap compile_review.compile_reviews
# --------------------------------------------------------------------------- #
def cmd_review_compile(run_dir: Path) -> int:
    """Wrap compile_review.compile_reviews — the deterministic content-gate compile."""
    import compile_review

    summary = compile_review.compile_reviews(run_dir)
    _emit(summary)
    return 0 if summary.get("meets_threshold") else 1


# --------------------------------------------------------------------------- #
# gate — wrap the deterministic gates, one verdict + exit code per phase.
# Mapping follows the pipeline's phase semantics (PAPER_PHASES / orchestrator):
#   phase2 -> doi_gate (Stage-4 DOI anti-cheat; phase-2 deliverable = references)
#   phase3 -> consistency_gate.run (claim-vs-ground-truth contradiction detector)
#   phase8 -> data_availability_gate.probe_hupd (the experiment data-source lock)
#   phase9 -> compile_review.compile_reviews (content-quality gate -> gate_report.json)
#   final  -> compile_review.compile_reviews (final content verdict; same backend)
# --------------------------------------------------------------------------- #
def _gate_doi(run_dir: Path) -> tuple[dict[str, Any], bool]:
    import paper_driver

    audit = paper_driver.doi_gate(run_dir)
    return audit, bool(audit.get("passed"))


def _gate_consistency(run_dir: Path) -> tuple[dict[str, Any], bool]:
    import consistency_gate

    payload = consistency_gate.run(run_dir)
    summary = payload.get("summary", payload)
    p0 = int(payload.get("p0_tasks", summary.get("p0_tasks", 0)) or 0)
    return payload, p0 == 0


def _gate_data_availability(run_dir: Path) -> tuple[dict[str, Any], bool]:
    import data_availability_gate

    lock = data_availability_gate.probe_hupd(run_dir)
    return lock, lock.get("status") == "available"


def _gate_content(run_dir: Path) -> tuple[dict[str, Any], bool]:
    import compile_review

    summary = compile_review.compile_reviews(run_dir)
    return summary, bool(summary.get("meets_threshold"))


_GATE_BACKENDS: dict[str, Callable[[Path], "tuple[dict[str, Any], bool]"]] = {
    "phase2": _gate_doi,
    "phase3": _gate_consistency,
    "phase8": _gate_data_availability,
    "phase9": _gate_content,
    "final": _gate_content,
}


def cmd_gate(run_dir: Path, phase: str) -> int:
    """Run the deterministic gate for `phase`; emit verdict, nonzero exit on block."""
    backend = _GATE_BACKENDS[phase]
    verdict, passed = backend(run_dir)
    _emit({"gate": phase, "run": run_dir.name, "passed": passed, "verdict": verdict})
    return 0 if passed else 1


# --------------------------------------------------------------------------- #
# argparse wiring
# --------------------------------------------------------------------------- #
def _add_run_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-dir", required=True, dest="run_dir",
                        help="run directory holding the contract + artifacts")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paperctl",
        description="Thin CLI over the deterministic engine core (refs / data / "
                    "figures / tables / render / gate / review / provenance).")
    sub = parser.add_subparsers(dest="group", metavar="<group>")

    # refs build-from-dois | audit
    refs = sub.add_parser("refs", help="bibliography: build from DOIs / re-audit")
    refs_sub = refs.add_subparsers(dest="action", metavar="<action>")
    _add_run_dir(refs_sub.add_parser("build-from-dois", help="CrossRef verify+complete the contract DOI list"))
    _add_run_dir(refs_sub.add_parser("audit", help="independent CrossRef DOI re-verification (Stage 4)"))

    # data meta-analysis
    data = sub.add_parser("data", help="run a deterministic data lane")
    data_sub = data.add_subparsers(dest="action", metavar="<action>")
    _add_run_dir(data_sub.add_parser("meta-analysis", help="abstract-level random-effects meta-analysis lane"))

    # figures meta
    figures = sub.add_parser("figures", help="generate deterministic figures")
    figures_sub = figures.add_subparsers(dest="action", metavar="<action>")
    _add_run_dir(figures_sub.add_parser("meta", help="forest + PRISMA + method-overview figures"))

    # tables inject
    tables = sub.add_parser("tables", help="splice generated tables/figures into the qmd")
    tables_sub = tables.add_subparsers(dest="action", metavar="<action>")
    _add_run_dir(tables_sub.add_parser("inject", help="inject GENERATED tables + dedup figure embeds"))

    # render
    _add_run_dir(sub.add_parser("render", help="render the journal-format PDF"))

    # gate <phase>
    gate = sub.add_parser("gate", help="run a deterministic phase gate")
    gate.add_argument("phase", choices=sorted(_GATE_BACKENDS), help="which phase gate to run")
    _add_run_dir(gate)

    # review compile
    review = sub.add_parser("review", help="compile the deterministic content review")
    review_sub = review.add_subparsers(dest="action", metavar="<action>")
    _add_run_dir(review_sub.add_parser("compile", help="merge reviews -> gate_report.json + verdict"))

    # provenance
    _add_run_dir(sub.add_parser("provenance", help="write the reproducibility record"))

    return parser


_GROUP_ACTIONS: dict[tuple[str, str | None], Callable[..., int]] = {
    ("refs", "build-from-dois"): cmd_refs_build_from_dois,
    ("refs", "audit"): cmd_refs_audit,
    ("data", "meta-analysis"): cmd_data_meta_analysis,
    ("figures", "meta"): cmd_figures_meta,
    ("tables", "inject"): cmd_tables_inject,
    ("render", None): cmd_render,
    ("review", "compile"): cmd_review_compile,
    ("provenance", None): cmd_provenance,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.group:
        parser.print_help()
        return 2

    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.is_dir():
        print(json.dumps({"error": f"run-dir not found: {run_dir}"}), file=sys.stderr)
        return 2

    if args.group == "gate":
        return cmd_gate(run_dir, args.phase)

    action = getattr(args, "action", None)
    handler = _GROUP_ACTIONS.get((args.group, action))
    if handler is None:
        # group present but missing/invalid sub-action -> show that group's help.
        parser.parse_args([args.group, "--help"])
        return 2
    try:
        return handler(run_dir)
    except Exception as exc:  # noqa: BLE001 - surface a structured error + nonzero exit
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}",
                          "group": args.group, "action": action}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
