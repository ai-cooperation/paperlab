#!/usr/bin/env python3
"""Phase-0 plan calibration — run BEFORE the 12-phase pipeline.

The grill (a weak model on the user's phone) can over-commit the plan: promise a
moderation analysis the abstract-level data can't power, put a moderator term in
the search query, frame a saturated gap as novel. Today a executes that plan
blindly through 12 phases + 3 review loops and only discovers the over-reach when
the reviewer penalises the finished paper — a wasted 30-60 min run.

Phase-0 moves the judgement upstream: a cheap feasibility probe (how much will
actually pool?) + a single codex calibration pass that (a) decides viability,
(b) assesses whether the gap is real or saturated, and (c) rewrites the contract
to match what the data supports — or blocks fast with an actionable reason.

Division of labour: the irreducible judgement (is this answerable / valuable?)
goes to the strong model ONCE upstream; a DETERMINISTIC floor still blocks the
hard-infeasible cases when codex is unavailable, so the gate never silently
passes a doomed plan.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

MIN_POOLABLE_K = 3       # below this, nothing meaningful can be pooled -> block
QUALITY_K = 8            # below this, a SATURATED question is not worth a thin re-do
MODERATION_MIN_K = 10    # a subgroup/moderation claim needs at least this many
CODEX_BIN = os.environ.get("PAPER_CODEX_BIN", "codex")
CODEX_AUTH_DIR = Path(os.environ.get("PAPER_CODEX_AUTH_DIR", str(Path.home() / ".codex")))


def feasibility_probe(run_dir: Path, query: str, syn_type: str,
                      picos: dict[str, Any]) -> dict[str, Any]:
    """Lightweight count of what this plan would actually pool — runs the real
    meta_analysis extraction to a scratch dir (no paper written) and reports the
    poolable k per scale. Collects through the SHARED job cache so the real run
    reuses the same corpus (one collect per job, no re-hammering the source)."""
    import meta_analysis
    probe_dir = run_dir / "_phase0_probe"
    if probe_dir.exists():
        shutil.rmtree(probe_dir, ignore_errors=True)
    try:
        r = meta_analysis.run(query, probe_dir, max_works=2400,
                              syn_type=syn_type, picos_spec=picos,
                              cache_path=run_dir / "_corpus_cache.json")
    except Exception as exc:  # noqa: BLE001 - probe failure -> let codex/floor decide
        return {"status": "error", "reason": str(exc)[:200], "max_poolable_k": 0}
    if r.get("status") != "completed":
        return {"status": r.get("status"), "reason": r.get("reason"),
                "max_poolable_k": 0, "prisma": r.get("prisma")}
    m = r.get("meta") or {}
    pooled = m.get("pooled") or {}
    ks = {s: p.get("k") for s, p in pooled.items()}
    return {
        "status": "completed",
        "total_studies": (m.get("prisma") or {}).get("studies_with_effects"),
        "excluded_picos": (m.get("prisma") or {}).get("excluded_picos"),
        "by_scale_counts": m.get("by_measure_counts"),
        "poolable_k": ks,
        "max_poolable_k": max([k for k in ks.values() if isinstance(k, int)], default=0),
    }


def _title_promises_moderation(contract: dict[str, Any]) -> bool:
    text = (str(contract.get("topic") or "") + " " + str(contract.get("contribution") or "")).lower()
    cues = ["moderat", "subgroup", "stratif", "調節", "次群組", "分層", "meta-regression",
            "delivery mode", "delivery format", "傳遞形式", "by ", "differ"]
    return any(c in text for c in cues)


def deterministic_floor(contract: dict[str, Any], probe: dict[str, Any]) -> dict[str, Any]:
    """Hard viability rules that hold regardless of codex. A floor BLOCK cannot be
    overridden by codex (a doomed plan stays doomed); a floor DOWNGRADE is advisory."""
    k = int(probe.get("max_poolable_k") or 0)
    if probe.get("status") != "completed" or k < MIN_POOLABLE_K:
        return {"viable": False,
                "reason": f"abstract-level extraction yields only {k} poolable studies "
                          f"(need >= {MIN_POOLABLE_K}); not viable as a meta-analysis for this "
                          "topic/type. Reframe the question or pick a less data-sparse topic.",
                "downgrade_moderation": False}
    downgrade = _title_promises_moderation(contract) and k < MODERATION_MIN_K
    return {"viable": True, "reason": "", "downgrade_moderation": downgrade, "k": k}


def _build_prompt(contract: dict[str, Any], probe: dict[str, Any]) -> str:
    plan = {
        "topic_title": contract.get("topic"),
        "research_question": contract.get("research_question"),
        "contribution": contract.get("contribution"),
        "synthesis": contract.get("synthesis"),
        "data_source_query": (contract.get("data_source") or {}).get("name"),
        "level": contract.get("level"),
    }
    return (
        "You are a methodology gatekeeper for an automated abstract-level meta-analysis "
        "pipeline. The pipeline pools effect sizes extracted from OpenAlex ABSTRACTS only "
        "(no full text), using DerSimonian-Laird random effects. It CANNOT do Bayesian/"
        "latent-class models, network meta-analysis, meta-regression, RoB2/GRADE, or "
        "full-text screening. Raw MD is reported but never pooled (only SMD and ratio "
        "measures pool).\n\n"
        f"THE GRILL'S PLAN:\n{json.dumps(plan, ensure_ascii=False, indent=1)}\n\n"
        f"FEASIBILITY PROBE (what would ACTUALLY pool, ground truth):\n"
        f"{json.dumps(probe, ensure_ascii=False, indent=1)}\n\n"
        "Decide and CALIBRATE. Return ONLY a fenced ```json block with exactly:\n"
        "{\n"
        '  "viable": true|false,            // can this produce a defensible paper?\n'
        '  "reason": "...",                 // one paragraph; if not viable, why + what to change\n'
        '  "gap_assessment": "...",         // is the research gap real or SATURATED? cite the saturation signal\n'
        '  "calibrated": {                  // corrections to apply (omit a field to leave it)\n'
        '     "data_source_name": "...",    // OpenAlex query = CORE topic only, never a moderator term\n'
        '     "topic_title": "...",         // align to what the data supports (drop unfulfillable claims)\n'
        '     "contribution": "...",        // same; do NOT claim moderation/stratified if k < 10\n'
        '     "picos": { ... }              // tighten exclude_terms/require_any/require_all/moderators if helpful\n'
        "  }\n"
        "}\n"
        f"Rules: if max_poolable_k < {MODERATION_MIN_K}, the title/contribution MUST NOT claim "
        "moderation, subgroup, or stratified estimates — rewrite to a straightforward pooled-effect "
        f"question. If max_poolable_k < {MIN_POOLABLE_K}, set viable=false. If the gap is SATURATED "
        f"(already well-covered by existing meta-analyses) AND max_poolable_k < {QUALITY_K}, set "
        "viable=false — a thin re-do of a saturated question is not worth a paper; say so and suggest "
        "a sharper, less-covered angle. Keep the calibrated query in English, core topic only."
    )


def _codex_available() -> bool:
    return shutil.which(CODEX_BIN) is not None and (CODEX_AUTH_DIR / "auth.json").is_file()


def _run_codex(prompt: str, run_dir: Path, timeout_s: int = 420) -> dict[str, Any] | None:
    """Single codex calibration call (read-only). Returns the parsed JSON or None."""
    log_dir = run_dir / "_phase_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "phase0_codex.prompt.txt").write_text(prompt, encoding="utf-8")
    try:
        proc = subprocess.run(
            [CODEX_BIN, "exec", "--skip-git-repo-check", "--sandbox", "read-only", prompt],
            cwd=run_dir, stdin=subprocess.DEVNULL, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_s)
    except (subprocess.TimeoutExpired, OSError) as exc:
        (log_dir / "phase0_codex.stderr.txt").write_text(f"phase0 codex failed: {exc}", encoding="utf-8")
        return None
    out = proc.stdout or ""
    (log_dir / "phase0_codex.stdout.txt").write_text(out, encoding="utf-8")
    try:
        import compile_review
        block = compile_review._last_json_block(out)
    except Exception:  # noqa: BLE001
        block = None
    return block if isinstance(block, dict) else None


def _apply(contract: dict[str, Any], calibrated: dict[str, Any]) -> dict[str, Any]:
    """Merge codex's calibrated fields into a NEW contract (immutable; bounded to
    the safe, plan-level fields — never level/tier/identity)."""
    c = json.loads(json.dumps(contract))  # deep copy
    # NOTE: codex's data_source_name (query) is intentionally NOT applied. The query
    # is fixed deterministically (_clean_query) so the probe's cached corpus is reused
    # by the real run; letting codex rewrite the query would invalidate the cache and
    # force a second large collect (the source then throttles -> inconsistent counts).
    for fld in ("topic_title", "contribution"):
        key = "topic" if fld == "topic_title" else fld
        if isinstance(calibrated.get(fld), str) and calibrated[fld].strip():
            c[key] = calibrated[fld].strip()
    if isinstance(calibrated.get("picos"), dict):
        c.setdefault("synthesis", {}).setdefault("picos", {}).update(calibrated["picos"])
    return c


def _clean_query(query: str, moderators: list[dict[str, Any]]) -> str:
    """Strip moderator phrases from the OpenAlex query. A moderator (e.g.
    'delivery_mode' -> 'delivery mode') in the SEARCH narrows the corpus to records
    that mention it, starving the pool; the moderator should only TAG, not filter."""
    import re
    q = query
    for m in moderators or []:
        name = str(m.get("name") or "").replace("_", " ").strip()
        if name and name.lower() in q.lower():
            q = re.sub(re.escape(name), " ", q, flags=re.I)
    return " ".join(q.split())


def _enforce(contract: dict[str, Any], floor: dict[str, Any]) -> dict[str, Any]:
    """Deterministic enforcement applied on EVERY viable plan, independent of codex
    (codex gives judgement but is non-deterministic about edits). Fixes the two
    failure modes that actually broke runs: a moderator term in the query, and an
    unsupported moderation claim in the framing."""
    c = json.loads(json.dumps(contract))
    syn = c.setdefault("synthesis", {})
    mods = (syn.get("picos") or {}).get("moderators") or []
    ds = c.setdefault("data_source", {})
    cleaned = _clean_query(str(ds.get("name") or ""), mods)
    if cleaned and cleaned != ds.get("name"):
        ds["name"] = cleaned
    if floor.get("downgrade_moderation"):
        # The writer + metrics block read this to keep moderation/subgroup OUT of the
        # title/abstract/contribution (k too small to support it).
        syn["suppress_moderation_claim"] = True
    return c


def run_phase0(run_dir: Path, contract: dict[str, Any], query: str) -> dict[str, Any]:
    """Calibrate the plan before the pipeline runs. Returns
    {viable, contract (calibrated), reason, gap_assessment, probe, source}.
    Only the meta-analysis lane is calibrated here; other lanes pass through."""
    run_dir = Path(run_dir)
    syn = contract.get("synthesis") if isinstance(contract.get("synthesis"), dict) else {}
    syn_type = str(syn.get("type") or "intervention").lower()
    picos = syn.get("picos") if isinstance(syn.get("picos"), dict) else {}

    # Clean the query up-front (strip moderator phrases) and probe on THAT, so the
    # probe's cached corpus is exactly what the real run will reuse (one collect).
    clean_query = _clean_query(query, picos.get("moderators") or [])
    if clean_query and contract.get("data_source"):
        contract["data_source"]["name"] = clean_query
    probe = feasibility_probe(run_dir, clean_query, syn_type, picos)
    floor = deterministic_floor(contract, probe)
    result: dict[str, Any] = {"probe": probe, "contract": contract, "gap_assessment": "",
                              "source": "floor", "downgrade_moderation": floor.get("downgrade_moderation", False)}

    if not floor["viable"]:                       # hard infeasible — codex can't rescue
        result.update(viable=False, reason=floor["reason"])
        _write(run_dir, result)
        return result

    base = contract
    reason = "deterministic floor passed (k=%s)" % floor.get("k")
    if _codex_available():
        block = _run_codex(_build_prompt(contract, probe), run_dir)
        if block is not None and isinstance(block.get("viable"), bool):
            result["source"] = "codex"
            result["gap_assessment"] = str(block.get("gap_assessment") or "")
            if not block["viable"]:               # codex judges it not worth doing
                result.update(viable=False, reason=str(block.get("reason") or "codex: not viable"))
                _write(run_dir, result)
                return result
            # Deterministic backstop: a SATURATED gap + a thin pool is not worth a
            # paper even if codex waffled to viable=true. Don't burn a run on it.
            gap = result["gap_assessment"].lower()
            if ("saturat" in gap or "well-covered" in gap or "already" in gap) \
                    and int(probe.get("max_poolable_k") or 0) < QUALITY_K:
                result.update(viable=False, reason=(
                    "saturated question + only %s poolable studies at the abstract level: not worth "
                    "a thin re-do. Pick a sharper, less-covered angle or a less data-sparse topic. "
                    % probe.get("max_poolable_k")) + str(block.get("reason") or ""))
                _write(run_dir, result)
                return result
            calib = block.get("calibrated") if isinstance(block.get("calibrated"), dict) else {}
            base = _apply(contract, calib)        # codex's judgement edits (best-effort)
            reason = str(block.get("reason") or reason)

    # Deterministic enforcement on top of codex (the critical fixes never depend on it)
    result.update(viable=True, reason=reason, contract=_enforce(base, floor))
    _write(run_dir, result)
    return result


def _write(run_dir: Path, result: dict[str, Any]) -> None:
    slim = {k: v for k, v in result.items() if k != "contract"}
    (run_dir / "phase0_calibration.json").write_text(
        json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")
