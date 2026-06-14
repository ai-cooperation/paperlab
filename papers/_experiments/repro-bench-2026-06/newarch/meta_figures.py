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
METHOD = "fig_method_overview"

# Journal-ish palette + editable SVG text (svg.fonttype=none so labels stay text)
plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none"})
_INK = "#1a202c"
_BLUE, _BLUE_FILL = "#2b6cb0", "#eaf1fb"
_RED, _RED_FILL = "#c53030", "#fdecec"
_GREEN, _GREEN_FILL = "#2f855a", "#e9f6ef"
_GRAY = "#4a5568"
_SCALE_SHORT = {"log_ratio": "Ratio", "smd": "SMD", "md": "MD",
                "proportion": "Proportion", "correlation": "r"}
_SRC_NAME = {"europepmc": "Europe PMC", "openalex": "OpenAlex", "crossref": "CrossRef"}


def _box(ax: plt.Axes, x: float, y: float, w: float, h: float, text: str,
         ec: str, fc: str, fs: float = 9.0) -> None:
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                                boxstyle="round,pad=0.02,rounding_size=0.10",
                                fc=fc, ec=ec, lw=1.4))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, color=_INK, linespacing=1.45)


def _arrow(ax: plt.Axes, x1: float, y1: float, x2: float, y2: float, color: str = _GRAY) -> None:
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=1.6, shrinkA=0, shrinkB=0))


def _source_name(meta: dict[str, Any]) -> str:
    by = ((meta.get("prisma") or {}).get("by_source")) or {}
    names = [_SRC_NAME.get(s, s) for s, n in by.items() if n]
    return " + ".join(names) if names else "database"


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
    def _label(e: dict[str, Any]) -> str:
        # word-boundary truncation (no mid-word cut) + year, for a clean axis tick
        title = " ".join(str(e.get("title") or "").split())
        if len(title) > 46:
            cut = title[:46].rsplit(" ", 1)[0]
            title = (cut or title[:46]) + "…"
        return f"{title} ({e.get('year') or 'n.d.'})"
    labels = [_label(e) for e in rows]
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
    """PRISMA 2020-style study-selection flow with Identification / Screening /
    Included phase bands and a broken-out exclusion box — drawn from real counts."""
    p = meta.get("prisma") or {}
    if not p.get("identified"):
        return []
    ident = p.get("identified") or 0
    scanned = p.get("scanned") or 0
    excl = p.get("excluded_picos", 0) or 0
    studies = p.get("studies_with_effects")
    effects = p.get("effects_extracted", "?")
    pooled = meta.get("pooled") or {}
    pooled_txt = " · ".join(f"{_SCALE_SHORT.get(s, s)} k={pp.get('k')}"
                            for s, pp in pooled.items()) or "—"

    fig, ax = plt.subplots(figsize=(6.8, 7.2))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 12)
    ax.axis("off")
    mx, ex = 5.6, 10.3                          # main column / exclusion column
    ys = [10.4, 7.8, 5.2, 2.6]                  # 4 main rows
    _box(ax, mx, ys[0], 6.6, 1.5, f"Records identified via {_source_name(meta)}\n(n = {ident:,})", _BLUE, _BLUE_FILL)
    _box(ax, mx, ys[1], 6.6, 1.5, f"Abstracts screened against PICOS\n(n = {scanned:,})", _BLUE, _BLUE_FILL)
    _box(ax, ex, ys[1], 3.0, 1.5, f"Excluded by PICOS\n(n = {excl:,})", _RED, _RED_FILL, fs=8)
    _box(ax, mx, ys[2], 6.6, 1.5, f"Studies with extractable\neffect sizes (n = {studies})", _BLUE, _BLUE_FILL)
    _box(ax, mx, ys[3], 6.6, 1.5, f"Included in pooling ({effects} effects)\n{pooled_txt}", _GREEN, _GREEN_FILL)
    _arrow(ax, mx, ys[0] - 0.75, mx, ys[1] + 0.75)
    _arrow(ax, mx, ys[1] - 0.75, mx, ys[2] + 0.75)
    _arrow(ax, mx, ys[2] - 0.75, mx, ys[3] + 0.75)
    _arrow(ax, mx + 3.3, ys[1], ex - 1.5, ys[1], _RED)
    for label, ytop, ybot in [("Identification", ys[0], ys[0]), ("Screening", ys[1], ys[2]),
                              ("Included", ys[3], ys[3])]:
        yc = (ytop + ybot) / 2
        ax.add_patch(FancyBboxPatch((0.3, ybot - 0.95), 1.0, (ytop - ybot) + 1.9,
                                    boxstyle="round,pad=0.02", fc="#f7fafc", ec="#cbd5e0", lw=1.0))
        ax.text(0.8, yc, label, ha="center", va="center", rotation=90,
                fontsize=9.5, color=_GRAY, fontweight="bold")
    ax.set_title("Study selection (PRISMA 2020)", fontsize=11.5, fontweight="bold", color=_INK, pad=12)
    return _save(fig, run_dir, PRISMA)


