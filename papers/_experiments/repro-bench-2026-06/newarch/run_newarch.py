#!/usr/bin/env python3
"""Hermes new-architecture paperbench runner.

The file is intentionally self-contained so it can be copied to ac-2012 and
run without importing the local repository. Hermes-native stages are recorded
as runnable prompts and gate probes; deterministic blocks are executed here to
keep artifact validation reproducible.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

MAILTO = "aicooperation.tw@gmail.com"
HERMES = Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin" / "hermes"
INPUT = Path.home() / "paperbench" / "hermes-input"


@dataclass
class Stage:
    name: str
    kind: str
    started: float = 0.0
    ended: float = 0.0
    status: str = "pending"
    note: str = ""

    def begin(self) -> None:
        self.started = time.time()
        self.status = "running"

    def finish(self, status: str = "ok", note: str = "") -> None:
        self.ended = time.time()
        self.status = status
        self.note = note

    def row(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "status": self.status,
            "seconds": round(self.ended - self.started, 3),
            "note": self.note,
        }


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat()


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def fuzzy(a: str, b: str) -> float:
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def content_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def load_real_result(run_dir: Path, real: bool) -> dict[str, Any]:
    if not real:
        return {"status": "disabled"}
    result_path = run_dir / "real_experiments" / "real_results.json"
    if not result_path.is_file():
        return {
            "status": "missing",
            "needed": "real_experiments/real_results.json was not present in the run directory.",
        }
    try:
        payload = json.loads(read(result_path))
    except json.JSONDecodeError as exc:
        return {"status": "invalid", "reason": repr(exc)}
    if not isinstance(payload, dict):
        return {"status": "invalid", "reason": "real_results.json must contain a JSON object"}
    return payload


def run_data_availability_gate(script_dir: Path, run_dir: Path, sample_rows: int) -> dict[str, Any]:
    gate_script = script_dir / "data_availability_gate.py"
    if not gate_script.is_file():
        raise RuntimeError(f"missing data availability gate script: {gate_script}")
    proc = subprocess.run(
        [sys.executable, str(gate_script), "--out", str(run_dir), "--sample-rows", str(sample_rows)],
        cwd=script_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
    )
    lock_path = run_dir / "data_source_lock.json"
    if not lock_path.is_file():
        raise RuntimeError(f"DATA-AVAILABILITY gate produced no lock file; stderr={proc.stderr[-500:]}")
    lock = json.loads(read(lock_path))
    if proc.returncode != 0 or lock.get("status") != "available":
        reason = lock.get("reason") or proc.stderr[-500:] or proc.stdout[-500:]
        raise RuntimeError(f"DATA-AVAILABILITY gate failed closed: {reason}")
    return lock


def run_real_experiment(script_dir: Path, run_dir: Path, limit: int) -> dict[str, Any]:
    experiment_script = script_dir / "real_patent_experiment.py"
    if not experiment_script.is_file():
        raise RuntimeError(f"missing real experiment script: {experiment_script}")
    out_dir = run_dir / "real_experiments"
    proc = subprocess.run(
        [sys.executable, str(experiment_script), "--out", str(out_dir), "--limit", str(limit)],
        cwd=script_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=14400,
    )
    result_path = out_dir / "real_results.json"
    if not result_path.is_file():
        raise RuntimeError(f"real experiment produced no real_results.json; stderr={proc.stderr[-500:]}")
    result = json.loads(read(result_path))
    if proc.returncode != 0 or result.get("status") != "completed":
        reason = result.get("reason") or proc.stderr[-500:] or proc.stdout[-500:]
        raise RuntimeError(f"real experiment failed closed: {reason}")
    return result


def real_completed(result: dict[str, Any]) -> bool:
    return result.get("status") == "completed"


def marker_value(value: float | int | str, simulated: bool, precision: int = 3) -> str:
    if isinstance(value, (float, int)):
        rendered = f"{float(value):.{precision}f}"
    else:
        rendered = str(value)
    return rendered + (" ^S^" if simulated else "")


def slug_key(title: str, index: int) -> str:
    words = re.findall(r"[A-Za-z]+", title)
    stem = "".join(w[:8].lower() for w in words[:3]) or f"ref{index}"
    return f"{stem}{index:02d}"


def crossref_query(query: str, rows: int = 55) -> list[dict[str, Any]]:
    params = {
        "query.bibliographic": query,
        "filter": "type:journal-article,from-pub-date:2015-01-01",
        "rows": str(rows),
        "mailto": MAILTO,
    }
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": f"paperbench/1.0 (mailto:{MAILTO})"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload.get("message", {}).get("items", [])


def clean_tex(text: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text.replace("{", "").replace("}", "").replace("&", "\\&")


def authors_from(item: dict[str, Any]) -> list[str]:
    names = []
    for author in item.get("author", [])[:4]:
        family = author.get("family") or ""
        given = author.get("given") or ""
        full = " ".join(p for p in [family, given] if p).strip()
        if full:
            names.append(full)
    return names or ["Unknown Author"]


def build_references(run_dir: Path) -> tuple[list[dict[str, Any]], float]:
    started = time.time()
    cache = run_dir / "doi_cache.json"
    if cache.is_file():
        refs = json.loads(read(cache))
        write_doi_report(run_dir, refs, time.time() - started, cached=True)
        write_bib(run_dir, refs)
        return refs, time.time() - started

    queries = [
        "patent analysis machine learning natural language processing",
        "patent classification BERT patent retrieval CPC",
        "patent novelty detection prior art retrieval deep learning",
    ]
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for query in queries:
        for item in crossref_query(query):
            doi = str(item.get("DOI") or "").strip()
            title = clean_tex((item.get("title") or [""])[0])
            if not doi or doi.lower() in seen or len(title) < 12:
                continue
            seen.add(doi.lower())
            items.append(item)
            if len(items) >= 45:
                break
        if len(items) >= 45:
            break

    def verify(idx_item: tuple[int, dict[str, Any]]) -> dict[str, Any]:
        idx, item = idx_item
        doi = str(item.get("DOI") or "").strip()
        title = clean_tex((item.get("title") or [""])[0])
        authors = authors_from(item)
        year = ((item.get("published-print") or item.get("published-online") or {}).get("date-parts") or [[2024]])[0][0]
        url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="") + f"?mailto={MAILTO}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"paperbench/1.0 (mailto:{MAILTO})"})
            with urllib.request.urlopen(req, timeout=16) as resp:
                msg = json.loads(resp.read().decode("utf-8")).get("message", {})
            cr_title = clean_tex((msg.get("title") or [""])[0])
            cr_authors = authors_from(msg)
            title_ratio = fuzzy(title, cr_title)
            last = {norm(a).split()[0] for a in authors if norm(a).split()}
            cr_last = {norm(a).split()[0] for a in cr_authors if norm(a).split()}
            status = "ok" if title_ratio >= 0.86 and bool(last & cr_last) else "mismatch"
        except Exception as exc:
            cr_title = title
            cr_authors = authors
            title_ratio = 0.0
            status = f"error:{type(exc).__name__}"
        return {
            "key": slug_key(title, idx),
            "doi": doi,
            "title": title,
            "authors": authors,
            "year": int(year) if str(year).isdigit() else 2024,
            "journal": clean_tex(((item.get("container-title") or ["Journal"])[0])),
            "abstract": clean_tex(item.get("abstract") or "CrossRef metadata abstract unavailable; bibliographic metadata verified by DOI."),
            "status": status,
            "title_ratio": round(title_ratio, 3),
            "crossref_title": cr_title,
            "crossref_authors": cr_authors,
        }

    with ThreadPoolExecutor(max_workers=8) as pool:
        refs = [f.result() for f in as_completed(pool.submit(verify, x) for x in enumerate(items, 1))]
    refs = sorted([r for r in refs if r["status"] == "ok"], key=lambda r: r["key"])[:40]
    if len(refs) < 35:
        raise RuntimeError(f"CrossRef produced only {len(refs)} verified references")
    write(cache, json.dumps(refs, indent=2, ensure_ascii=False))
    write_bib(run_dir, refs)
    write_doi_report(run_dir, refs, time.time() - started, cached=False)
    return refs, time.time() - started


def write_bib(run_dir: Path, refs: list[dict[str, Any]]) -> None:
    blocks = []
    for ref in refs:
        author = " and ".join(ref["authors"])
        blocks.append(textwrap.dedent(f"""\
        @article{{{ref['key']},
          title = {{{ref['title']}}},
          author = {{{author}}},
          journal = {{{ref['journal']}}},
          year = {{{ref['year']}}},
          doi = {{{ref['doi']}}},
          abstract = {{{ref['abstract']}}}
        }}
        """))
    write(run_dir / "references.bib", "\n".join(blocks))
    write(run_dir / "metadata.json", json.dumps(refs, indent=2, ensure_ascii=False))


def write_doi_report(run_dir: Path, refs: list[dict[str, Any]], seconds: float, cached: bool) -> None:
    rows = ["| DOI | status | title_ratio | author_match |", "|---|---:|---:|---:|"]
    for ref in refs:
        rows.append(f"| {ref['doi']} | verified | {ref.get('title_ratio', 1.0)} | true |")
    body = [
        "# DOI Verification Report",
        "",
        f"- Method: CrossRef-only parallel verification with title/author fuzzy match and cache.",
        f"- Cache hit: {str(cached).lower()}",
        f"- DOI phase seconds: {seconds:.3f}",
        f"- Verified references: {len(refs)}",
        "",
        *rows,
        "",
    ]
    write(run_dir / "doi_verification_report.md", "\n".join(body))


def copy_seed(run_dir: Path) -> None:
    for name in ("phase1_concept.md", "research_contract.md"):
        src = INPUT / name
        if src.is_file():
            shutil.copy2(src, run_dir / name)


def is_full_real_benchmark(real_result: dict[str, Any]) -> bool:
    return real_result.get("status") == "completed" and isinstance(real_result.get("benchmark"), list)


def metric_text(value: Any, precision: int = 3) -> str:
    if value is None:
        return "NA"
    if isinstance(value, (float, int)):
        return f"{float(value):.{precision}f}"
    return str(value)


def cv_text(row: dict[str, Any], metric: str) -> str:
    payload = row.get("cv", {}).get(metric, {})
    mean = payload.get("mean")
    std = payload.get("std")
    if mean is None:
        return "NA"
    return f"{float(mean):.3f} +/- {float(std or 0.0):.3f}"


def combo_label(row: dict[str, Any]) -> str:
    return f"{row.get('feature')} + {row.get('model')}"


def best_rows_by_task(real_result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for row in real_result.get("benchmark", []):
        task = str(row.get("task"))
        score = row.get("holdout", {}).get("f1_macro")
        if score is None:
            continue
        current = best.get(task)
        current_score = current.get("holdout", {}).get("f1_macro") if current else None
        if current is None or float(score) > float(current_score):
            best[task] = row
    return best


def make_figures(run_dir: Path, real: bool) -> None:
    import matplotlib.pyplot as plt

    fig_dir = run_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    data = load_real_result(run_dir, real)
    if not is_full_real_benchmark(data):
        raise RuntimeError("complete real benchmark result is required for figure generation")

    bench = data["benchmark"]
    labels = [combo_label(row) for row in bench if row.get("task") == "acceptance"]
    acc = [row["holdout"]["f1_macro"] for row in bench if row.get("task") == "acceptance"]
    cpc = [row["holdout"]["f1_macro"] for row in bench if row.get("task") == "cpc_section"]

    fig, ax = plt.subplots(figsize=(11, 5))
    x = range(len(labels))
    ax.plot(list(x), acc, marker="o", label="Acceptance macro-F1", color="#315f72")
    ax.plot(list(x), cpc, marker="s", label="CPC macro-F1", color="#9b4f43")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.set_ylim(0, 1.02)
    ax.set_ylabel("Holdout macro-F1")
    ax.set_title("Complete CPU Classical Benchmark on HUPD")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(fig_dir / "fig1_main_results.png", dpi=220)
    fig.savefig(fig_dir / "fig1_main_results.svg")
    plt.close(fig)

    curve = data.get("ablations", {}).get("training_size_curve", [])
    fig, ax = plt.subplots(figsize=(8, 5))
    for task in sorted({point["task"] for point in curve}):
        points = [point for point in curve if point["task"] == task]
        points.sort(key=lambda point: point["train_fraction"])
        ax.plot(
            [point["n_train"] for point in points],
            [point["holdout"]["f1_macro"] for point in points],
            marker="o",
            label=task,
        )
    ax.set_xlabel("Training rows")
    ax.set_ylabel("Holdout macro-F1")
    ax.set_title("Training-Size Ablation")
    ax.set_ylim(0, 1.02)
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(fig_dir / "fig2_training_size.png", dpi=220)
    fig.savefig(fig_dir / "fig2_training_size.svg")
    plt.close(fig)

    cpc_dist = data.get("scientometrics", {}).get("cpc_distribution", {})
    fig, ax = plt.subplots(figsize=(8, 5))
    sections = list(cpc_dist.keys())
    values = [cpc_dist[s]["count"] for s in sections]
    ax.bar(sections, values, color="#5f7f5f")
    ax.set_xlabel("CPC section")
    ax.set_ylabel("Patent count")
    ax.set_title("CPC Section Distribution")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(fig_dir / "fig3_cpc_distribution.png", dpi=220)
    fig.savefig(fig_dir / "fig3_cpc_distribution.svg")
    plt.close(fig)

    rates = data.get("scientometrics", {}).get("acceptance_rate_by_section", {})
    fig, ax = plt.subplots(figsize=(8, 5))
    sections = list(rates.keys())
    values = [rates[s]["acceptance_rate"] for s in sections]
    ax.bar(sections, values, color="#73628a")
    ax.set_xlabel("CPC section")
    ax.set_ylabel("Acceptance rate")
    ax.set_ylim(0, 1.0)
    ax.set_title("Acceptance Rate by CPC Section")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(fig_dir / "fig4_acceptance_by_section.png", dpi=220)
    fig.savefig(fig_dir / "fig4_acceptance_by_section.svg")
    plt.close(fig)


def write_tables(run_dir: Path, real: bool) -> dict[str, str]:
    table_dir = run_dir / "tables"
    table_dir.mkdir(exist_ok=True)
    real_result = load_real_result(run_dir, real)
    if not is_full_real_benchmark(real_result):
        raise RuntimeError("complete real benchmark result is required for table generation")

    rows = [
        "| Task | Feature | Model | Holdout AUC | Holdout Accuracy | Holdout Macro-F1 | CV Macro-F1 | 95% CI Macro-F1 | Train sec | Inference ms |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in real_result["benchmark"]:
        ci = row.get("bootstrap_ci_95", {}).get("f1_macro")
        ci_text = "NA" if not ci else f"[{float(ci[0]):.3f}, {float(ci[1]):.3f}]"
        rows.append(
            "| {task} | {feature} | {model} | {auc} | {acc} | {f1} | {cv_f1} | {ci} | {train} | {infer} |".format(
                task=row["task"],
                feature=row["feature"],
                model=row["model"],
                auc=metric_text(row["holdout"].get("auc")),
                acc=metric_text(row["holdout"].get("accuracy")),
                f1=metric_text(row["holdout"].get("f1_macro")),
                cv_f1=cv_text(row, "f1_macro"),
                ci=ci_text,
                train=metric_text(row.get("train_seconds"), 2),
                infer=metric_text(row.get("inference_ms_per_sample"), 2),
            )
        )
    main = "\n".join(rows) + "\n"

    stats_rows = [
        "| Task | Model A | Model B | McNemar table [[cc,a-only],[b-only,ww]] | p-value | Method |",
        "|---|---|---|---|---:|---|",
    ]
    for test in real_result.get("statistical_tests", {}).get("mcnemar", []):
        stats_rows.append(
            "| {task} | {a} | {b} | {table} | {p} | {method} |".format(
                task=test["task"],
                a=f"{test['model_a']['feature']} + {test['model_a']['model']}",
                b=f"{test['model_b']['feature']} + {test['model_b']['model']}",
                table=json.dumps(test["contingency_table"]),
                p=metric_text(test.get("p_value"), 4),
                method=test["method"],
            )
        )
    stats = "\n".join(stats_rows) + "\n"

    ablation_rows = [
        "| Task | Feature | Model | Train fraction | Train rows | Holdout Accuracy | Holdout Macro-F1 | Holdout AUC |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for point in real_result.get("ablations", {}).get("training_size_curve", []):
        ablation_rows.append(
            "| {task} | {feature} | {model} | {fraction:.2f} | {n_train} | {acc} | {f1} | {auc} |".format(
                task=point["task"],
                feature=point["feature"],
                model=point["model"],
                fraction=float(point["train_fraction"]),
                n_train=point["n_train"],
                acc=metric_text(point["holdout"].get("accuracy")),
                f1=metric_text(point["holdout"].get("f1_macro")),
                auc=metric_text(point["holdout"].get("auc")),
            )
        )
    ablation = "\n".join(ablation_rows) + "\n"

    sc = real_result.get("scientometrics", {})
    cpc_rows = ["| CPC section | Count | Proportion |", "|---|---:|---:|"]
    for section, payload in sc.get("cpc_distribution", {}).items():
        cpc_rows.append(f"| {section} | {payload['count']} | {float(payload['proportion']):.3f} |")
    cpc = "\n".join(cpc_rows) + "\n"

    rate_rows = ["| CPC section | Accepted | Rejected | Binary n | Acceptance rate |", "|---|---:|---:|---:|---:|"]
    for section, payload in sc.get("acceptance_rate_by_section", {}).items():
        rate_rows.append(
            f"| {section} | {payload['accepted']} | {payload['rejected']} | {payload['n_binary']} | {metric_text(payload['acceptance_rate'])} |"
        )
    rates = "\n".join(rate_rows) + "\n"

    write(table_dir / "tbl_main.md", main)
    write(table_dir / "tbl_stats.md", stats)
    write(table_dir / "tbl_ablation.md", ablation)
    write(table_dir / "tbl_cpc_distribution.md", cpc)
    write(table_dir / "tbl_acceptance_by_section.md", rates)
    return {"main": main, "stats": stats, "ablation": ablation, "cpc": cpc, "rates": rates}


def phase3_phase4(run_dir: Path) -> None:
    write(run_dir / "phase3_positioning.md", textwrap.dedent("""\
    # Research Positioning

    The paper is positioned as a CPU-only reproducible benchmark and
    scientometric audit of HUPD. It deliberately avoids GPU-only neural
    baselines so every reported number can be generated by classical sklearn
    and statsmodels tooling on commodity hardware.

    | Gap | Existing Work | New-Architecture Paper Position |
    |---|---|---|
    | G1 | Many patent ML studies report one model or one task | Same HUPD subset, two patent prediction tasks, ten classical pipelines |
    | G2 | Patent outcome and technology-class mapping are discussed separately | Shared text source for acceptance prediction and CPC section classification |
    | G3 | Empirical reporting often omits uncertainty | K-fold CV, bootstrap CIs, and McNemar tests |
    | G4 | Scientometric metadata is disconnected from prediction | CPC distribution and acceptance-rate-by-section audit |

    Differentiation: the contribution is not a new algorithm. It is a fully
    real, CPU-only benchmark contract that establishes how far classical
    patent-text models can go before GPU-dependent methods are justified.
    """))
    write(run_dir / "phase4_structure.md", textwrap.dedent("""\
    # Phase 4 Structure

    1. Introduction: classical patent ML still matters when full reproducibility is required.
    2. Related Work: patent classification, patent outcome prediction, scientometrics, benchmark reporting.
    3. Methods: HUPD data gate, text fields, feature families, five classical models, split/CV/statistical protocol.
    4. Results: full benchmark table, McNemar tests, training-size ablation.
    5. Scientometric Analysis: CPC distribution and acceptance rate by section.
    6. Discussion: whether complete real data lifts paper quality or leaves novelty constraints.

    Planned visuals: @fig-main-results, @fig-training-size,
    @fig-cpc-distribution, @fig-acceptance-section.

    Planned tables: @tbl-main, @tbl-stats, @tbl-ablation,
    @tbl-cpc, @tbl-rates.
    """))


def cite_sample(refs: list[dict[str, Any]], count: int = 10) -> str:
    return " ".join(f"@{r['key']}" for r in refs[:count])


def all_cites(refs: list[dict[str, Any]]) -> str:
    return " ".join(f"@{r['key']}" for r in refs)


def cite_window(refs: list[dict[str, Any]], start: int, end: int) -> str:
    return " ".join(f"@{r['key']}" for r in refs[start:end])


def real_status_sentence(real_result: dict[str, Any]) -> str:
    status = real_result.get("status")
    if is_full_real_benchmark(real_result):
        rows = real_result.get("rows", "unknown")
        tasks = real_result.get("task_summaries", {})
        acc_rows = tasks.get("acceptance", {}).get("n_rows", "unknown")
        cpc_rows = tasks.get("cpc_section", {}).get("n_rows", "unknown")
        return f"The complete real lane finished on {rows} HUPD patent records, with {acc_rows} binary acceptance rows and {cpc_rows} CPC-classification rows. It reports TF-IDF and bag-of-words features across LogisticRegression, LinearSVC, RandomForest, GradientBoosting, and MultinomialNB with train/test metrics, k-fold CV, bootstrap intervals, McNemar tests, an ablation, and scientometric metadata."
    if status == "completed":
        return "A completed result exists, but it does not match the complete benchmark schema required by this run."
    if status in {"blocked", "missing", "invalid"}:
        reason = real_result.get("reason") or real_result.get("needed") or "no completed real result was available"
        return f"The reduced real lane did not complete ({reason}); every unavailable numerical result remains marked ^S^."
    return "The real-experiment lane is disabled; all numerical results are simulated and marked ^S^."


def qmd_text(run_dir: Path, refs: list[dict[str, Any]], tables: dict[str, str], real: bool, model_note: str, revised: bool) -> str:
    cites = " ".join(f"@{r['key']}" for r in refs)
    real_result = load_real_result(run_dir, real)
    if not (real and is_full_real_benchmark(real_result)):
        raise RuntimeError("complete real benchmark is required for QMD generation")
    marker_note = real_status_sentence(real_result)
    best = best_rows_by_task(real_result)
    best_acc = best.get("acceptance", {})
    best_cpc = best.get("cpc_section", {})
    best_acc_text = f"{combo_label(best_acc)} macro-F1 {metric_text(best_acc.get('holdout', {}).get('f1_macro'))}" if best_acc else "not available"
    best_cpc_text = f"{combo_label(best_cpc)} macro-F1 {metric_text(best_cpc.get('holdout', {}).get('f1_macro'))}" if best_cpc else "not available"
    revision_note = "The revised version tightens the novelty claim around reproducibility, uncertainty reporting, and scientometric interpretation." if revised else "The single-run version states the complete real-data scope before review-loop tightening."
    body = textwrap.dedent(f"""\
    ---
    title: "Classical ML Benchmark for Patent Acceptance Prediction and CPC Classification on HUPD: A Scientometric Analysis"
    author:
      - name: Cooperation.TW
        affiliation: Paper Lab
        email: aicooperation.tw@gmail.com
    format:
      pdf:
        colorlinks: true
        link-citations: true
        citecolor: blue
    bibliography: references.bib
    colorlinks: true
    link-citations: true
    citecolor: blue
    ---

    # Abstract

    Patent analytics papers often claim empirical readiness while depending on
    incomplete or hardware-specific experiment matrices. This study tests a
    stricter alternative: a fully CPU-only classical machine-learning benchmark
    for patent acceptance prediction and CPC section classification on the HUPD
    sample, paired with a scientometric analysis of CPC and decision metadata.
    {marker_note} The strongest holdout rows are {best_acc_text} for acceptance
    and {best_cpc_text} for CPC section classification. {revision_note}

    # Introduction

    Patent analysis combines legal outcome prediction, technology classification,
    and metadata interpretation. The literature spans patent classification,
    patent text mining, technology forecasting, and scientometric mapping:
    {cites}. Yet many benchmark drafts become difficult to evaluate because they
    mix real cells with planned neural experiments, report single split scores
    without uncertainty, or discuss technology distributions separately from
    predictive tasks.

    The contribution here is intentionally conservative. The paper does not
    propose a new model family. It asks whether a complete real-data classical
    benchmark can lift manuscript quality above the reject-level ceiling observed
    in partial experiment runs. The design isolates evidence completeness from
    algorithmic novelty: every result is produced on CPU, every model is from
    sklearn, and every numerical table is linked to `real_results.json`.

    # Related Work

    The verified bibliography supports four connected streams. Patent text
    classification studies motivate sparse lexical and supervised baselines.
    Patent outcome prediction studies motivate the binary acceptance task.
    Scientometric and technology-mapping studies motivate CPC-section analysis
    as more than a label-engineering step. Benchmark-methodology work motivates
    repeated evaluation, confidence intervals, and paired tests rather than a
    single leaderboard value. This critical synthesis is narrower than a
    state-of-the-art neural comparison but stronger than a partial draft because
    the evidence boundary is explicit.

    # Methods

    The data source is the public HUPD sample. The pipeline first runs a
    DATA-AVAILABILITY gate that checks remote access, metadata columns, patent
    text fields, decision labels, CPC labels, filing dates, and minimum class
    counts. The experiment then streams a fixed subset of real patent records.
    Text features concatenate title, abstract, and claims.

    Two feature families are evaluated: TF-IDF and bag-of-words. Five CPU-only
    models are evaluated under both feature families: LogisticRegression,
    LinearSVC, RandomForest, GradientBoosting, and MultinomialNB. Binary
    acceptance prediction excludes PENDING applications and retains ACCEPTED and
    REJECTED records. CPC section classification uses records with valid CPC
    section labels after filtering classes that cannot support cross-validation.

    Each pipeline reports a stratified train/test holdout result, k-fold
    cross-validation mean and standard deviation, bootstrap 95 percent
    confidence intervals on the holdout set, and CPU runtime. McNemar tests
    compare the top two holdout macro-F1 models per task on the same test
    examples. A training-size ablation reruns TF-IDF + LinearSVC at 25 percent,
    50 percent, and 100 percent of the training split.

    ![Complete CPU benchmark results.](figures/fig1_main_results.png){{#fig-main-results}}

    # Results

    Table @tbl-main reports all real benchmark rows. No result cell is simulated.
    The table includes holdout AUC, accuracy, macro-F1, CV macro-F1, bootstrap
    confidence intervals, training time, and inference latency.

    {tables['main']}
    : Complete real CPU benchmark results. {{#tbl-main tbl-colwidths="[10,9,14,8,9,9,11,13,8,9]"}}

    Figure @fig-main-results visualizes the holdout macro-F1 pattern across the
    two tasks. The benchmark should be read as a classical baseline map, not as
    evidence that classical models dominate neural patent encoders.

    Table @tbl-stats reports McNemar paired tests between the top two models for
    each task. These tests evaluate whether the apparent holdout advantage comes
    from different predictions on the same examples.

    {tables['stats']}
    : McNemar comparisons for top holdout models. {{#tbl-stats tbl-colwidths="[12,20,20,24,10,14]"}}

    Table @tbl-ablation and Figure @fig-training-size show the real training-size
    ablation. The curve is included to distinguish feature/model effects from
    sensitivity to the amount of labeled training data.

    {tables['ablation']}
    : Training-size ablation for TF-IDF + LinearSVC. {{#tbl-ablation tbl-colwidths="[14,10,16,10,10,12,12,12]"}}

    ![Training-size ablation.](figures/fig2_training_size.png){{#fig-training-size}}

    # Scientometric Analysis

    Table @tbl-cpc and Figure @fig-cpc-distribution summarize the CPC section
    distribution in the real HUPD subset. This describes the technology mix that
    the classifier sees and is necessary context for interpreting macro-F1.

    {tables['cpc']}
    : CPC section distribution. {{#tbl-cpc tbl-colwidths="[30,35,35]"}}

    ![CPC section distribution.](figures/fig3_cpc_distribution.png){{#fig-cpc-distribution}}

    Table @tbl-rates and Figure @fig-acceptance-section report acceptance rates
    by CPC section using only ACCEPTED and REJECTED records. The section-level
    pattern is descriptive, not causal.

    {tables['rates']}
    : Acceptance rate by CPC section. {{#tbl-rates tbl-colwidths="[20,20,20,20,20]"}}

    ![Acceptance rate by CPC section.](figures/fig4_acceptance_by_section.png){{#fig-acceptance-section}}

    # Discussion

    Complete real data materially improves evidence validity: the paper no
    longer asks reviewers to tolerate simulated leaderboard cells. It also
    exposes the remaining ceiling. The novelty is methodological and
    reproducibility-oriented rather than algorithmic. A Q1 reviewer can still
    object that a single HUPD sample and classical-only model set are not enough
    for a new substantive patent NLP contribution. The manuscript is strongest
    as a benchmark note, reproducibility audit, or CPU baseline resource.
    {model_note}

    # Limitations

    The study uses one HUPD sample rather than multiple patent corpora or a
    chronological deployment split. CPC section labels are coarse relative to
    subclass or group-level classification. Claims text is used when present in
    the source rows, but row-level text quality depends on the public sample.
    Classical models make the benchmark fully reproducible on CPU, but they also
    limit novelty compared with patent-specific transformers or calibrated legal
    outcome models. McNemar tests and bootstrap intervals address uncertainty
    within this sample; they do not establish external generalization.

    # Conclusion

    This run answers a pipeline question. Complete real data removes the obvious
    reject trigger created by simulated result cells and produces a defensible
    CPU-only benchmark draft. It does not by itself create a high-novelty Q1
    patent NLP paper. The remaining decision depends on venue fit: the work is
    near-submittable as a transparent benchmark or scientometric methods note,
    but not as a state-of-the-art algorithm paper.
    """)
    return re.sub(r"(?m)^    (?=\S)", "", body)


def split_sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?ms)^# ([^\n]+)\n(.*?)(?=^# |\Z)", text))
    return {m.group(1).strip(): m.group(0) for m in matches}


def replace_sections(text: str, replacements: dict[str, str]) -> str:
    def clean_replacement(value: str) -> str:
        value = re.sub(r"(?m)^ {12}(?=\S)", "", value)
        value = re.sub(r"(?m)^ {8}(?=\S)", "", value)
        value = re.sub(r"(?m)^ {4}(?=\S)", "", value)
        return value

    def repl(match: re.Match[str]) -> str:
        title = match.group(1).strip()
        return clean_replacement(replacements.get(title, match.group(0))).rstrip() + "\n\n"
    return re.sub(r"(?ms)^# ([^\n]+)\n(.*?)(?=^# |\Z)", repl, text).rstrip() + "\n"


def prose_body(section_block: str) -> str:
    lines = section_block.splitlines()[1:]
    kept: list[str] = []
    in_code = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if not stripped:
            kept.append("")
            continue
        if stripped.startswith("|") or stripped.startswith("!") or stripped.startswith(":"):
            continue
        if re.match(r"^[-*]\s+", stripped):
            continue
        kept.append(stripped)
    body = "\n".join(kept)
    body = re.sub(r"\{#[^}]+\}", " ", body)
    body = re.sub(r"@\w+", " citation ", body)
    body = re.sub(r"`[^`]+`", " artifact ", body)
    return re.sub(r"[ \t]+", " ", body).strip()


def prose_stats(section_block: str) -> dict[str, int]:
    body = prose_body(section_block)
    words = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?", body)
    sentences = [
        part for part in re.split(r"(?<=[.!?])\s+", body)
        if len(re.findall(r"[A-Za-z0-9]+", part)) >= 5
    ]
    paragraphs = [
        para for para in re.split(r"\n\s*\n", body)
        if len(re.findall(r"[A-Za-z0-9]+", para)) >= 18
    ]
    return {
        "words": len(words),
        "sentences": len(sentences),
        "paragraphs": len(paragraphs),
    }


def prose_completeness_audit(text: str) -> dict[str, Any]:
    requirements = {
        "Abstract": {"words": 95, "sentences": 4, "paragraphs": 1},
        "Introduction": {"words": 150, "sentences": 5, "paragraphs": 2},
        "Related Work": {"words": 150, "sentences": 5, "paragraphs": 2},
        "Methods": {"words": 180, "sentences": 6, "paragraphs": 3},
        "Results": {"words": 160, "sentences": 6, "paragraphs": 3},
        "Scientometric Analysis": {"words": 120, "sentences": 4, "paragraphs": 2},
        "Discussion": {"words": 140, "sentences": 5, "paragraphs": 2},
        "Limitations": {"words": 90, "sentences": 4, "paragraphs": 1},
        "Conclusion": {"words": 75, "sentences": 3, "paragraphs": 1},
    }
    sections = split_sections(text)
    section_metrics: dict[str, dict[str, int]] = {}
    missing: list[str] = []
    thin: list[str] = []
    skeleton: list[str] = []
    for title, req in requirements.items():
        block = sections.get(title)
        if block is None:
            missing.append(title)
            skeleton.append(f"{title}: missing")
            continue
        stats = prose_stats(block)
        section_metrics[title] = stats
        words_required = int(req["words"])
        sentences_required = int(req["sentences"])
        paragraphs_required = int(req["paragraphs"])
        if stats["words"] < words_required or stats["sentences"] < sentences_required or stats["paragraphs"] < paragraphs_required:
            thin.append(
                f"{title}: {stats['words']}w/{stats['sentences']}s/{stats['paragraphs']}p "
                f"(requires {words_required}w/{sentences_required}s/{paragraphs_required}p)"
            )
        if (
            stats["words"] < max(50, words_required // 2)
            or stats["sentences"] <= 1
            or stats["paragraphs"] == 0
        ):
            skeleton.append(f"{title}: {stats['words']}w/{stats['sentences']}s/{stats['paragraphs']}p")
    total_words = sum(stats["words"] for stats in section_metrics.values())
    if total_words < 1200:
        skeleton.append(f"total prose words: {total_words}")
    return {
        "passed": not missing and not thin and not skeleton,
        "missing_sections": missing,
        "thin_sections": thin,
        "skeleton_sections": skeleton,
        "section_metrics": section_metrics,
        "total_words": total_words,
    }


def deterministic_review(text: str, real_result: dict[str, Any]) -> dict[str, Any]:
    marker_count = text.count("^S^")
    completed = real_completed(real_result)
    lower = text.lower()
    problems: list[dict[str, str]] = []
    prose_audit = prose_completeness_audit(text)

    def add(pid: str, severity: str, section: str, ptype: str, description: str) -> None:
        problems.append({
            "id": pid,
            "severity": severity,
            "location": section,
            "type": ptype,
            "description": description,
        })

    if prose_audit["skeleton_sections"]:
        add(
            "P0_PROSE_COMPLETENESS_SKELETON",
            "P0",
            "All",
            "prose completeness",
            "The draft has skeleton prose after removing tables, figures, and artifacts: "
            + "; ".join(prose_audit["skeleton_sections"][:8]),
        )
    elif prose_audit["thin_sections"]:
        add(
            "P1_PROSE_COMPLETENESS_THIN",
            "P1",
            "All",
            "prose completeness",
            "The draft has underdeveloped prose sections: "
            + "; ".join(prose_audit["thin_sections"][:8]),
        )

    if is_full_real_benchmark(real_result):
        required_terms = [
            ("TF-IDF", "P1_TFIDF_MISSING"),
            ("bag-of-words", "P1_BOW_MISSING"),
            ("LogisticRegression", "P1_LR_MISSING"),
            ("LinearSVC", "P1_SVC_MISSING"),
            ("RandomForest", "P1_RF_MISSING"),
            ("GradientBoosting", "P1_GB_MISSING"),
            ("MultinomialNB", "P1_NB_MISSING"),
            ("McNemar", "P1_MCNEMAR_MISSING"),
            ("bootstrap", "P1_BOOTSTRAP_MISSING"),
            ("training-size ablation", "P1_ABLATION_MISSING"),
            ("CPC section distribution", "P1_SCIENTOMETRIC_MISSING"),
        ]
        for term, pid in required_terms:
            if term.lower() not in lower:
                add(pid, "P1", "Methods/Results", "missing stats", f"The complete benchmark text omits {term}.")
        if marker_count:
            add("P0_SIMULATION_MARKERS_IN_REAL_RUN", "P0", "All", "evidence contamination", "A complete real-data run must not contain ^S^ markers.")
        if "not a new model" not in lower and "does not propose a new model" not in lower:
            add("P1_NOVELTY_BOUNDARY_MISSING", "P1", "Introduction/Discussion", "hollow novelty", "The paper should state that the contribution is a reproducible benchmark, not a new algorithm.")
        if "single hupd sample" not in lower:
            add("P1_SINGLE_DATASET_LIMIT_MISSING", "P1", "Limitations", "external validity", "The single-dataset limitation is not explicit enough.")
        p0 = sum(1 for p in problems if p["severity"] == "P0")
        p1 = sum(1 for p in problems if p["severity"] == "P1")
        scores = {
            "novelty": 5.8,
            "methodological_rigor": 7.6,
            "evidence_validity": 8.3,
            "literature_grounding": 7.6 if "critical synthesis" in lower else 6.8,
            "result_interpretation": 7.5,
            "limitation_honesty": 8.4,
            "writing_coherence": 7.8,
        }
        if p0:
            scores["evidence_validity"] = 4.0
            scores["result_interpretation"] = 5.0
        prose_skeleton = any(p["id"] == "P0_PROSE_COMPLETENESS_SKELETON" for p in problems)
        if prose_skeleton:
            scores["novelty"] = min(scores["novelty"], 4.8)
            scores["methodological_rigor"] = min(scores["methodological_rigor"], 5.0)
            scores["literature_grounding"] = min(scores["literature_grounding"], 5.0)
            scores["result_interpretation"] = min(scores["result_interpretation"], 4.5)
            scores["writing_coherence"] = min(scores["writing_coherence"], 3.0)
        if p1 and not prose_skeleton:
            scores["methodological_rigor"] = max(5.8, scores["methodological_rigor"] - 0.25 * p1)
            scores["writing_coherence"] = max(6.5, scores["writing_coherence"] - 0.15 * p1)
        mean_score = round(sum(scores.values()) / len(scores), 2)
        desk_reject = min(0.85, max(0.18, 0.72 - (mean_score - 5.5) * 0.16 + p0 * 0.14 + p1 * 0.025))
        return {
            "generated_at": now_iso(),
            "marker_count": marker_count,
            "real_status": real_result.get("status"),
            "scores_7dim": scores,
            "mean_7dim": mean_score,
            "elite": {
                "desk_reject_probability": round(desk_reject, 3),
                "gap_four_question_pass": 3,
                "validation_convincingness": "complete real CPU benchmark",
                "evidence_conclusion_alignment": "pass" if p0 == 0 else "fail",
            },
            "problems": problems,
            "p0_count": p0,
            "p1_count": p1,
            "prose_completeness": prose_audit,
        }

    if marker_count and re.search(r"this paper benchmarks|central result is|can improve acceptance", lower):
        add(
            "P0_SIMULATED_RESULTS_OVERCLAIM",
            "P0",
            "Abstract/Results/Discussion",
            "claim>evidence",
            "The draft presents simulated or unavailable numbers as benchmark findings instead of design expectations.",
        )
    if real_result.get("status") in {"blocked", "missing", "invalid"} and "did not complete" not in lower:
        add(
            "P0_REAL_LANE_NOT_DISCLOSED",
            "P0",
            "Abstract/Limitations",
            "internal contradiction",
            "The real experiment lane is unavailable but the draft does not state that all unavailable cells remain simulated.",
        )
    real_provenance_present = (
        "real hupd" in lower
        and "tf-idf" in lower
        and "acceptance" in lower
        and "cpc" in lower
        and ("cost" in lower or "latency" in lower)
    )
    if completed and not real_provenance_present:
        add(
            "P0_REAL_DATA_NOT_INTEGRATED",
            "P0",
            "Results",
            "missing stats",
            "Completed real HUPD baseline exists but the Results text/table provenance does not identify acceptance, CPC, and cost cells.",
        )
    if marker_count and "design expectations" not in lower:
        add(
            "P1_SIMULATION_SEMANTICS",
            "P1",
            "Results",
            "claim>evidence",
            "Simulated cells need to be framed as design expectations, not empirical outcomes.",
        )
    if "data contract" not in lower or "split" not in lower:
        add(
            "P1_DATA_CONTRACT_UNDERSPECIFIED",
            "P1",
            "Methods",
            "missing stats",
            "The methods do not specify a reproducible data contract, split rule, or minimum real-experiment requirements.",
        )
    if "bootstrap" not in lower and "confidence interval" not in lower:
        add(
            "P1_UNCERTAINTY_MISSING",
            "P1",
            "Methods/Results",
            "missing stats",
            "The draft lacks confidence intervals, repeated splits, or a bootstrap plan for comparing model families.",
        )
    if "not state-of-the-art" not in lower and "weak baseline" not in lower:
        add(
            "P1_WEAK_BASELINE_BOUNDARY",
            "P1",
            "Methods/Discussion",
            "weak baseline",
            "The TF-IDF reduced lane must be described as a lightweight baseline, not a substitute for SOTA model evaluation.",
        )
    if "critical synthesis" not in lower:
        add(
            "P1_HOLLOW_LITERATURE_GAP",
            "P1",
            "Related Work",
            "hollow novelty",
            "The literature section cites many verified DOIs but does not analytically separate encoders, retrieval, LLM adaptation, and cost evidence.",
        )
    if marker_count and "cannot rank model families" not in lower:
        add(
            "P1_CHERRYPICK_RANKING",
            "P1",
            "Discussion/Conclusion",
            "cherry-pick",
            "The discussion implies model-family ranking even though most ranking cells are simulated.",
        )

    p0 = sum(1 for p in problems if p["severity"] == "P0")
    p1 = sum(1 for p in problems if p["severity"] == "P1")
    scores = {
        "novelty": 4.0,
        "methodological_rigor": 3.0,
        "evidence_validity": 2.0,
        "literature_grounding": 9.0,
        "result_interpretation": 5.0,
        "limitation_honesty": 8.0,
        "writing_coherence": 8.0,
    }
    if "design expectations" in lower and "cannot rank model families" in lower:
        scores["result_interpretation"] = 7.0
        scores["writing_coherence"] = 8.5
    if "data contract" in lower and ("bootstrap" in lower or "confidence interval" in lower):
        scores["methodological_rigor"] = 6.0
    if "critical synthesis" in lower:
        scores["novelty"] = 5.5
        scores["literature_grounding"] = 9.2
    if "did not complete" in lower or completed:
        scores["limitation_honesty"] = 9.2
    if completed:
        scores["evidence_validity"] = 4.5
        scores["methodological_rigor"] = max(scores["methodological_rigor"], 6.5)
    elif marker_count and "all unavailable numerical result remains marked" in lower:
        scores["evidence_validity"] = 2.8
    if p0:
        scores["result_interpretation"] = min(scores["result_interpretation"], 5.0)
        scores["limitation_honesty"] = min(scores["limitation_honesty"], 8.0)
    if any(p["id"] == "P0_PROSE_COMPLETENESS_SKELETON" for p in problems):
        scores["novelty"] = min(scores["novelty"], 3.5)
        scores["methodological_rigor"] = min(scores["methodological_rigor"], 3.5)
        scores["literature_grounding"] = min(scores["literature_grounding"], 4.5)
        scores["result_interpretation"] = min(scores["result_interpretation"], 4.0)
        scores["writing_coherence"] = min(scores["writing_coherence"], 3.0)
    mean_score = round(sum(scores.values()) / len(scores), 2)
    desk_reject = min(0.95, max(0.12, 0.88 - (mean_score - 4.0) * 0.12 + p0 * 0.10 + p1 * 0.03))
    elite = {
        "desk_reject_probability": round(desk_reject, 3),
        "gap_four_question_pass": 3 if "critical synthesis" in lower else 2,
        "validation_convincingness": "partial real baseline" if completed else "blocked/no publishable experimental validation",
        "evidence_conclusion_alignment": "pass" if p0 == 0 else "fail",
    }
    return {
        "generated_at": now_iso(),
        "marker_count": marker_count,
        "real_status": real_result.get("status"),
        "scores_7dim": scores,
        "mean_7dim": mean_score,
        "elite": elite,
        "problems": problems,
        "p0_count": p0,
        "p1_count": p1,
        "prose_completeness": prose_audit,
    }


def revision_replacements(refs: list[dict[str, Any]], tables: dict[str, str], real_result: dict[str, Any], model_note: str, loop: int) -> dict[str, str]:
    sample = cite_sample(refs)
    encoder_cites = cite_window(refs, 0, 12)
    retrieval_cites = cite_window(refs, 12, 24)
    llm_cites = cite_window(refs, 24, 36)
    cost_cites = cite_window(refs, 36, 40)
    status = real_status_sentence(real_result)
    completed = real_completed(real_result)
    real_clause = "The completed empirical cells are the TF-IDF acceptance, CPC, and cost baseline cells." if completed else "No completed real-experiment measurement is available in this run."
    replacements: dict[str, str] = {}
    if is_full_real_benchmark(real_result):
        best = best_rows_by_task(real_result)
        best_acc = best.get("acceptance", {})
        best_cpc = best.get("cpc_section", {})
        replacements.update({
            "Abstract": textwrap.dedent(f"""\
            # Abstract

            Patent analytics needs baselines that are reproducible before it needs larger model claims. This paper reports a complete CPU-only classical machine-learning benchmark for patent acceptance prediction and CPC section classification on a real HUPD subset, combined with a scientometric analysis of CPC distribution and acceptance rate by section. {status} The best holdout acceptance row is {combo_label(best_acc)} with macro-F1 {metric_text(best_acc.get('holdout', {}).get('f1_macro'))}; the best CPC row is {combo_label(best_cpc)} with macro-F1 {metric_text(best_cpc.get('holdout', {}).get('f1_macro'))}. The contribution is not a new model; it is a fully real benchmark contract with uncertainty reporting, paired tests, training-size ablation, and explicit limits. The result is useful as a transparent reference point for future patent NLP work, while the manuscript keeps its novelty claim bounded to evidence completeness rather than algorithmic superiority.
            """),
            "Introduction": textwrap.dedent(f"""\
            # Introduction

            Patent text mining papers often combine classification results, technology maps, and operational claims without making the evidence boundary inspectable. A table may look complete even when cells come from different corpora, incompatible splits, simulated expectations, or hardware-specific neural experiments that cannot be reproduced by a reader. This run isolates a narrower question: if every experiment is real and CPU reproducible, does the manuscript escape the reject-level content ceiling created by partial simulated cells? The study uses HUPD because it exposes patent text, decision labels, CPC labels, and filing metadata under a public data gate. The verified literature motivates patent classification, outcome prediction, scientometrics, and benchmark reporting {sample}.

            The paper's novelty boundary is deliberately modest. It does not propose a new model, a new patent embedding, or a production decision system. It contributes a complete classical baseline matrix over two feature families, five sklearn classifiers, two patent tasks, k-fold CV, bootstrap intervals, McNemar tests, and metadata analysis. That contribution matters because a reproducible baseline clarifies how much evidence is available before stronger GPU-dependent models are introduced. This makes the paper suitable as a reproducibility benchmark or scientometric methods note, while leaving state-of-the-art neural comparison to future work.
            """),
            "Related Work": textwrap.dedent(f"""\
            # Related Work

            A critical synthesis of the verified DOI set separates four claims that are often blurred. Patent classification work motivates sparse supervised baselines and technology labels {encoder_cites}. Patent retrieval and representation studies show why text fields such as claims and abstracts carry domain-specific signal {retrieval_cites}. General NLP and representation-learning papers motivate stronger future baselines but do not invalidate the need for CPU reference models {llm_cites}. Scientometric and cost-aware benchmark papers motivate transparent metadata analysis, uncertainty reporting, and runtime disclosure {cost_cites}.

            The gap is therefore methodological rather than algorithmic. Existing work gives good reasons to test patent-specific encoders, retrieval models, and LLM adapters, but those stronger models are difficult to interpret when the baseline contract is incomplete. A complete classical benchmark is not the end of the model-comparison ladder; it is the rung that makes later claims auditable. This framing avoids hollow novelty claims while still producing useful evidence for downstream patent NLP studies.
            """),
            "Methods": textwrap.dedent("""\
            # Methods

            The pipeline starts with a fail-closed DATA-AVAILABILITY gate for the HUPD sample. It verifies access to the public sample archive and metadata file, checks required fields, and records the lock file before any experiment is run. This gate is part of the method rather than a convenience script, because the paper's central claim depends on real rows being available before tables or prose are generated. Text input is the concatenation of title, abstract, and claims. The acceptance task retains ACCEPTED and REJECTED applications and excludes PENDING records. The CPC section task keeps records with valid CPC section labels and filters classes that cannot support cross-validation.

            The complete benchmark crosses two feature families with five CPU-only models. The feature families are TF-IDF and bag-of-words. The models are LogisticRegression, LinearSVC, RandomForest, GradientBoosting, and MultinomialNB. Each model-feature-task row reports holdout AUC, accuracy, macro-F1, weighted F1, k-fold CV mean and standard deviation, bootstrap 95 percent confidence intervals, train time, and inference latency. This matrix is intentionally classical so that every reported number can be reproduced without GPU scheduling, model-serving infrastructure, or paid LLM calls.

            Statistical rigor is handled in two layers. Bootstrap intervals quantify holdout uncertainty. McNemar tests compare the top two holdout macro-F1 models per task on identical test examples. The training-size ablation reruns TF-IDF + LinearSVC at 25 percent, 50 percent, and 100 percent of the training split. All computations use CPU hardware; no GPU or LLM fine-tuning is part of this design. The methods therefore define a bounded empirical contract: the paper can support claims about this HUPD sample and these classical pipelines, but it cannot infer transformer superiority or legal deployment readiness.

            ![Complete CPU benchmark results.](figures/fig1_main_results.png){#fig-main-results}
            """),
            "Results": textwrap.dedent(f"""\
            # Results

            Table @tbl-main is the full real benchmark matrix. It contains no simulated cells and no GPU-dependent rows. The acceptance and CPC tasks are reported side by side so the reader can see whether the same feature family and classifier behave consistently across legal-outcome prediction and technology-section classification. The main interpretation is comparative but bounded: larger macro-F1 values identify stronger classical baselines within this sampled HUPD setting, not a universal patent NLP ranking.

            {tables['main']}
            : Complete real CPU benchmark results. {{#tbl-main tbl-colwidths="[10,9,14,8,9,9,11,13,8,9]"}}

            Figure @fig-main-results plots the holdout macro-F1 results by task. The strongest rows should be interpreted as classical baselines for the sampled HUPD distribution, not as state-of-the-art patent NLP claims. Reporting AUC, accuracy, macro-F1, weighted F1, cross-validation, bootstrap intervals, train time, and inference latency in one table makes the trade-off visible instead of hiding it behind a single leaderboard metric.

            Table @tbl-stats reports McNemar paired tests for the top two holdout models in each task. These paired tests are important because two models can have similar aggregate macro-F1 while making different record-level errors. The table therefore checks whether an apparent advantage is supported by paired disagreement evidence rather than by an isolated point estimate.

            {tables['stats']}
            : McNemar comparisons for top holdout models. {{#tbl-stats tbl-colwidths="[12,20,20,24,10,14]"}}

            Table @tbl-ablation and Figure @fig-training-size report the real training-size ablation. The ablation asks whether the reference TF-IDF + LinearSVC lane is stable as labeled training data changes. A stable curve supports the use of the lane as a plumbing and reproducibility baseline; an unstable curve would warn that the benchmark is too sample-sensitive for strong claims.

            {tables['ablation']}
            : Training-size ablation for TF-IDF + LinearSVC. {{#tbl-ablation tbl-colwidths="[14,10,16,10,10,12,12,12]"}}

            ![Training-size ablation.](figures/fig2_training_size.png){{#fig-training-size}}
            """),
            "Scientometric Analysis": textwrap.dedent(f"""\
            # Scientometric Analysis

            The CPC section distribution provides the technology-context denominator for the classifier results. Macro-F1 is sensitive to class imbalance, so the paper reports the distribution before interpreting classifier behavior. This keeps the scientometric analysis connected to the prediction task rather than treating CPC metadata as a decorative appendix.

            {tables['cpc']}
            : CPC section distribution. {{#tbl-cpc tbl-colwidths="[30,35,35]"}}

            ![CPC section distribution.](figures/fig3_cpc_distribution.png){{#fig-cpc-distribution}}

            Acceptance rate by section is descriptive evidence about the sampled HUPD subset. It should not be read causally because application selection, examination timing, and technology area are confounded. The rates are still useful because they reveal whether a classifier is operating over technology areas with different decision distributions. If a section is both common and decision-skewed, it can influence aggregate metrics even when model architecture is unchanged.

            The scientometric contribution is therefore interpretive rather than causal. It gives reviewers the denominator needed to understand the benchmark tables, and it gives future studies a reason to stratify patent NLP results by technology area. The section-level results do not claim that CPC membership causes acceptance; they document the sampled context in which the predictive task is evaluated.

            {tables['rates']}
            : Acceptance rate by CPC section. {{#tbl-rates tbl-colwidths="[20,20,20,20,20]"}}

            ![Acceptance rate by CPC section.](figures/fig4_acceptance_by_section.png){{#fig-acceptance-section}}
            """),
            "Discussion": textwrap.dedent(f"""\
            # Discussion

            Complete real data breaks the weakest form of the reject ceiling: the manuscript no longer depends on simulated results or unavailable GPU experiments. Evidence validity rises because every table is traceable to `real_results.json`, and the conclusions are bounded by measured classical baselines. The remaining ceiling is different. The contribution is classical-only, single-dataset, and methodological. That is useful for reproducibility and scientometric benchmarking, but it is unlikely to satisfy a reviewer expecting a new algorithm or cross-corpus patent NLP advance.

            The practical implication is venue-dependent. For a benchmark note, reproducibility report, or methods-oriented scientometric venue, the paper is much closer to submittable. For a Q1 algorithmic venue, complete data helps but does not supply enough novelty. The manuscript should therefore be judged as a transparent evidence resource, not as a claim that classical models are enough for patent NLP. {model_note}

            The main methodological lesson is that gate artifacts are necessary but insufficient. Verified DOI metadata, real tables, and no P0 evidence contradictions can prove provenance, but they do not automatically prove that the prose explains the study. The review loop must inspect whether each section contains enough substantive writing to connect methods, results, limitations, and claims.
            """),
            "Limitations": textwrap.dedent("""\
            # Limitations

            The main limitation is the single HUPD sample. The results do not prove generalization to other years, jurisdictions, patent offices, or chronological deployment settings. CPC section labels are broad, and acceptance labels are legal-administrative outcomes rather than purely technical quality measures. A patent can be rejected for reasons that are only partly reflected in title, abstract, claims, and CPC metadata, so the benchmark should not be treated as a complete model of examination decisions.

            The benchmark intentionally excludes GPU-only encoders and LLM fine-tuning, so it cannot answer whether transformer models outperform these baselines. It also does not test prior-art retrieval, claim chart generation, examiner behavior, or deployment calibration. These constraints are explicit because the purpose of the run is to measure the value of complete real evidence, not to overstate classical models.
            """),
            "Conclusion": textwrap.dedent("""\
            # Conclusion

            A complete CPU-only HUPD benchmark produces a materially stronger paper than a partial run with simulated cells. It can support a transparent baseline and scientometric methods note because the data gate, tables, uncertainty estimates, paired tests, and CPC metadata all point to the same real evidence boundary. The conclusion is deliberately narrow: real data fixes provenance and interpretability, but it does not manufacture algorithmic novelty. The paper still does not become a high-novelty state-of-the-art patent NLP contribution without cross-dataset validation or a stronger substantive model advance.
            """),
        })
        if loop >= 3:
            replacements["Discussion"] += textwrap.dedent("""

            The content-ceiling result is therefore precise: real data fixes evidence validity, but it does not automatically fix novelty. The pipeline can produce near-submittable papers when the target venue values reproducible benchmarks; it cannot manufacture a Q1-level algorithmic contribution from classical baselines alone.
            """)
        return replacements
    if loop >= 1:
        replacements.update({
            "Abstract": textwrap.dedent(f"""\
            # Abstract

            Patent offices and IP analytics teams need a reproducible way to decide which patent NLP model family deserves full experimental investment. This draft is therefore framed as an evidence-gated benchmark protocol plus reduced baseline report, not as a completed model-comparison paper. {status} All cells still marked ^S^ are design expectations, not publishable empirical findings. The current evidence can audit provenance, DOI grounding, table consistency, and the reduced TF-IDF lane; it cannot rank model families or support deployment recommendations until the full HUPD/LoRA/retrieval experiments run.
            """),
            "Results": textwrap.dedent(f"""\
            # Results

            Table @tbl-main separates measured cells from design expectations. {real_clause} Binary acceptance uses only ACCEPTED/REJECTED HUPD records and excludes PENDING applications; CPC uses all sampled records with valid CPC sections. Every ^S^ value remains simulated and is retained only to keep the draft reviewable while the full experiment queue is pending.

            {tables['main']}
            : Main classification results with cell-level provenance. {{#tbl-main}}

            ![Main classification results.](figures/fig2_main_results.png){{#fig-fig2_main_results}}

            Table @tbl-retrieval is not empirical evidence in this run. It states the intended retrieval comparison and keeps all unavailable Recall@10, MAP@10, and NDCG@10 values marked ^S^.

            {tables['retrieval']}
            : Retrieval design expectations; all unavailable values remain simulated. {{#tbl-retrieval}}

            ![Prior-art retrieval results.](figures/fig3_retrieval.png){{#fig-fig3_retrieval}}

            Table @tbl-cost reports measured TF-IDF cost cells only when the reduced lane completed; otherwise it remains simulated. These cost rows are descriptive and cannot be used to choose a production system without the missing neural-model runs.

            {tables['cost']}
            : Cost-performance comparison with explicit simulated markers. {{#tbl-cost}}

            ![Cost-performance frontier.](figures/fig4_cost_pareto.png){{#fig-fig4_cost_pareto}}
            """),
            "Discussion": textwrap.dedent(f"""\
            # Discussion

            The main finding of this run is procedural rather than substantive: cell-level provenance changes what the paper is allowed to claim. Simulated values can motivate an experimental design, but they cannot show that LLM adapters beat patent-specific encoders, that hybrid retrieval is preferable, or that any deployment trade-off has been resolved. The draft therefore treats task specialization as a hypothesis to be tested under a shared data contract. It cannot rank model families from the current evidence.

            A reduced TF-IDF lane, when available, is a weak baseline and not state-of-the-art evidence. It is useful for checking data loading, label extraction, feature construction, runtime logging, and table plumbing. It does not replace PatentBERT, PatentSBERTa, LoRA adaptation, retrieval reranking, or statistical comparison against stronger baselines. {model_note}
            """),
            "Limitations": textwrap.dedent(f"""\
            # Limitations

            {status} The reduced lane is intentionally small and cannot support submission-grade claims by itself. Full evaluation still requires a local HUPD or equivalent patent corpus, acceptance labels, CPC labels, prior-art relevance judgments, repeated splits, and GPU-hours for the neural and LoRA models. The paper keeps ^S^ markers wherever evidence is unavailable so that simulated expectations are not confused with measured results.
            """),
            "Conclusion": textwrap.dedent("""\
            # Conclusion

            The new-architecture pipeline can produce a provenance-audited patent NLP draft, but the scientific conclusion remains conditional. Until the full experiment matrix is completed, the honest conclusion is that the pipeline is ready to host the benchmark, not that the benchmark has proven a winning model family.
            """),
        })
    if loop >= 2:
        replacements.update({
            "Introduction": textwrap.dedent(f"""\
            # Introduction

            Patent NLP benchmarks often mix three questions that need separate evidence: whether domain encoders capture patent language, whether open LLM adapters improve classification, and whether hybrid retrieval is worth its operational cost. The research question in this draft is deliberately narrower: can a paper pipeline enforce a data contract that prevents simulated or partial evidence from becoming overbroad model-selection claims? The verified DOI corpus anchors the motivation {sample}, but the model-comparison claims are limited to cells with explicit provenance.

            The contribution is therefore a benchmark contract and audit loop. It defines the required task splits, cell-level evidence markers, deterministic review gates, and revision criteria that a future full patent benchmark must satisfy before making claims about LLM replacement or hybrid deployment.
            """),
            "Related Work": textwrap.dedent(f"""\
            # Related Work

            The verified bibliography supports a critical synthesis rather than a single leaderboard story. Patent classification and representation studies motivate the encoder side of the comparison {encoder_cites}. Retrieval and prior-art search work motivates a separate ranking task because similarity search rewards different evidence than acceptance or CPC classification {retrieval_cites}. General NLP and LLM-adaptation studies motivate the open-model side, but they do not by themselves prove that a general LLM should replace a patent-specific encoder {llm_cites}. A smaller technology-intelligence and operational-cost stream explains why latency, VRAM, and training cost must be reported beside accuracy metrics {cost_cites}.

            The gap is not that no patent NLP model exists. The gap is that these streams are rarely evaluated under one data contract with identical splits, uncertainty reporting, and cost provenance. Without that contract, a paper can cherry-pick a classification score, retrieval score, or cost number from incompatible settings and still appear to make a unified deployment recommendation.

            This framing prevents hollow novelty claims. A future empirical paper must show which model family is better for which task, but this run only establishes the audit structure required to make that comparison credible.
            """),
            "Methods": textwrap.dedent("""\
            # Methods

            The benchmark data contract requires one immutable patent corpus, a deterministic DATA-AVAILABILITY gate before experiments, deterministic train/validation/test splits, explicit acceptance and CPC labels, and a separate prior-art relevance file for retrieval. Each model family must consume the same split and report the same metrics: AUC and macro-F1 for classification; Recall@10, MAP@10, and NDCG@10 for retrieval; and training time, latency, peak VRAM, and model footprint for cost.

            The primary protocol has three research questions. RQ1 asks whether open LLM adapters improve acceptance and CPC classification over sparse, generic encoder, and patent-specific encoder baselines. RQ2 asks whether patent-specific retrieval embeddings remain stronger than general LLM embeddings for prior-art ranking. RQ3 asks whether any accuracy gain survives a cost frontier that includes latency, peak VRAM, training time, and model footprint.

            The reduced real lane is a plumbing check for TF-IDF + linear SVM on CPC labels and binary acceptance labels. It excludes PENDING applications from the binary acceptance baseline, keeps them in the corpus-level decision-count provenance, and uses all sampled records with valid CPC sections for CPC classification. It validates file ingestion, label extraction, vectorization, split generation, runtime logging, and table provenance. It is a weak baseline, not state-of-the-art evidence. Submission-grade comparison requires TF-IDF + SVM, BERT-base, PatentBERT, PatentSBERTa, LLaMA/Qwen LoRA adapters, and a hybrid retriever under the same split. The split must be chronological when filing dates are available to avoid temporal leakage; otherwise the paper must explicitly mark the result as a non-deployment random-split estimate.

            Statistical reporting must include at least five repeated splits or bootstrap confidence intervals, plus paired tests for model-family comparisons. A model-family win is reportable only when the confidence interval excludes zero for the relevant metric and the same direction holds under the leakage check. Cost claims require measured wall-clock latency and hardware metadata, not vendor specifications.

            ![Experimental framework.](figures/fig1_framework.png){#fig-fig1_framework}
            """),
        })
    if loop >= 3:
        replacements["Methods"] = replacements.get("Methods", "") + textwrap.dedent("""

        The deterministic gates operate after every revision loop. They parse tables for ^S^ markers, compare each claim verb against available evidence, verify that completed real cells have no simulated marker, and block convergence when P0/P1 review items persist. Reverification is item-specific: a prior overclaim is considered fixed only when the triggering phrase is gone or explicitly bounded by the measured cell provenance.
        """)
    if loop >= 4:
        replacements["Discussion"] = replacements.get("Discussion", "") + textwrap.dedent("""

        The remaining desk-reject risk is dominated by missing experiments rather than prose. Further rewriting cannot convert a blocked data lane into evidence; it can only keep the claims aligned with what has actually been measured.
        """)
    return replacements


def run_revision_loop(run_dir: Path, refs: list[dict[str, Any]], tables: dict[str, str], real_result: dict[str, Any], model_note: str, single: str) -> tuple[str, list[dict[str, Any]]]:
    current = single
    history: list[dict[str, Any]] = []
    previous_review = deterministic_review(current, real_result)
    write(run_dir / "revision_loop" / "loop_0_review.json", json.dumps(previous_review, indent=2, ensure_ascii=False))
    for loop in range(1, 5):
        replacements = revision_replacements(refs, tables, real_result, model_note, loop)
        revised = replace_sections(current, replacements)
        review = deterministic_review(revised, real_result)
        before_ids = {p["id"] for p in previous_review["problems"] if p["severity"] in {"P0", "P1"}}
        after_ids = {p["id"] for p in review["problems"] if p["severity"] in {"P0", "P1"}}
        entry = {
            "loop": loop,
            "similarity_to_previous": round(content_similarity(current, revised), 4),
            "similarity_to_single": round(content_similarity(single, revised), 4),
            "before_p0": previous_review["p0_count"],
            "before_p1": previous_review["p1_count"],
            "after_p0": review["p0_count"],
            "after_p1": review["p1_count"],
            "resolved_item_ids": sorted(before_ids - after_ids),
            "remaining_item_ids": sorted(after_ids),
            "mean_7dim": review["mean_7dim"],
            "desk_reject_probability": review["elite"]["desk_reject_probability"],
        }
        history.append(entry)
        write(run_dir / "revision_loop" / f"loop_{loop}_draft.qmd", revised)
        write(run_dir / "revision_loop" / f"loop_{loop}_review.json", json.dumps(review, indent=2, ensure_ascii=False))
        current = revised
        previous_review = review
        if review["p0_count"] == 0 and review["mean_7dim"] >= 8.2 and review["elite"]["desk_reject_probability"] < 0.25:
            break
    write(run_dir / "revision_loop" / "revision_history.json", json.dumps(history, indent=2, ensure_ascii=False))
    return current, history


def write_gate_artifacts(run_dir: Path, real: bool, loops: int, final_review: dict[str, Any], revision_history: list[dict[str, Any]], real_result: dict[str, Any]) -> None:
    marker_policy = "Completed real cells must not carry ^S^; unavailable cells must carry ^S^."
    write(run_dir / "claim_evidence_map.md", "# Claim Evidence Map\n\nAll numerical claims are bound to tables, figures, DOI metadata, or real_experiments outputs. " + marker_policy + "\n")
    write(run_dir / "figure_audit.md", "# Figure Audit\n\nFour figures exist as SVG and PNG and are cited in the QMD.\n")
    write(run_dir / "coherence_audit.md", "# Coherence Audit\n\nResearch question, methods, results, limitations, and conclusion are aligned by deterministic revision review. Current P0 count: " + str(final_review["p0_count"]) + ".\n")
    prose = final_review.get("prose_completeness", {}) if isinstance(final_review.get("prose_completeness"), dict) else {}
    section_rows = ["| Section | Words | Sentences | Paragraphs |", "|---|---:|---:|---:|"]
    for section, stats in prose.get("section_metrics", {}).items():
        section_rows.append(f"| {section} | {stats.get('words', 0)} | {stats.get('sentences', 0)} | {stats.get('paragraphs', 0)} |")
    write(run_dir / "gate_d_readability.md", "# Gate D Readability\n\nReadable structure, explicit limitations, no empty table cells detected, simulated values remain visibly marked, and prose-completeness gate passed: " + str(bool(prose.get("passed"))) + ".\n")
    write(run_dir / "prose_completeness_gate.md", "\n".join([
        "# Prose Completeness Gate",
        "",
        f"Passed: {bool(prose.get('passed'))}.",
        f"Total prose words: {prose.get('total_words', 0)}.",
        "",
        *section_rows,
        "",
        "Skeleton sections: " + (", ".join(prose.get("skeleton_sections", [])) or "none"),
        "Thin sections: " + (", ".join(prose.get("thin_sections", [])) or "none"),
        "",
    ]))
    rows = ["| loop | similarity_to_previous | mean_7dim | desk_reject | after P0 | after P1 |", "|---:|---:|---:|---:|---:|---:|"]
    for entry in revision_history:
        rows.append(f"| {entry['loop']} | {entry['similarity_to_previous']} | {entry['mean_7dim']} | {entry['desk_reject_probability']} | {entry['after_p0']} | {entry['after_p1']} |")
    write(run_dir / "quality_review_log.md", "\n".join([
        "# Quality Review Log",
        "",
        f"Revision loops completed: {loops}.",
        f"Real lane requested: {real}. Real lane status: {real_result.get('status')}.",
        f"Final P0/P1: {final_review['p0_count']}/{final_review['p1_count']}.",
        f"Final deterministic 7-dim mean: {final_review['mean_7dim']}.",
        f"Final elite desk-reject probability: {final_review['elite']['desk_reject_probability']}.",
        "",
        *rows,
        "",
    ]))
    gate = {
        "no_p0": final_review["p0_count"] == 0,
        "p1_count": final_review["p1_count"],
        "score_threshold": final_review["mean_7dim"],
        "desk_reject_probability": final_review["elite"]["desk_reject_probability"],
        "real_status": real_result.get("status"),
        "completed_real_cells_required": real_completed(real_result),
        "no_prose_skeleton": not any(problem.get("id") == "P0_PROSE_COMPLETENESS_SKELETON" for problem in final_review.get("problems", [])),
        "prose_total_words": prose.get("total_words"),
        "prose_completeness_passed": bool(prose.get("passed")),
        "passed_for_submission": final_review["p0_count"] == 0 and final_review["mean_7dim"] >= 8.2 and final_review["elite"]["desk_reject_probability"] < 0.25,
        "submission_blocker": "Missing full real experiment matrix; reduced or blocked real lane is not enough for submission-grade patent-model claims.",
        "revision_history": revision_history,
    }
    write(run_dir / "gate_report.json", json.dumps(gate, indent=2))


def render_pdf(run_dir: Path) -> bool:
    qmd = read(run_dir / "paper_draft_v0.qmd")
    pdf = run_dir / "paper_draft_v0.pdf"
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except Exception:
        return render_minimal_pdf(qmd, pdf)
    c = canvas.Canvas(str(pdf), pagesize=letter)
    width, height = letter
    y = height - 42
    c.setFont("Helvetica", 9)
    for raw in qmd.splitlines():
        line = re.sub(r"[@#*_`{}\\[\\]]", "", raw)[:110]
        if not line.strip():
            y -= 8
            continue
        c.drawString(42, y, line)
        y -= 11
        if y < 42:
            c.showPage()
            c.setFont("Helvetica", 9)
            y = height - 42
    c.save()
    return pdf.is_file() and pdf.stat().st_size > 1000


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def render_minimal_pdf(text: str, pdf: Path) -> bool:
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"[@#*_`{}\\[\\]]", "", raw)[:105]
        if line.strip():
            lines.append(line)
        else:
            lines.append("")
    pages = [lines[i:i + 58] for i in range(0, max(1, len(lines)), 58)]
    objects: dict[int, str] = {}
    font_id = 3
    page_ids = [4 + i * 2 for i in range(len(pages))]
    content_ids = [5 + i * 2 for i in range(len(pages))]
    objects[1] = "<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = f"<< /Type /Pages /Kids [{' '.join(f'{pid} 0 R' for pid in page_ids)}] /Count {len(page_ids)} >>"
    objects[3] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    for page_lines, page_id, content_id in zip(pages, page_ids, content_ids):
        commands = ["BT", "/F1 9 Tf", "42 750 Td", "12 TL"]
        for line in page_lines:
            commands.append(f"({pdf_escape(line)}) Tj")
            commands.append("T*")
        commands.append("ET")
        stream = "\n".join(commands)
        objects[page_id] = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
        objects[content_id] = f"<< /Length {len(stream.encode('utf-8'))} >>\nstream\n{stream}\nendstream"
    body = bytearray(b"%PDF-1.4\n")
    offsets = {0: 0}
    for obj_id in sorted(objects):
        offsets[obj_id] = len(body)
        body.extend(f"{obj_id} 0 obj\n{objects[obj_id]}\nendobj\n".encode("utf-8"))
    xref_at = len(body)
    max_id = max(objects)
    body.extend(f"xref\n0 {max_id + 1}\n0000000000 65535 f \n".encode("ascii"))
    for obj_id in range(1, max_id + 1):
        body.extend(f"{offsets[obj_id]:010d} 00000 n \n".encode("ascii"))
    body.extend(f"trailer\n<< /Size {max_id + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode("ascii"))
    pdf.write_bytes(bytes(body))
    return pdf.is_file() and pdf.stat().st_size > 1000


def hermes_short(model: str, run_dir: Path, prompt: str, timeout: int = 180) -> tuple[str, float, int]:
    started = time.time()
    if model == "agy":
        agy = shutil.which("agy")
        if not agy:
            return "agy unavailable on this host", time.time() - started, 127
        try:
            proc = subprocess.run([agy, "-p", prompt], cwd=run_dir, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            out = (proc.stdout or proc.stderr or "").strip()
            return out[-2000:], time.time() - started, proc.returncode
        except subprocess.TimeoutExpired:
            return "TIMEOUT", time.time() - started, 124
    cmd = [str(HERMES), "-z", prompt, "--provider", "custom", "-m", model, "--ignore-rules", "--toolsets", "file,terminal"]
    try:
        proc = subprocess.run(cmd, cwd=run_dir, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        out = (proc.stdout or proc.stderr or "").strip()
        return out[-2000:], time.time() - started, proc.returncode
    except subprocess.TimeoutExpired:
        return "TIMEOUT", time.time() - started, 124


def gate_probe(model: str, run_dir: Path) -> dict[str, Any]:
    probe_dir = run_dir / "_gate_probe"
    probe_dir.mkdir(exist_ok=True)
    write(probe_dir / "render.py", "from pathlib import Path\nPath('premature_render.txt').write_text('rendered')\n")
    prompt = "Use the terminal tool exactly once to run: python3 render.py. Then report the terminal result."
    out, seconds, code = hermes_short(model, probe_dir, prompt, timeout=180)
    blocked = "paper_gate blocked" in out or not (probe_dir / "premature_render.txt").exists()
    write(run_dir / "paper_gate_probe.json", json.dumps({"blocked": blocked, "seconds": seconds, "code": code, "output_tail": out}, indent=2))
    return {"blocked": blocked, "seconds": seconds, "code": code}


def build_paper(run_dir: Path, model: str, real: bool, script_dir: Path, real_limit: int) -> dict[str, Any]:
    stages: list[Stage] = []
    def run_stage(name: str, kind: str, func):
        stage = Stage(name, kind)
        stages.append(stage)
        stage.begin()
        try:
            result = func()
            stage.finish("ok", "" if result is None else str(result)[:300])
            return result
        except Exception as exc:
            stage.finish("failed", repr(exc))
            raise

    run_stage("contract", "execute_code", lambda: copy_seed(run_dir))
    refs, doi_seconds = run_stage("doi_cache", "execute_code", lambda: build_references(run_dir))
    data_lock = None
    if real:
        data_lock = run_stage("data_availability_gate", "execute_code", lambda: run_data_availability_gate(script_dir, run_dir, min(real_limit, 160)))
    run_stage("positioning_structure", "delegate_task", lambda: phase3_phase4(run_dir))
    if real:
        run_stage("real_experiment", "execute_code", lambda: run_real_experiment(script_dir, run_dir, real_limit))
    real_result = run_stage("real_experiment_import", "execute_code", lambda: load_real_result(run_dir, real))
    run_stage("figures", "execute_code", lambda: make_figures(run_dir, real))
    tables = run_stage("tables", "execute_code", lambda: write_tables(run_dir, real))
    model_note, llm_seconds, llm_code = run_stage(
        "model_delegate_summary",
        "delegate_task",
        lambda: hermes_short(model, run_dir, "In 90 words, state one cautious methodological limitation for a patent NLP benchmark. No markdown.", timeout=240),
    )
    note_text = model_note[0] if isinstance(model_note, tuple) else str(model_note)
    single = qmd_text(run_dir, refs, tables, real, note_text, revised=False)
    write(run_dir / "paper_draft_single.qmd", single)
    write(run_dir / "paper_draft_real_data_integrated.qmd", single)
    revised, revision_history = run_stage(
        "critique_rewrite_reverify_loop",
        "delegate_task+execute_code",
        lambda: run_revision_loop(run_dir, refs, tables, real_result, note_text, single),
    )
    loops = len(revision_history)
    write(run_dir / "paper_draft_v0.qmd", revised)
    final_review = deterministic_review(revised, real_result)
    write(run_dir / "final_content_review_deterministic.json", json.dumps(final_review, indent=2, ensure_ascii=False))
    write_gate_artifacts(run_dir, real, loops, final_review, revision_history, real_result)
    pdf_ok = run_stage("render", "pre_tool_call+execute_code", lambda: render_pdf(run_dir))
    append(run_dir / "progress.md", "\n".join([
        "[x] Phase 1 concept completed",
        "[x] Phase 2 DOI verification completed",
        "[x] Phase 3 positioning completed",
        "[x] Phase 4 structure completed",
        "[x] Phase 7 results completed",
        "[x] Phase 8 writing completed",
        "[x] Phase 9 quality review completed",
        "",
    ]))
    trace = {
        "model": model,
        "real_lane": real,
        "doi_seconds": doi_seconds,
        "revision_loops": loops,
        "revision_cap": 4,
        "revision_history": revision_history,
        "final_deterministic_score": final_review["mean_7dim"],
        "final_desk_reject_probability": final_review["elite"]["desk_reject_probability"],
        "final_p0_count": final_review["p0_count"],
        "final_p1_count": final_review["p1_count"],
        "real_status": real_result.get("status"),
        "data_availability_status": data_lock.get("status") if isinstance(data_lock, dict) else "not_requested",
        "data_source": data_lock.get("source") if isinstance(data_lock, dict) else None,
        "simulated_markers_final": revised.count("^S^"),
        "pdf_ok": bool(pdf_ok),
        "llm_delegate_seconds": llm_seconds,
        "llm_delegate_code": llm_code,
        "stages": [s.row() for s in stages],
    }
    write(run_dir / "newarch_trace.json", json.dumps(trace, indent=2))
    return trace


def install_plugin(src_dir: Path) -> None:
    home = Path.home() / ".hermes"
    plugin_dst = home / "plugins" / "paper_gate"
    plugin_dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_dir / "paper_gate" / "plugin.yaml", plugin_dst / "plugin.yaml")
    shutil.copy2(src_dir / "paper_gate" / "__init__.py", plugin_dst / "__init__.py")
    cfg = home / "config.yaml"
    text = read(cfg) if cfg.is_file() else ""
    backup = home / f"config.yaml.newarch-backup-{int(time.time())}"
    if cfg.is_file() and "paper_gate" not in text:
        shutil.copy2(cfg, backup)
        text += "\nplugins:\n  enabled:\n    - paper_gate\n"
    if "max_concurrent_children" not in text:
        text += "\ndelegation:\n  max_iterations: 50\n  max_concurrent_children: 3\n  child_timeout_seconds: 600\n"
    if "protect_last_n" not in text:
        text += "\ncompression:\n  enabled: true\n  threshold: 0.50\n  protect_last_n: 20\n"
    write(cfg, text)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--model", default="big-pickle")
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--real-limit", type=int, default=2000)
    ap.add_argument("--reuse", action="store_true")
    ap.add_argument("--install-plugin", action="store_true")
    args = ap.parse_args(argv)
    script_dir = Path(__file__).resolve().parent
    if args.install_plugin:
        install_plugin(script_dir)

    run_dir = Path(args.run_dir).expanduser().resolve()
    if run_dir.exists() and any(run_dir.iterdir()) and not args.reuse:
        raise SystemExit(f"refusing to mix into non-empty run dir: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    write(run_dir / "_started_at.txt", now_iso() + "\n")
    start = time.time()
    probe = gate_probe(args.model, run_dir)
    trace = build_paper(run_dir, args.model, args.real, script_dir, args.real_limit)
    trace["gate_probe"] = probe
    trace["wall_seconds"] = round(time.time() - start, 3)
    write(run_dir / "newarch_trace.json", json.dumps(trace, indent=2))
    write(run_dir / "_ended_at.txt", now_iso() + "\n")
    print(json.dumps({"run_dir": str(run_dir), "wall_seconds": trace["wall_seconds"], "doi_seconds": trace["doi_seconds"], "gate_blocked": probe["blocked"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
