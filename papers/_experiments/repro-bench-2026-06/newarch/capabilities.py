"""a-side capability advertisement + experiment executability validation.

`/capabilities` lets b negotiate: it submits a v2 Contract ONLY when a advertises a
matching schema_hash + contract_version + recipe_id. Schema is served (not duplicated in
both repos) and every job pins the schema_hash both sides log.

`validate_experiment_contract` proves a v2 experiment block is EXECUTABLE against an
a-side recipe registry BEFORE the job runs (codex: schema validity != executability).
After the run, `validate_real_results` compares actual output to the resolved plan.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = SCRIPT_DIR / "assets" / "contract_v2.schema.json"
RECIPES_DIR = SCRIPT_DIR / "recipes"
RESULT_SCHEMA_VERSION = "2026-06-06-a"
MAX_PAYLOAD_BYTES = 1_000_000


def schema_text() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8") if SCHEMA_PATH.is_file() else "{}"


def schema_hash() -> str:
    return hashlib.sha256(schema_text().encode("utf-8")).hexdigest()[:16]


def _recipes() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if RECIPES_DIR.is_dir():
        for p in sorted(RECIPES_DIR.glob("*.json")):
            try:
                out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
    return out


def capabilities() -> dict[str, Any]:
    return {
        "contract_versions": [1, 2],
        "schema_hash": schema_hash(),
        "schema_url": "/schema/contract_v2.schema.json",
        "experiment_recipe_ids": sorted(_recipes().keys()),
        "max_payload_bytes": MAX_PAYLOAD_BYTES,
        "renderer": "elsevier-pdf/xelatex",
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "reviewer_chain": ["copilot", "deterministic_floor"],
    }


def _subset(requested: Any, allowed: list[str], label: str, errors: list[str]) -> None:
    for item in (requested or []):
        name = item if isinstance(item, str) else (item.get("name") if isinstance(item, dict) else None)
        if name is not None and name not in allowed:
            errors.append(f"{label}: '{name}' not supported by recipe (allowed: {allowed})")


def validate_experiment_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """Validate a v2 experiment block against the recipe registry. Returns
    {ok, errors, recipe_id, resolved_plan}. Unsupported fields are reported (caller may
    reject or downgrade). A contract with no experiment block is OK (v1 / non-experiment)."""
    exp = contract.get("experiment")
    if not isinstance(exp, dict):
        return {"ok": True, "errors": [], "recipe_id": None, "resolved_plan": None,
                "note": "no experiment block (v1 / model-driven path)"}
    recipes = _recipes()
    rid = exp.get("recipe_id")
    errors: list[str] = []
    if rid not in recipes:
        return {"ok": False, "errors": [f"unknown experiment recipe_id '{rid}' (have: {sorted(recipes)})"],
                "recipe_id": rid, "resolved_plan": None}
    r = recipes[rid]
    _subset(exp.get("tasks"), r.get("tasks", []), "task", errors)
    _subset(exp.get("models"), r.get("models", []), "model", errors)
    _subset(exp.get("metrics"), r.get("metrics", []), "metric", errors)
    ev = exp.get("eval_protocol") or {}
    if ev.get("cv_folds") is not None and ev["cv_folds"] not in r.get("eval_protocol", {}).get("cv_folds", []):
        errors.append(f"cv_folds={ev['cv_folds']} not in {r.get('eval_protocol', {}).get('cv_folds')}")
    bi_max = r.get("eval_protocol", {}).get("bootstrap_iters_max")
    if ev.get("bootstrap_iters") and bi_max and ev["bootstrap_iters"] > bi_max:
        errors.append(f"bootstrap_iters={ev['bootstrap_iters']} exceeds max {bi_max}")
    resolved = {
        "recipe_id": rid,
        "tasks": [t.get("name") if isinstance(t, dict) else t for t in (exp.get("tasks") or r.get("tasks", []))],
        "models": exp.get("models") or r.get("models", []),
        "metrics": exp.get("metrics") or r.get("metrics", []),
        "eval_protocol": {**r.get("eval_protocol", {}), **ev},
        "expected_real_results_keys": r.get("expected_real_results_keys", []),
        "min_rows": r.get("min_rows"), "min_classes": r.get("min_classes"),
    }
    return {"ok": not errors, "errors": errors, "recipe_id": rid, "resolved_plan": resolved}


def validate_real_results(real_results: dict[str, Any], resolved_plan: dict[str, Any]) -> list[str]:
    """Post-run: actual results must satisfy the resolved plan."""
    errs: list[str] = []
    if str(real_results.get("status")) != "completed":
        errs.append(f"real_results.status != completed ({real_results.get('status')})")
    if real_results.get("simulated"):
        errs.append("real_results.simulated is true")
    for k in resolved_plan.get("expected_real_results_keys", []):
        if k not in real_results:
            errs.append(f"missing expected key '{k}' in real_results")
    got_tasks = set(real_results.get("tasks") or [])
    want_tasks = set(resolved_plan.get("tasks") or [])
    if want_tasks and not want_tasks.issubset(got_tasks):
        errs.append(f"tasks {sorted(want_tasks - got_tasks)} missing from real_results")
    return errs