def method_overview(run_dir: Path, meta: dict[str, Any]) -> list[str]:
    """Horizontal pipeline overview — search -> PICOS screen -> extract -> pool ->
    sensitivity, with the real numbers. Deterministic (replaces the writer's TikZ)."""
    p = meta.get("prisma") or {}
    if not p.get("identified"):
        return []
    pooled = meta.get("pooled") or {}
    sens = meta.get("sensitivity") or {}
    pooled_txt = "\n".join(f"{_SCALE_SHORT.get(s, s)} k={pp.get('k')}"
                           for s, pp in pooled.items()) or "—"
    sens_txt = "\n".join(sorted(k.replace("subgroup_by_", "subgroup: ").replace("_", " ")
                                for k in sens)) or "—"
    stages = [
        ("Search", f"{_source_name(meta)}\n{p.get('identified', 0):,} records", _BLUE, _BLUE_FILL),
        ("PICOS screen", f"{p.get('excluded_picos', 0):,} excluded\n{p.get('studies_with_effects', '?')} studies kept", _RED, _RED_FILL),
        ("Effect extraction", f"{p.get('effects_extracted', '?')} effects\nverbatim evidence", _BLUE, _BLUE_FILL),
        ("DerSimonian–Laird\nrandom-effects pool", pooled_txt, _GREEN, _GREEN_FILL),
        ("Sensitivity", sens_txt, _GRAY, "#f1f5f9"),
    ]
    n = len(stages)
    fig, ax = plt.subplots(figsize=(2.05 * n, 2.9))
    ax.set_xlim(0, n * 2)
    ax.set_ylim(0, 4)
    ax.axis("off")
    for i, (title, body, ec, fc) in enumerate(stages):
        cx = i * 2 + 1
        ax.add_patch(FancyBboxPatch((cx - 0.92, 1.0), 1.84, 2.0,
                                    boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=ec, lw=1.5))
        ax.text(cx, 2.62, title, ha="center", va="center", fontsize=8.6, fontweight="bold", color=_INK, linespacing=1.3)
        ax.text(cx, 1.62, body, ha="center", va="center", fontsize=7.6, color=_GRAY, linespacing=1.4)
        if i < n - 1:
            _arrow(ax, cx + 0.92, 2.0, cx + 1.08, 2.0)
    ax.set_title("Abstract-level meta-analysis pipeline", fontsize=11, fontweight="bold", color=_INK, pad=8)
    return _save(fig, run_dir, METHOD)


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
    try:
        mo = method_overview(run_dir, meta)
        if mo:
            out[METHOD] = mo
    except Exception:  # noqa: BLE001
        pass
    return out


if __name__ == "__main__":
    import sys
    print(generate(Path(sys.argv[1] if len(sys.argv) > 1 else ".")))
