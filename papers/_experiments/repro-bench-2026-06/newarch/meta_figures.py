#!/usr/bin/env python3
"""Deterministic meta-analysis figures from real_results — forest plot + PRISMA
flow. A meta-analysis without a forest plot does not pass review; like the
GENERATED tables these are machine-drawn from the pooled numbers (never the
model's imagination), so the figure cannot disagree with the analysis.

Headless matplotlib (Agg). Writes png + svg into <run_dir>/figures/.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon  # noqa: E402

FOREST = "fig_forest_plot"
PRISMA = "fig_prisma_flow"


def _primary_scale(meta: dict[str, Any]) -> str | None:
    pooled = meta.get("pooled") or {}
    if not pooled:
        return None
    return max(pooled, key=lambda s: (pooled[s] or {}).get("k", 0))


def _save(fig: plt.Figure, run_dir: Path, name: str) -> list[str]:
    figdir = run_dir / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    out: list[str] = []
    for ext in ("png", "svg"):
        p = figdir / f"{name}.{ext}"
        fig.savefig(p, dpi=150, bbox_inches="tight")
        out.append(p.name)
    plt.close(fig)
    return out


def forest_plot(run_dir: Path, meta: dict[str, Any]) -> list[str]:
    """Forest plot of the primary pool: per-study effect + 95% CI, pooled diamond.
    Ratio scales use a log x-axis with a null line at 1; others a linear axis."""
    scale = _primary_scale(meta)
    pooled = (meta.get("pooled") or {}).get(scale) if scale else None
    if not pooled:
        return []
    log_scale = scale == "log_ratio"
    null = 1.0 if log_scale else 0.0
    # studies with a usable CI on this scale, de-duplicated by study
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for e in meta.get("effects") or []:
        if e.get("scale") != scale or e.get("ci_low") is None or e.get("ci_high") is None:
            continue
        sid = str(e.get("doi") or e.get("title"))
        if sid in seen:
            continue
        seen.add(sid)
        rows.append(e)
    if len(rows) < 2:
        return []
    rows = rows[:25]
    n = len(rows)
    fig, ax = plt.subplots(figsize=(8.4, 0.42 * n + 1.8))
    ys = list(range(n, 0, -1))
    for y, e in zip(ys, rows):
        lo, hi, pt = e["ci_low"], e["ci_high"], e["effect"]
        ax.plot([lo, hi], [y, y], color="#444", lw=1.3, zorder=2)
        ax.plot([pt], [y], "s", color="#2b6cb0", ms=6, zorder=3)
    labels = [f"{(e.get('title') or '')[:48]} ({e.get('year') or 'n.d.'})" for e in rows]
    # pooled diamond
    pe, plo, phi = pooled["pooled_effect"], pooled["ci_low"], pooled["ci_high"]
    ax.add_patch(Polygon([[plo, 0], [pe, 0.32], [phi, 0], [pe, -0.32]],
                         closed=True, color="#c53030", zorder=4))
    ax.axvline(null, color="#999", lw=1, ls="--", zorder=1)
    ax.set_yticks(ys + [0])
    ax.set_yticklabels(labels + [f"Pooled (k={pooled['k']}, I²={pooled['i2_percent']}%)"],
                       fontsize=8)
    ax.set_ylim(-0.8, n + 0.8)
    if log_scale:
        ax.set_xscale("log")
        ax.set_xlabel("Effect (ratio, log scale; 95% CI)")
    else:
        ax.set_xlabel("Effect size (95% CI)")
    ax.set_title(f"Forest plot — {meta.get('synthesis_type', 'meta-analysis')} "
                 f"({scale}); pooled {pe} [{plo}, {phi}]", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    return _save(fig, run_dir, FOREST)


def prisma_flow(run_dir: Path, meta: dict[str, Any]) -> list[str]:
    """PRISMA-style flow: identified -> screened -> eligible -> pooled."""
    p = meta.get("prisma") or {}
    if not p.get("identified"):
        return []
    steps = [
        ("Records identified\n(OpenAlex)", p.get("identified")),
        ("Abstracts screened", p.get("scanned")),
        (f"Excluded by PICOS\n(n={p.get('excluded_picos', 0)})", None),
        ("Studies with\nextractable effects", p.get("studies_with_effects")),
        (f"Effects extracted\n({p.get('effects_extracted', '?')})", None),
    ]
    fig, ax = plt.subplots(figsize=(4.6, 6.4))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, len(steps) * 2)
    y = len(steps) * 2 - 1.2
    cx = 5
    for i, (label, count) in enumerate(steps):
        excl = "Excluded" in label
        x = 7.4 if excl else cx
        w = 3.4 if excl else 5.2
        txt = label if count is None else f"{label}\nn = {count:,}"
        ax.add_patch(FancyBboxPatch((x - w / 2, y - 0.7), w, 1.4,
                                    boxstyle="round,pad=0.05",
                                    fc="#fdeeee" if excl else "#eef3fb",
                                    ec="#c53030" if excl else "#2b6cb0", lw=1.2))
        ax.text(x, y, txt, ha="center", va="center", fontsize=8.5)
        if i > 0 and not excl:
            ax.annotate("", xy=(cx, y + 0.7), xytext=(cx, y + 1.3),
                        arrowprops=dict(arrowstyle="-|>", color="#555"))
        if excl:
            ax.annotate("", xy=(x - w / 2, y), xytext=(cx, y),
                        arrowprops=dict(arrowstyle="-|>", color="#c53030"))
        y -= 2
    ax.axis("off")
    ax.set_title("Study selection (PRISMA-style)", fontsize=10)
    return _save(fig, run_dir, PRISMA)


def generate(run_dir: Path) -> dict[str, list[str]]:
    """Generate both figures from real_results.json. Returns {name: [files]}."""
    run_dir = Path(run_dir)
    rr_path = run_dir / "real_experiments" / "real_results.json"
    try:
        rr = json.loads(rr_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    meta = rr.get("meta")
    if not isinstance(meta, dict):
        return {}
    out: dict[str, list[str]] = {}
    try:
        f = forest_plot(run_dir, meta)
        if f:
            out[FOREST] = f
    except Exception:  # noqa: BLE001 - a figure failure must not kill the run
        pass
    try:
        pr = prisma_flow(run_dir, meta)
        if pr:
            out[PRISMA] = pr
    except Exception:  # noqa: BLE001
        pass
    return out


if __name__ == "__main__":
    import sys
    print(generate(Path(sys.argv[1] if len(sys.argv) > 1 else ".")))
