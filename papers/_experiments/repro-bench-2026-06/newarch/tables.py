"""Deterministic table generation from real_experiments/real_results.json.

The model never transcribes numbers: tables are generated from the results JSON, wrapped
in machine-owned GENERATED blocks, and post-render verified. This makes the quantitative
core correct-by-construction (kills number-transcription drift, fabrication, and the wide-
table overflow class — column count/width are controlled here).

Per-contribution-type templates over small rendering primitives (not a generic table
mini-language). Currently: `classical_ml_benchmark` (benchmark[] of task×feature×model
holdout/cv/CI rows + a training-size ablation).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

GEN_OPEN = "<!-- GENERATED:{tid} source=real_results sha256={sha} -->"
GEN_CLOSE = "<!-- /GENERATED:{tid} -->"
GEN_BLOCK_RE = re.compile(
    r"<!-- GENERATED:(?P<tid>[\w:-]+) source=real_results sha256=(?P<sha>[0-9a-f]+) -->\n"
    r"(?P<body>.*?)\n<!-- /GENERATED:(?P=tid) -->",
    re.DOTALL,
)

# Compact model labels (paper defines these acronyms) keep the first column narrow.
MODEL_ABBR = {
    "LogisticRegression": "LR", "LinearSVC": "SVC", "RandomForest": "RF",
    "GradientBoosting": "GB", "MultinomialNB": "MNB",
}
FEATURE_LABEL = {"tfidf": "TF-IDF", "bow": "BoW"}
TASK_LABEL = {"acceptance": "Acceptance prediction", "cpc_section": "CPC section classification"}


def _f(x: Any, n: int = 3) -> str:
    try:
        return f"{float(x):.{n}f}"
    except (TypeError, ValueError):
        return "—"


def _ci(pair: Any) -> str:
    if isinstance(pair, (list, tuple)) and len(pair) == 2:
        return f"[{_f(pair[0])}, {_f(pair[1])}]"
    return "—"


def _sha(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def _wrap(tid: str, body: str) -> str:
    sha = _sha(body)
    # Blank line between the caption and the close marker is REQUIRED: an HTML
    # comment directly after the caption line stops pandoc from parsing the
    # `{#tbl-id ...}` attributes — the attrs typeset literally and every
    # @tbl-id cross-reference renders as "?@tbl-id" (caught live in r6).
    return f"{GEN_OPEN.format(tid=tid, sha=sha)}\n{body}\n\n{GEN_CLOSE.format(tid=tid)}"


def _main_results_table(rr: dict[str, Any]) -> str | None:
    bench = rr.get("benchmark")
    if not isinstance(bench, list) or not bench:
        return None
    header = ("| Model | Feature | Acc. | Macro-F1 | CV Macro-F1 (mean±std) | 95% CI Macro-F1 |\n"
              "|---|---|---|---|---|---|")
    lines = [header]
    tasks = rr.get("tasks") or sorted({r.get("task") for r in bench if isinstance(r, dict)})
    for task in tasks:
        rows = [r for r in bench if isinstance(r, dict) and r.get("task") == task]
        if not rows:
            continue
        lines.append(f"| **{TASK_LABEL.get(task, task)}** | | | | | |")
        for r in rows:
            cv = (r.get("cv") or {}).get("f1_macro") or {}
            cv_cell = f"{_f(cv.get('mean'))} ± {_f(cv.get('std'))}" if cv else "—"
            lines.append(
                f"| {MODEL_ABBR.get(r.get('model'), r.get('model'))} "
                f"| {FEATURE_LABEL.get(r.get('feature'), r.get('feature'))} "
                f"| {_f((r.get('holdout') or {}).get('accuracy'))} "
                f"| {_f((r.get('holdout') or {}).get('f1_macro'))} "
                f"| {cv_cell} "
                f"| {_ci((r.get('bootstrap_ci_95') or {}).get('f1_macro'))} |"
            )
    n_acc = next((r.get("n_rows") for r in bench if r.get("task") == "acceptance"), "?")
    n_cpc = next((r.get("n_rows") for r in bench if r.get("task") == "cpc_section"), "?")
    caption = (f": Main results: holdout accuracy and macro-F1, 5-fold CV macro-F1 (mean±std), and 95% "
               f"bootstrap confidence intervals across five classifiers and two feature representations "
               f"(acceptance n={n_acc}; CPC section n={n_cpc}). CPU-only. Model keys: "
               f"LR=LogisticRegression, SVC=LinearSVC, RF=RandomForest, GB=GradientBoosting, "
               f"MNB=MultinomialNB. {{#tbl-main tbl-colwidths=\"[14,12,12,14,28,20]\"}}")
    return "\n".join(lines) + "\n\n" + caption


def _ablation_table(rr: dict[str, Any]) -> str | None:
    abl = (rr.get("ablations") or {}).get("training_size_curve")
    if not isinstance(abl, (list, dict)):
        return None
    rows = abl if isinstance(abl, list) else abl.get("rows") if isinstance(abl, dict) else None
    if not isinstance(rows, list) or not rows:
        return None
    header = ("| Task | Train fraction | n_train | Macro-F1 | Accuracy |\n|---|---|---|---|---|")
    lines = [header]
    for r in rows:
        if not isinstance(r, dict):
            continue
        frac = r.get("train_fraction", r.get("fraction"))
        frac_s = f"{int(round(float(frac) * 100))}%" if isinstance(frac, (int, float)) else str(frac)
        hold = r.get("holdout") or {}
        f1 = hold.get("f1_macro", r.get("f1_macro"))
        acc = hold.get("accuracy", r.get("accuracy"))
        lines.append(
            f"| {TASK_LABEL.get(r.get('task'), r.get('task'))} | {frac_s} "
            f"| {r.get('n_train', '—')} | {_f(f1)} | {_f(acc)} |"
        )
    if len(lines) == 1:
        return None
    caption = (": Training-size ablation: macro-F1 and accuracy as a function of training-data "
               "fraction. {#tbl-ablation tbl-colwidths=\"[30,18,16,18,18]\"}")
    return "\n".join(lines) + "\n\n" + caption


def _scientometric_overview_table(rr: dict[str, Any]) -> str | None:
    a = rr.get("analysis")
    if not isinstance(a, dict):
        return None
    cit = a.get("citations") or {}
    yr = a.get("year_range") or ["—", "—"]
    header = "| Indicator | Value |\n|---|---|"
    lines = [
        header,
        f"| OpenAlex corpus size (topic total) | {a.get('openalex_total_count', '—')} |",
        f"| Analysed sample | {a.get('sample_size', '—')} |",
        f"| Year range | {yr[0]}–{yr[1]} |",
        f"| Total citations (sample) | {cit.get('total', '—')} |",
        f"| Mean citations | {cit.get('mean', '—')} |",
        f"| Median citations | {cit.get('median', '—')} |",
        f"| Max citations | {cit.get('max', '—')} |",
    ]
    for v in (a.get("top_venues") or [])[:5]:
        lines.append(f"| Top venue: {str(v.get('name'))[:60]} | {v.get('count')} works |")
    caption = (f": Scientometric overview of the topic corpus (OpenAlex; sample "
               f"n={a.get('sample_size')}). All values derived from collected records. "
               "{#tbl-main tbl-colwidths=\"[62,38]\"}")
    return "\n".join(lines) + "\n\n" + caption


def _pubs_per_year_table(rr: dict[str, Any]) -> str | None:
    a = rr.get("analysis")
    if not isinstance(a, dict):
        return None
    per_year = a.get("publications_per_year") or {}
    if not per_year:
        return None
    years = sorted(per_year, key=int)[-15:]  # most recent 15 years keeps the table short
    header = "| Year | Publications |\n|---|---|"
    lines = [header] + [f"| {y} | {per_year[y]} |" for y in years]
    caption = (": Publications per year for the analysed sample (most recent years; "
               "OpenAlex). {#tbl-trend tbl-colwidths=\"[40,60]\"}")
    return "\n".join(lines) + "\n\n" + caption


def _meta_pooled_table(rr: dict[str, Any]) -> str | None:
    m = rr.get("meta")
    if not isinstance(m, dict):
        return None
    pooled = m.get("pooled") or {}
    prisma = m.get("prisma") or {}
    header = "| Measure | k | Pooled (95% CI) | I² (%) | τ² |\n|---|---|---|---|---|"
    lines = [header]
    for measure, p in sorted(pooled.items()):
        lines.append(f"| {measure} | {p.get('k')} | {_f(p.get('pooled_effect'))} "
                     f"[{_f(p.get('ci_low'))}, {_f(p.get('ci_high'))}] "
                     f"| {p.get('i2_percent')} | {p.get('tau2')} |")
    if len(lines) == 1:
        return None
    caption = (f": Random-effects pooled estimates per effect measure (DerSimonian-Laird, "
               f"log scale). Abstract-level extraction from {prisma.get('scanned')} screened "
               f"OpenAlex records ({prisma.get('studies_with_effects')} studies with "
               f"extractable effects). {{#tbl-main tbl-colwidths=\"[18,10,34,18,20]\"}}")
    return "\n".join(lines) + "\n\n" + caption


def _meta_studies_table(rr: dict[str, Any]) -> str | None:
    m = rr.get("meta")
    if not isinstance(m, dict) or not m.get("effects"):
        return None
    header = "| Study (year) | Measure | Effect (95% CI) | n |\n|---|---|---|---|"
    lines = [header]
    for e in (m.get("effects") or [])[:20]:
        ci = (f" [{_f(e.get('ci_low'))}, {_f(e.get('ci_high'))}]"
              if e.get("ci_low") is not None else "")
        title = str(e.get("title") or "—")[:60]
        lines.append(f"| {title} ({e.get('year')}) | {e.get('measure')} "
                     f"| {_f(e.get('effect'))}{ci} | {e.get('n') or '—'} |")
    caption = (": Per-study quantitative effects mechanically extracted from abstracts "
               "(verbatim evidence retained in the analysis record). "
               "{#tbl-studies tbl-colwidths=\"[44,14,28,14]\"}")
    return "\n".join(lines) + "\n\n" + caption


# contribution-type -> ordered list of (table_id, builder)
TEMPLATES = {
    "classical_ml_benchmark": [("tbl-main", _main_results_table), ("tbl-ablation", _ablation_table)],
    "scientometric": [("tbl-main", _scientometric_overview_table), ("tbl-trend", _pubs_per_year_table)],
    "meta_analysis": [("tbl-main", _meta_pooled_table), ("tbl-studies", _meta_studies_table)],
}


def _template_for(contract: dict[str, Any], rr: dict[str, Any]) -> str:
    if isinstance(rr.get("meta"), dict) or rr.get("lane") == "meta_analysis":
        return "meta_analysis"
    if isinstance(rr.get("analysis"), dict) or rr.get("lane") == "scientometric":
        return "scientometric"
    ct = str(contract.get("contribution_type") or "").lower()
    if "benchmark" in ct or "reproducib" in ct or isinstance(rr.get("benchmark"), list):
        return "classical_ml_benchmark"
    return "classical_ml_benchmark"  # default; extend per type


def generate(run_dir: Path, contract: dict[str, Any] | None = None) -> dict[str, str]:
    """Return {table_id: GENERATED-wrapped markdown}. Empty if no results."""
    run_dir = Path(run_dir)
    rr_path = run_dir / "real_experiments" / "real_results.json"
    if not rr_path.is_file():
        return {}
    try:
        rr = json.loads(rr_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    contract = contract or {}
    out: dict[str, str] = {}
    for tid, builder in TEMPLATES[_template_for(contract, rr)]:
        body = builder(rr)
        if body:
            out[tid] = _wrap(tid, body)
    return out


def inject(run_dir: Path, contract: dict[str, Any] | None = None) -> int:
    """Splice deterministic GENERATED tables into the qmd. Replaces, in priority order:
    (1) a stale GENERATED:<tid> block (idempotent re-run), (2) a `<!-- TABLE:<tid> -->`
    placeholder the writing phase was told to leave. Does nothing for a table whose marker
    is absent (backward-compatible: old runs keep the model's table). Returns count."""
    run_dir = Path(run_dir)
    qmd = run_dir / "paper_draft_v0.qmd"
    if not qmd.is_file():
        return 0
    text = qmd.read_text(encoding="utf-8", errors="ignore")
    gen = generate(run_dir, contract)
    n = 0
    for tid, block in gen.items():
        existing = re.compile(
            r"<!-- GENERATED:" + re.escape(tid) + r" .*?<!-- /GENERATED:" + re.escape(tid) + r" -->",
            re.DOTALL)
        ph = re.compile(r"<!--\s*TABLE:" + re.escape(tid) + r"\s*-->")
        m = existing.search(text)
        if m:
            if m.group(0) != block:  # only count a real change (heals model edits;
                text = existing.sub(lambda _m: block, text, count=1)  # idempotent otherwise)
                n += 1
        elif ph.search(text):
            text = ph.sub(lambda _m: block, text, count=1)
            n += 1
    if n:
        qmd.write_text(text, encoding="utf-8")
    return n


def verify(run_dir: Path, contract: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Post-render integrity check: every GENERATED block in the qmd must still equal a
    fresh deterministic regeneration from real_results (catches tampering inside the
    protected region). Returns a list of problems (empty == clean)."""
    run_dir = Path(run_dir)
    qmd = run_dir / "paper_draft_v0.qmd"
    if not qmd.is_file():
        return []
    text = qmd.read_text(encoding="utf-8", errors="ignore")
    fresh = generate(run_dir, contract)
    problems: list[dict[str, Any]] = []
    seen = set()
    for m in GEN_BLOCK_RE.finditer(text):
        tid = m.group("tid")
        seen.add(tid)
        expect = fresh.get(tid)
        if expect is None:
            continue
        expect_body = expect.split("\n", 1)[1].rsplit("\n", 1)[0].rstrip("\n")
        if m.group("body").strip() != expect_body.strip() or m.group("sha") != _sha(expect_body):
            problems.append({
                "id": f"TBL_TAMPERED:{tid}", "severity": "P0", "location": "paper_draft_v0.qmd",
                "type": "generated_table_mismatch",
                "description": f"GENERATED table {tid} no longer matches real_results — "
                               "numbers were edited inside a machine-owned block.",
            })
    return problems


if __name__ == "__main__":
    import sys
    rd = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    g = generate(rd)
    print(f"generated {len(g)} tables: {list(g)}\n")
    for tid, md in g.items():
        print(md, "\n")
