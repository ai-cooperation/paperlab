#!/usr/bin/env python3
"""Complete CPU-only HUPD classical-ML benchmark lane.

This module intentionally contains no simulated fallback. It streams real HUPD
sample rows, runs sparse classical baselines on CPU, and writes a fail-closed
`real_results.json` if any required data or experiment stage cannot complete.
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from data_availability_gate import collect_hupd_sample_rows, probe_hupd, require_available


MODEL_NAMES = [
    "LogisticRegression",
    "LinearSVC",
    "RandomForest",
    "GradientBoosting",
    "MultinomialNB",
]
FEATURE_NAMES = ["tfidf", "bow"]
TASK_NAMES = ["acceptance", "cpc_section"]


def write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


def text_from_row(row: dict[str, str], fields: tuple[str, ...] = ("title", "abstract", "claims")) -> str:
    return " ".join(str(row.get(field) or "").strip() for field in fields).strip()


def label_counts(labels: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(labels).items()))


def filter_min_count(rows: list[dict[str, str]], key: str, min_count: int) -> list[dict[str, str]]:
    counts = Counter(row[key] for row in rows if str(row.get(key) or "").strip())
    keep = {label for label, count in counts.items() if count >= min_count}
    return [row for row in rows if row.get(key) in keep]


def prepare_tasks(rows: list[dict[str, str]], cv_splits: int) -> dict[str, dict[str, Any]]:
    acceptance_rows = [
        row for row in rows
        if row.get("decision") in {"ACCEPTED", "REJECTED"} and text_from_row(row)
    ]
    cpc_rows = [
        row for row in rows
        if str(row.get("cpc_section") or "").strip() and text_from_row(row)
    ]
    cpc_rows = filter_min_count(cpc_rows, "cpc_section", cv_splits)
    tasks = {
        "acceptance": {
            "rows": acceptance_rows,
            "label_key": "decision",
            "positive_label": "ACCEPTED",
            "description": "Binary ACCEPTED vs REJECTED prediction; PENDING records excluded.",
        },
        "cpc_section": {
            "rows": cpc_rows,
            "label_key": "cpc_section",
            "positive_label": None,
            "description": "Multi-class CPC section classification from patent text.",
        },
    }
    for name, task in tasks.items():
        labels = [row[task["label_key"]] for row in task["rows"]]
        counts = Counter(labels)
        if len(counts) < 2:
            raise RuntimeError(f"{name} has fewer than 2 classes after filtering: {dict(counts)}")
        if min(counts.values()) < 2:
            raise RuntimeError(f"{name} has a class with fewer than 2 rows: {dict(counts)}")
    return tasks


def build_vectorizer(feature_name: str, max_features: int):
    from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer

    kwargs = {
        "max_features": max_features,
        "ngram_range": (1, 2),
        "min_df": 1,
        "max_df": 0.98,
        "lowercase": True,
        "strip_accents": "unicode",
    }
    if feature_name == "tfidf":
        return TfidfVectorizer(sublinear_tf=True, norm="l2", **kwargs)
    if feature_name == "bow":
        return CountVectorizer(binary=False, **kwargs)
    raise ValueError(f"unknown feature family: {feature_name}")


def build_model(model_name: str, random_state: int):
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.svm import LinearSVC

    if model_name == "LogisticRegression":
        return LogisticRegression(max_iter=1200, class_weight="balanced", n_jobs=1, random_state=random_state)
    if model_name == "LinearSVC":
        return LinearSVC(class_weight="balanced", dual=False, random_state=random_state)
    if model_name == "RandomForest":
        return RandomForestClassifier(
            n_estimators=80,
            max_depth=24,
            min_samples_leaf=2,
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=random_state,
        )
    if model_name == "GradientBoosting":
        return GradientBoostingClassifier(
            n_estimators=45,
            learning_rate=0.08,
            max_depth=2,
            subsample=0.85,
            random_state=random_state,
        )
    if model_name == "MultinomialNB":
        return MultinomialNB(alpha=0.5)
    raise ValueError(f"unknown model: {model_name}")


def build_pipeline(feature_name: str, model_name: str, max_features: int, random_state: int):
    from sklearn.pipeline import Pipeline

    return Pipeline([
        ("features", build_vectorizer(feature_name, max_features)),
        ("model", build_model(model_name, random_state)),
    ])


def score_matrix(pipe: Any, texts: list[str]) -> np.ndarray | None:
    if hasattr(pipe, "predict_proba"):
        try:
            return np.asarray(pipe.predict_proba(texts))
        except Exception:
            return None
    if hasattr(pipe, "decision_function"):
        try:
            scores = np.asarray(pipe.decision_function(texts))
            return scores
        except Exception:
            return None
    return None


def auc_score(y_true: list[str], scores: np.ndarray | None, classes: np.ndarray, positive_label: str | None) -> float | None:
    from sklearn.metrics import roc_auc_score

    if scores is None or len(set(y_true)) < 2:
        return None
    try:
        if len(classes) == 2:
            positive = positive_label if positive_label in set(classes) else classes[1]
            if scores.ndim == 1:
                score_1d = scores if classes[1] == positive else -scores
            else:
                pos_idx = list(classes).index(positive)
                score_1d = scores[:, pos_idx]
            y_bin = np.asarray([1 if label == positive else 0 for label in y_true])
            return float(roc_auc_score(y_bin, score_1d))
        if scores.ndim == 1:
            return None
        return float(roc_auc_score(y_true, scores, labels=list(classes), multi_class="ovr", average="macro"))
    except Exception:
        return None


def metric_bundle(
    y_true: list[str],
    y_pred: list[str],
    scores: np.ndarray | None,
    classes: np.ndarray,
    positive_label: str | None,
) -> dict[str, float | None]:
    from sklearn.metrics import accuracy_score, f1_score

    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "f1_weighted": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
        "auc": auc_score(y_true, scores, classes, positive_label),
    }


def bootstrap_ci(
    y_true: list[str],
    y_pred: list[str],
    scores: np.ndarray | None,
    classes: np.ndarray,
    positive_label: str | None,
    samples: int,
    random_state: int,
) -> dict[str, list[float] | None]:
    if samples <= 1:
        return {"accuracy": None, "f1_macro": None, "auc": None}
    rng = np.random.default_rng(random_state)
    y_true_arr = np.asarray(y_true)
    y_pred_arr = np.asarray(y_pred)
    n = len(y_true_arr)
    values: dict[str, list[float]] = {"accuracy": [], "f1_macro": [], "auc": []}
    for _ in range(samples):
        idx = rng.integers(0, n, n)
        if len(set(y_true_arr[idx])) < 2:
            continue
        sample_scores = scores[idx] if scores is not None and len(scores) == n else None
        bundle = metric_bundle(
            y_true_arr[idx].tolist(),
            y_pred_arr[idx].tolist(),
            sample_scores,
            classes,
            positive_label,
        )
        for key in values:
            value = bundle[key]
            if value is not None and np.isfinite(value):
                values[key].append(float(value))
    ci: dict[str, list[float] | None] = {}
    for key, vals in values.items():
        if vals:
            ci[key] = [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]
        else:
            ci[key] = None
    return ci


def cv_metrics(
    texts: list[str],
    labels: list[str],
    task_name: str,
    positive_label: str | None,
    feature_name: str,
    model_name: str,
    cv_splits: int,
    max_features: int,
    random_state: int,
) -> tuple[dict[str, dict[str, float | int | None]], int]:
    from sklearn.model_selection import StratifiedKFold

    counts = Counter(labels)
    splits = min(cv_splits, min(counts.values()))
    if splits < 2:
        raise RuntimeError(f"{task_name} cannot run CV with class counts {dict(counts)}")
    skf = StratifiedKFold(n_splits=splits, shuffle=True, random_state=random_state)
    fold_values: dict[str, list[float]] = defaultdict(list)
    for fold, (train_idx, test_idx) in enumerate(skf.split(texts, labels), start=1):
        x_train = [texts[i] for i in train_idx]
        y_train = [labels[i] for i in train_idx]
        x_test = [texts[i] for i in test_idx]
        y_test = [labels[i] for i in test_idx]
        pipe = build_pipeline(feature_name, model_name, max_features, random_state + fold)
        pipe.fit(x_train, y_train)
        pred = pipe.predict(x_test).tolist()
        scores = score_matrix(pipe, x_test)
        classes = np.asarray(pipe.classes_)
        bundle = metric_bundle(y_test, pred, scores, classes, positive_label)
        for key, value in bundle.items():
            if value is not None and np.isfinite(value):
                fold_values[key].append(float(value))
    summary: dict[str, dict[str, float | int | None]] = {}
    for metric in ["accuracy", "f1_macro", "f1_weighted", "auc"]:
        vals = fold_values.get(metric, [])
        summary[metric] = {
            "mean": float(np.mean(vals)) if vals else None,
            "std": float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0 if vals else None,
            "n_folds": len(vals),
        }
    return summary, splits


def run_one_combo(
    texts: list[str],
    labels: list[str],
    task_name: str,
    positive_label: str | None,
    feature_name: str,
    model_name: str,
    cv_splits: int,
    max_features: int,
    bootstrap_samples: int,
    random_state: int,
) -> tuple[dict[str, Any], list[str], list[str]]:
    from sklearn.model_selection import train_test_split

    x_train, x_test, y_train, y_test = train_test_split(
        texts,
        labels,
        test_size=0.25,
        random_state=random_state,
        stratify=labels,
    )
    pipe = build_pipeline(feature_name, model_name, max_features, random_state)
    t0 = time.time()
    pipe.fit(x_train, y_train)
    train_seconds = time.time() - t0
    t1 = time.time()
    pred = pipe.predict(x_test).tolist()
    inference_ms = (time.time() - t1) * 1000 / max(1, len(x_test))
    scores = score_matrix(pipe, x_test)
    classes = np.asarray(pipe.classes_)
    holdout = metric_bundle(y_test, pred, scores, classes, positive_label)
    ci = bootstrap_ci(y_test, pred, scores, classes, positive_label, bootstrap_samples, random_state)
    cv, splits = cv_metrics(
        texts,
        labels,
        task_name,
        positive_label,
        feature_name,
        model_name,
        cv_splits,
        max_features,
        random_state,
    )
    row = {
        "task": task_name,
        "feature": feature_name,
        "model": model_name,
        "n_rows": len(texts),
        "n_classes": len(set(labels)),
        "class_counts": label_counts(labels),
        "holdout": holdout,
        "bootstrap_ci_95": ci,
        "cv": cv,
        "cv_splits": splits,
        "train_seconds": float(train_seconds),
        "inference_ms_per_sample": float(inference_ms),
        "hardware": "CPU",
        "gpu_used": False,
    }
    return row, y_test, pred


def mcnemar_compare(y_true: list[str], pred_a: list[str], pred_b: list[str]) -> dict[str, Any]:
    a_correct = np.asarray(pred_a) == np.asarray(y_true)
    b_correct = np.asarray(pred_b) == np.asarray(y_true)
    both_correct = int(np.sum(a_correct & b_correct))
    a_only = int(np.sum(a_correct & ~b_correct))
    b_only = int(np.sum(~a_correct & b_correct))
    both_wrong = int(np.sum(~a_correct & ~b_correct))
    table = [[both_correct, a_only], [b_only, both_wrong]]
    try:
        from statsmodels.stats.contingency_tables import mcnemar

        exact = a_only + b_only < 25
        result = mcnemar(table, exact=exact, correction=not exact)
        statistic = None if exact else float(result.statistic)
        p_value = float(result.pvalue)
        method = "statsmodels.mcnemar_exact" if exact else "statsmodels.mcnemar_chi2_corrected"
    except Exception:
        from scipy.stats import binomtest

        discordant = a_only + b_only
        p_value = float(binomtest(min(a_only, b_only), discordant, 0.5).pvalue) if discordant else 1.0
        statistic = None
        method = "scipy.binomtest_fallback"
    return {
        "method": method,
        "contingency_table": table,
        "statistic": statistic,
        "p_value": p_value,
    }


def statistical_tests(benchmark: list[dict[str, Any]], predictions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    tests: list[dict[str, Any]] = []
    for task in TASK_NAMES:
        task_rows = [row for row in benchmark if row["task"] == task]
        ranked = sorted(
            task_rows,
            key=lambda row: (
                row["holdout"]["f1_macro"] if row["holdout"]["f1_macro"] is not None else -1,
                row["holdout"]["accuracy"] if row["holdout"]["accuracy"] is not None else -1,
            ),
            reverse=True,
        )
        if len(ranked) < 2:
            continue
        best, challenger = ranked[0], ranked[1]
        key_best = f"{best['task']}::{best['feature']}::{best['model']}"
        key_challenger = f"{challenger['task']}::{challenger['feature']}::{challenger['model']}"
        pred_best = predictions[key_best]
        pred_challenger = predictions[key_challenger]
        test = mcnemar_compare(pred_best["y_true"], pred_best["y_pred"], pred_challenger["y_pred"])
        test.update({
            "task": task,
            "metric_for_ranking": "holdout.f1_macro",
            "model_a": {"feature": best["feature"], "model": best["model"], "f1_macro": best["holdout"]["f1_macro"]},
            "model_b": {"feature": challenger["feature"], "model": challenger["model"], "f1_macro": challenger["holdout"]["f1_macro"]},
        })
        tests.append(test)
    return tests


def training_size_curve(
    task_name: str,
    texts: list[str],
    labels: list[str],
    positive_label: str | None,
    max_features: int,
    random_state: int,
) -> list[dict[str, Any]]:
    from sklearn.model_selection import train_test_split

    x_train, x_test, y_train, y_test = train_test_split(
        texts,
        labels,
        test_size=0.25,
        random_state=random_state,
        stratify=labels,
    )
    out: list[dict[str, Any]] = []
    for fraction in [0.25, 0.50, 1.00]:
        if fraction < 1:
            subset_x, _, subset_y, _ = train_test_split(
                x_train,
                y_train,
                train_size=fraction,
                random_state=random_state,
                stratify=y_train,
            )
        else:
            subset_x, subset_y = x_train, y_train
        pipe = build_pipeline("tfidf", "LinearSVC", max_features, random_state)
        pipe.fit(subset_x, subset_y)
        pred = pipe.predict(x_test).tolist()
        scores = score_matrix(pipe, x_test)
        metrics = metric_bundle(y_test, pred, scores, np.asarray(pipe.classes_), positive_label)
        out.append({
            "task": task_name,
            "feature": "tfidf",
            "model": "LinearSVC",
            "train_fraction": fraction,
            "n_train": len(subset_x),
            "holdout": metrics,
        })
    return out


def scientometrics(rows: list[dict[str, str]]) -> dict[str, Any]:
    cpc_counts = Counter(row.get("cpc_section") for row in rows if row.get("cpc_section"))
    decision_counts = Counter(row.get("decision") for row in rows if row.get("decision"))
    total_cpc = sum(cpc_counts.values()) or 1
    section_decisions: dict[str, Counter[str]] = defaultdict(Counter)
    filing_years: Counter[str] = Counter()
    for row in rows:
        section = row.get("cpc_section")
        decision = row.get("decision")
        if section and decision in {"ACCEPTED", "REJECTED"}:
            section_decisions[section][decision] += 1
        filing = str(row.get("filing_date") or "")
        if len(filing) >= 4 and filing[:4].isdigit():
            filing_years[filing[:4]] += 1
    acceptance_rate_by_section = {}
    for section, counts in sorted(section_decisions.items()):
        accepted = counts.get("ACCEPTED", 0)
        rejected = counts.get("REJECTED", 0)
        n = accepted + rejected
        acceptance_rate_by_section[section] = {
            "accepted": int(accepted),
            "rejected": int(rejected),
            "n_binary": int(n),
            "acceptance_rate": float(accepted / n) if n else None,
        }
    return {
        "cpc_distribution": {
            section: {"count": int(count), "proportion": float(count / total_cpc)}
            for section, count in sorted(cpc_counts.items())
        },
        "decision_counts": dict(sorted((k, int(v)) for k, v in decision_counts.items())),
        "acceptance_rate_by_section": acceptance_rate_by_section,
        "filing_year_distribution": dict(sorted((k, int(v)) for k, v in filing_years.items())),
    }


def run_full_benchmark(
    rows: list[dict[str, str]],
    cv_splits: int = 5,
    max_features: int = 3000,
    bootstrap_samples: int = 300,
    random_state: int = 42,
) -> dict[str, Any]:
    started = time.time()
    if len(rows) < 40:
        raise RuntimeError(f"insufficient HUPD rows: {len(rows)}")
    tasks = prepare_tasks(rows, cv_splits)
    benchmark: list[dict[str, Any]] = []
    predictions: dict[str, dict[str, Any]] = {}
    task_summaries: dict[str, Any] = {}
    for task_name, task in tasks.items():
        task_rows = task["rows"]
        texts = [text_from_row(row) for row in task_rows]
        labels = [row[task["label_key"]] for row in task_rows]
        task_summaries[task_name] = {
            "description": task["description"],
            "n_rows": len(task_rows),
            "class_counts": label_counts(labels),
        }
        for feature_name in FEATURE_NAMES:
            for model_name in MODEL_NAMES:
                row, y_true, pred = run_one_combo(
                    texts,
                    labels,
                    task_name,
                    task["positive_label"],
                    feature_name,
                    model_name,
                    cv_splits,
                    max_features,
                    bootstrap_samples,
                    random_state,
                )
                benchmark.append(row)
                predictions[f"{task_name}::{feature_name}::{model_name}"] = {
                    "y_true": y_true,
                    "y_pred": pred,
                }
    ablations = {
        "training_size_curve": [
            point
            for task_name, task in tasks.items()
            for point in training_size_curve(
                task_name,
                [text_from_row(row) for row in task["rows"]],
                [row[task["label_key"]] for row in task["rows"]],
                task["positive_label"],
                max_features,
                random_state,
            )
        ],
    }
    return {
        "status": "completed",
        "source": "HUPD/hupd sample-jan-2016",
        "source_type": "dataset",
        "rows": len(rows),
        "tasks": TASK_NAMES,
        "task_summaries": task_summaries,
        "features": FEATURE_NAMES,
        "models": MODEL_NAMES,
        "benchmark": benchmark,
        "statistical_tests": {"mcnemar": statistical_tests(benchmark, predictions)},
        "ablations": ablations,
        "scientometrics": scientometrics(rows),
        "cv_requested": cv_splits,
        "max_features": max_features,
        "bootstrap_samples": bootstrap_samples,
        "random_state": random_state,
        "hardware": {
            "device": "CPU",
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python": platform.python_version(),
        },
        "gpu_used": False,
        "simulation_markers": 0,
        "simulated": False,
        "wall_seconds": time.time() - started,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=2000)
    ap.add_argument("--cv-splits", type=int, default=5)
    ap.add_argument("--max-features", type=int, default=3000)
    ap.add_argument("--bootstrap-samples", type=int, default=300)
    ap.add_argument("--random-state", type=int, default=42)
    args = ap.parse_args()
    out = Path(args.out).expanduser().resolve()
    started = time.time()
    try:
        if args.limit < 2000:
            raise RuntimeError("complete CPU benchmark requires --limit >= 2000")
        lock = probe_hupd(out, sample_rows=min(args.limit, 200))
        require_available(lock)
        rows = collect_hupd_sample_rows(args.limit)
        if len(rows) < args.limit:
            raise RuntimeError(f"HUPD returned {len(rows)} valid rows, requested {args.limit}")
        result = run_full_benchmark(
            rows,
            cv_splits=args.cv_splits,
            max_features=args.max_features,
            bootstrap_samples=args.bootstrap_samples,
            random_state=args.random_state,
        )
        result["data_source_lock"] = str(out / "data_source_lock.json")
    except Exception as exc:
        result = {
            "status": "blocked",
            "reason": repr(exc),
            "needed": "Reachable HUPD sample tar + metadata with >=2000 real patent rows and usable decision/CPC/text fields.",
            "gpu_used": False,
            "simulation_markers": 0,
            "simulated": False,
            "wall_seconds": time.time() - started,
        }
    write(out / "real_results.json", json.dumps(result, indent=2))
    title = "# Complete Real HUPD Classical-ML Benchmark\n\n"
    write(out / "real_experiment_report.md", title + json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
