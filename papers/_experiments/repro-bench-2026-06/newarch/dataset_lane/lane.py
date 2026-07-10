"""The general dataset-analysis lane orchestration. It drives the AGENT (brain plans,
worker codes) and the DETERMINISTIC core (fetch, runner, gates) to turn a `data_source`
of type "dataset" into a verified `real_experiments/real_results.json` that the normal
downstream phases (gap/structure/write/render) consume.

Domain-agnostic: every prompt is built from the CONTRACT (topic, question, data_source,
requested method) — this file names no dataset, column, or study. `brain(prompt, writes)`
and `worker(prompt, writes)` are injected by the pipeline (bound to the LiveDispatcher);
in tests they are stubbed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from . import fetch, gates, runner, schema

Dispatch = Callable[[str, list[str]], bool]


def _contract_brief(contract: dict[str, Any]) -> str:
    ds = contract.get("data_source") or {}
    return (
        f"Research contract:\n- Topic: {contract.get('topic')}\n"
        f"- Research question: {contract.get('research_question')}\n"
        f"- Contribution: {contract.get('contribution')}\n"
        f"- Data source: {ds.get('name')} (type={ds.get('type')}, url={ds.get('url')})\n"
        f"- Output language: {contract.get('output_language')}\n"
        "Use ONLY the real downloaded data. Never invent values. Every number you will "
        "later report in the paper must be produced by the analysis code and recorded in "
        "real_results.json.\n")


def _resolve_prompt(contract: dict[str, Any], skills: str, feedback: str = "") -> str:
    ds = contract.get("data_source") or {}
    return _contract_brief(contract) + (
        f"\nYou are the DATA-RESOLUTION brain.\n{skills}\n"
        f"Resolve the dataset at {ds.get('url')} into the ACTUAL downloadable data files "
        "needed for this study. Use your terminal to FIND and VERIFY the real file URLs — "
        "do NOT guess a URL pattern from memory (data portals change their paths). Steps: "
        "curl/read the landing page or data-files index to discover the real links; then for "
        "each candidate run `curl -sIL <url>` and KEEP IT ONLY IF it returns HTTP 200 with a "
        "binary/data content-type (NOT text/html — an HTML page is a 404, not data). "
        'Write `data/download_plan.json` = a JSON list of {"url": "<verified direct url>", '
        '"filename": "<name>"}. List ONLY URLs you verified return real data. Python downloads '
        "them; you do not." + (f"\n\nPREVIOUS ATTEMPT FAILED: {feedback} The URLs you listed did "
        "not return real data files (they 404'd to HTML). Find the CORRECT current file URLs by "
        "reading the source's actual data-files page this time." if feedback else "") +
        "\nOnly write that one file. End with CHILD_OK.")


def _feedback_block(analysis_feedback: list[dict[str, Any]] | None) -> str:
    """A PRIOR-RUN review fed back analysis-level problems (escalation ladder). The new spec
    MUST address them — they could not be fixed by editing prose."""
    items = [a for a in (analysis_feedback or []) if isinstance(a, dict) and a.get("issue")]
    if not items:
        return ""
    lines = "\n".join(f"- [{a.get('required_action') or 'fix'}] {a.get('issue')}" for a in items)
    return ("\nPRIOR-RUN ANALYSIS PROBLEMS — a reviewer flagged these about the LAST analysis; they "
            "need a CHANGED specification (not prose edits). Address each in THIS spec where the data "
            "allow (e.g. restrict the period, add a control, complete an interaction test, bound an "
            "unstable elasticity); if a fix is genuinely impossible with this dataset, say so in the "
            f"spec rationale rather than ignoring it:\n{lines}\n")


def _spec_prompt(contract: dict[str, Any], manifest: dict[str, Any], skills: str,
                 analysis_feedback: list[dict[str, Any]] | None = None) -> str:
    cols = sorted({c for a in (manifest.get("artifacts") or [])
                   for c in ((a.get("probe_sample") or {}).get("columns") or [])})
    return _contract_brief(contract) + _feedback_block(analysis_feedback) + (
        f"\nYou are the ANALYSIS-SPEC brain.\n{skills}\n"
        "The real data is downloaded (see data/manifest.json). Sample columns seen: "
        f"{cols[:80] if cols else '(binary format — open the files to discover columns)'}.\n"
        "Write `real_experiments/analysis_spec.json`: map the contract's exposures/outcomes/"
        "method to THIS dataset's real variable names; choose defensible models; and IF the "
        "dataset is a complex survey, declare survey_design = {weight_variable, "
        "strata_variable, psu_variable, design notes} using the dataset's REAL column names. "
        "Include `required_outputs` (sample_flow, weighted/unweighted n, model_results, "
        "spline_results, subgroup_results, sensitivity_results). DECLARE which model is the "
        "PRIMARY specification via `primary_model_id` (the id of the most rigorous adjusted "
        "model answering the research question — e.g. the two-way fixed-effects model with key "
        "controls, NOT a naive descriptive model); real_results.json MUST echo `primary_model_id`. "
        "The analysis MUST also emit generic `sample_flow` declarations: `analytic_units` "
        "(count of DISTINCT analytic units, e.g. countries/firms/stations/subjects/households), "
        "`unit_label` (e.g. countries, firms, stations), and when longitudinal/time-indexed "
        "`time_min`, `time_max`, and optional `time_label`; omit time fields for cross-sectional data. "
        "Keep wording consistent "
        "with the study design (e.g. cross-sectional => association/odds, not prevention). "
        "Only write that one file. End with CHILD_OK.")


def _code_prompt(contract: dict[str, Any], skills: str) -> str:
    return _contract_brief(contract) + (
        f"\nYou WRITE the analysis program.\n{skills}\n"
        "Write `real_experiments/analysis.py`. It is invoked as:\n"
        "  python analysis.py --manifest data/manifest.json "
        "--spec real_experiments/analysis_spec.json --out real_experiments/real_results.json\n"
        "It MUST: (1) read the real downloaded files listed in the manifest (pandas; handle "
        "the formats present — csv/xpt/sas7bdat/zip etc.); (2) build the analytic dataset per "
        "the spec (derive exposures/outcomes, record sample flow); (3) run the spec's models "
        "(survey-weighted with the declared weight/strata/psu when the spec declares a survey "
        "design — apply the weights, do NOT run a plain unweighted fit); (4) write "
        "real_results.json with EXACTLY: status='completed', simulated=False, "
        f"lane='{schema.LANE_NAME}', source, data_manifest_sha256 (copy manifest_sha256 from "
        "the manifest you read), rows, sample_flow, survey_design (weighted bool + the real "
        "column names + design_df + weight combination rule), variables (the columns you "
        "actually used), models (each: id, family, outcome, exposure, estimate, ci_low, "
        "ci_high, p_value, n_unweighted, n_weighted, covariates), primary_model_id (the id of "
        "the PRIMARY model from the spec — the rigorous adjusted specification, not a naive "
        "descriptive one), sample_flow declarations `analytic_units` (count of DISTINCT analytic "
        "units), `unit_label`, and when longitudinal/time-indexed `time_min`, `time_max`, and "
        "optional `time_label` (omit time fields for cross-sectional data), and numeric_index (a flat "
        "list of EVERY number you report). Print a one-line summary to stdout. Do NOT "
        "hardcode results or write numbers you did not compute. Only write that one file. "
        "End with CHILD_OK.")


def _review_prompt(contract: dict[str, Any], problems: list[dict[str, Any]], skills: str) -> str:
    """BRAIN (codex) review: diagnose the failure AND decide who should apply the fix — a
    small localized edit a non-reasoning worker can do, or a rewrite only the brain can do.
    This SCOPE call is the escalation-ladder decision (the reviewer knows if its own fix is
    worker-applicable)."""
    bullets = "\n".join(f"- [{p.get('id')}] {p.get('description')}" for p in problems)
    return _contract_brief(contract) + (
        f"\nYou are the REVIEW brain (Hermes two-layer §3.6).\n{skills}\n"
        "The deterministic gates FAILED on the worker's analysis. READ the actual files:\n"
        "- `real_experiments/analysis.py` (the code the worker wrote — may be missing/empty)\n"
        "- `real_experiments/analysis_stderr.txt` and `analysis_stdout.txt` (the run log)\n"
        "- `real_experiments/analysis_spec.json` and `data/manifest.json`\n"
        "Gate failures:\n" + bullets + "\n\n"
        "Diagnose the REAL cause (did not read the downloaded files; UNWEIGHTED fit when the "
        "spec declares a survey design; a pandas/statsmodels error in the log; a timeout from "
        "processing too much; missing real_results fields; numbers not in numeric_index).\n"
        "Write `real_experiments/fix_prescription.md`. Its FIRST LINE must be exactly one of:\n"
        "  SCOPE: small_edit   (a localized change — a non-reasoning worker can apply it)\n"
        "  SCOPE: rewrite      (the code is missing/empty or needs substantial rewriting — "
        "only a capable author should do it)\n"
        "Then a SHORT, CONCRETE prescription: the exact changes (specific functions/columns/"
        "weights/imports, or a corrected snippet). NEVER prescribe fabricating numbers or faking "
        "the result shape. Only write that one file. End with CHILD_OK.")


def _apply_prompt(contract: dict[str, Any]) -> str:
    """WORKER applies a SMALL prescribed edit to analysis.py — typing, not reasoning."""
    return _contract_brief(contract) + (
        "\nThe reviewer wrote a fix prescription at `real_experiments/fix_prescription.md` "
        "(scope: small_edit). READ it and apply EXACTLY that localized change to "
        "`real_experiments/analysis.py` — do not add your own ideas, do not fabricate numbers, "
        "keep the rest intact. Only write analysis.py. End with CHILD_OK.")


def _brain_apply_prompt(contract: dict[str, Any], skills: str) -> str:
    """BRAIN takes over and WRITES analysis.py itself — escalation when the worker can't (the
    code is missing, or the reviewer judged the fix a rewrite). The brain authored the
    prescription, so it now implements it fully and correctly."""
    return _contract_brief(contract) + (
        f"\nThe free worker could not produce a working analysis (its draft is missing/empty or "
        "the fix is a rewrite), so YOU (the capable author) now write it.\n"
        f"{skills}\nFollow your own `real_experiments/fix_prescription.md` and "
        "`real_experiments/analysis_spec.json`. Write the COMPLETE `real_experiments/analysis.py` "
        "with the fixed interface (argparse --manifest/--spec/--out): read the real downloaded "
        "files per the manifest, build the analytic dataset, run the spec's models (survey-"
        "weighted with the declared weight/strata/psu when declared), and write real_results.json "
        "with all required fields incl. data_manifest_sha256 (copied from the manifest) and "
        "numeric_index. Do NOT fabricate numbers. Only write analysis.py. End with CHILD_OK.")


def run(run_dir: Path, contract: dict[str, Any], *, brain: Dispatch, worker: Dispatch,
        skills: str = "", max_heal_rounds: int = 2,
        analysis_feedback: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Fetch -> spec -> code -> execute -> gates (+heal). Returns
    {ok, problems, real_results}. Raises nothing; the caller decides on `ok`."""
    run_dir = Path(run_dir)

    # 1. resolve + deterministic fetch (re-resolve heal if the gate rejects the data —
    # feed the specific failure back so the brain fixes the URLs instead of re-guessing)
    fetch_problems: list[dict[str, Any]] = []
    for attempt in range(3):
        feedback = "; ".join(p.get("description", "") for p in fetch_problems[:2]) if attempt else ""
        brain(_resolve_prompt(contract, skills, feedback), [schema.DOWNLOAD_PLAN])
        fetch.fetch(run_dir, contract)
        fetch_problems = gates.fetch_gate(run_dir)
        if not fetch_problems:
            break
        if attempt == 2:
            return {"ok": False, "problems": fetch_problems, "real_results": None,
                    "stage": "fetch"}

    # 2. the BRAIN reasons the SPEC (map the contract to this dataset's real variables +
    # survey design); the free WORKER drafts the analysis CODE from the spec+skills.
    manifest = schema.read_json(run_dir, schema.MANIFEST) or {}
    brain(_spec_prompt(contract, manifest, skills, analysis_feedback), [schema.ANALYSIS_SPEC])
    worker(_code_prompt(contract, skills), [schema.ANALYSIS_CODE])

    # 3. the HERMES ESCALATION LADDER (loop engineering): cheapest layer first, escalate on
    # failure, and let the BRAIN decide who applies its own fix.
    #   worker drafts -> run+gate -> on fail the brain REVIEWS + prescribes + declares SCOPE
    #   -> small_edit: the free WORKER applies it (cheap);  rewrite / empty / already-escalated:
    #   the BRAIN takes over and writes the code itself (the worker proved unable).
    problems: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []
    escalated = False
    for rnd in range(max_heal_rounds + 1):
        runner.run_analysis(run_dir)
        problems = gates.run_all(run_dir)
        if not problems:
            history.append({"round": rnd, "problem_ids": [], "applied_by": None})
            break
        if rnd >= max_heal_rounds:
            history.append({"round": rnd, "problem_ids": [p.get("id") for p in problems], "applied_by": None})
            break
        brain(_review_prompt(contract, problems, skills), [schema.FIX_PRESCRIPTION])      # review + SCOPE
        code = run_dir / schema.ANALYSIS_CODE
        code_empty = (not code.is_file()) or len(code.read_text(encoding="utf-8", errors="ignore").strip()) < 40
        # A spec-alignment failure (the code did not implement the spec — wrong primary model or
        # sample) is NOT a small worker edit: force the BRAIN to (re)write the code so the result
        # actually conforms to its own spec. Otherwise the worker can keep echoing the label.
        force_brain = any(str(p.get("id") or "").startswith("DS_SPEC_") for p in problems)
        use_brain = force_brain or escalated or code_empty or _scope(run_dir) == "rewrite"
        if use_brain:
            brain(_brain_apply_prompt(contract, skills), [schema.ANALYSIS_CODE])           # brain writes it
            escalated = True                                                               # keep it (worker unable)
            applied_by = "brain"
        else:
            worker(_apply_prompt(contract), [schema.ANALYSIS_CODE])                        # worker applies small edit
            applied_by = "worker"
        history.append({"round": rnd, "problem_ids": [p.get("id") for p in problems], "applied_by": applied_by})

    rr = schema.read_json(run_dir, schema.REAL_RESULTS)
    return {"ok": not problems, "problems": problems, "real_results": rr,
            "stage": "analysis", "history": history, "escalated": escalated}


def _scope(run_dir: Path) -> str:
    """Read the reviewer's SCOPE decision from the first line of the prescription."""
    p = Path(run_dir) / schema.FIX_PRESCRIPTION
    if not p.is_file():
        return "rewrite"
    first = p.read_text(encoding="utf-8", errors="ignore").strip().splitlines()[:1]
    line = (first[0] if first else "").lower()
    return "small_edit" if "small_edit" in line else "rewrite"


def metrics_block(real_results: dict[str, Any]) -> str:
    """The ONLY admissible numbers for the manuscript (analogous to meta_metrics_block):
    the dataset analysis's models, sample flow, and survey design — transcribed verbatim,
    never re-derived. Domain-agnostic (reads whatever the analysis produced)."""
    rr = real_results or {}
    sd = rr.get("survey_design") or {}
    lines = [
        "REAL DATASET-ANALYSIS RESULTS — the ONLY admissible numbers. Transcribe exact "
        "values; do NOT invent, re-estimate, or re-pool anything.",
        f"Source: {rr.get('source')} | rows analysed: {rr.get('rows')}",
        f"Sample flow (verbatim): {json.dumps(rr.get('sample_flow') or {}, ensure_ascii=False)}",
    ]
    if sd.get("weighted"):
        lines.append(
            "Complex-survey design (weighted): "
            f"weight={sd.get('weight_variable')}, strata={sd.get('strata_variable')}, "
            f"psu={sd.get('psu_variable')}, design_df={sd.get('design_df')}. Report estimates "
            "as survey-weighted; describe associations, not effects beyond the design.")
    lines.append("\nModel estimates (verbatim; cite each by outcome/exposure):")
    for m in (rr.get("models") or [])[:30]:
        ci = (f" [{m.get('ci_low')}, {m.get('ci_high')}]" if m.get("ci_low") is not None else "")
        lines.append(
            f"- {m.get('family')}: {m.get('outcome')} ~ {m.get('exposure')} | "
            f"estimate={m.get('estimate')}{ci} | p={m.get('p_value')} | "
            f"n_unweighted={m.get('n_unweighted')} | n_weighted={m.get('n_weighted')}")
    return "\n".join(lines)
