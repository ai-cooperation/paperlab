#!/usr/bin/env python3
"""Deterministic figures for the GENERAL dataset-analysis lane — machine-drawn from
real_results.json, never the model's imagination (so the figure cannot disagree with
the analysis). The sibling of meta_figures.py for the dataset lane.

GENERALITY (the whole point): this reads only the GENERIC result schema every dataset
run emits — `models[]` (estimate/ci/p), `spline_results.*` (predicted values), and
`sample_flow{}` (flow counts). It contains ZERO dataset-specific strings: axis labels
come from each model's own `outcome`/`exposure` fields (agent-produced), key detection
is by PATTERN (`*_value` = x, `predicted_*` = y). Litmus: a new dataset emits the same
schema with different values -> the SAME renderer draws its figures with no code change.

Headless matplotlib (Agg). Writes png + svg into <run_dir>/figures/.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

FOREST = "fig_model_forest"
DOSE = "fig_dose_response"
FLOW = "fig_sample_flow"

# Journal-ish palette + editable SVG text (svg.fonttype=none so labels stay text)
plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none"})
_INK = "#1a202c"
_BLUE, _BLUE_FILL = "#2b6cb0", "#eaf1fb"
_RED, _RED_FILL = "#c53030", "#fdecec"
_GREEN, _GREEN_FILL = "#2f855a", "#e9f6ef"
_GRAY = "#4a5568"


def _clean(s: Any) -> str:
    """Turn a generic field name into a human axis label (no domain knowledge)."""
    return re.sub(r"\s+", " ", str(s or "").replace("_", " ")).strip()


def _num(x: Any) -> float | None:
    try:
        f = float(x)
        return f if f == f else None          # drop NaN
    except (TypeError, ValueError):
        return None


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


def forest_plot(run_dir: Path, rr: dict[str, Any]) -> list[str]:
    """Coefficient forest: each model's point estimate + 95% CI on a common axis,
    null line at 0. A panel of model specifications (not a meta-analysis pool), so no
    pooled diamond. Drawn from whatever `models[]` the analysis produced."""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for m in rr.get("models") or []:
        lo, hi = _num(m.get("ci_low")), _num(m.get("ci_high"))
        pt = _num(m.get("estimate"))
        if pt is None:
            pt = _num(m.get("beta"))
        if lo is None or hi is None or pt is None:
            continue
        sid = str(m.get("id") or m.get("family"))
        if sid in seen:
            continue
        seen.add(sid)
        rows.append({"label": _clean(m.get("id") or m.get("family")), "pt": pt, "lo": lo, "hi": hi,
                     "p": _num(m.get("p_value"))})
    if len(rows) < 2:
        return []
    rows = rows[:25]
    n = len(rows)
    fig, ax = plt.subplots(figsize=(8.6, 0.46 * n + 1.6))
    ys = list(range(n, 0, -1))
    for y, r in zip(ys, rows):
        ax.plot([r["lo"], r["hi"]], [y, y], color="#444", lw=1.4, zorder=2)
        crosses = r["lo"] <= 0 <= r["hi"]
        ax.plot([r["pt"]], [y], "s", color=_GRAY if crosses else _BLUE, ms=7, zorder=3)
    ax.axvline(0.0, color="#999", lw=1, ls="--", zorder=1)
    ax.set_yticks(ys)
    ax.set_yticklabels([r["label"] for r in rows], fontsize=9)
    ax.set_ylim(0.3, n + 0.7)
    m0 = (rr.get("models") or [{}])[0]
    out_lbl, exp_lbl = _clean(m0.get("outcome")), _clean(m0.get("exposure"))
    ax.set_xlabel(f"Coefficient on {exp_lbl} (95% CI)" if exp_lbl else "Coefficient (95% CI)",
                  fontsize=11)
    ttl = f"Model estimates — {out_lbl} ~ {exp_lbl}" if out_lbl and exp_lbl else "Model estimates (95% CI)"
    ax.set_title(ttl, fontsize=12, color=_INK)
    ax.tick_params(axis="x", labelsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    return _save(fig, run_dir, FOREST)


def _find_spline(rr: dict[str, Any]) -> dict[str, Any] | None:
    """The first spline_results entry carrying a predicted-values curve (model id agnostic)."""
    for v in (rr.get("spline_results") or {}).values():
        if isinstance(v, dict) and v.get("predicted_values_at_predefined_percentiles"):
            return v
    return None


def dose_response(run_dir: Path, rr: dict[str, Any]) -> list[str]:
    """Dose-response curve from the spline model's predicted values + 95% band. The x
    (exposure) and y (predicted outcome) columns are detected by PATTERN, so the renderer
    never names the variables: `*_value` (not predicted) = x, `predicted_*` = y."""
    sp = _find_spline(rr)
    if not sp:
        return []
    pv = sp.get("predicted_values_at_predefined_percentiles") or []
    if len(pv) < 3:
        return []
    keys = list(pv[0].keys())
    x_key = next((k for k in keys if k.endswith("_value") and not k.startswith("predicted")), None)
    y_key = next((k for k in keys if k.startswith("predicted")), None)
    if not x_key or not y_key:
        return []
    pts = []
    for row in pv:
        x, y = _num(row.get(x_key)), _num(row.get(y_key))
        if x is None or y is None:
            continue
        pts.append((x, y, _num(row.get("ci_low")), _num(row.get("ci_high"))))
    pts.sort(key=lambda t: t[0])
    if len(pts) < 3:
        return []
    xs = [p[0] for p in pts]
    ysv = [p[1] for p in pts]
    fig, ax = plt.subplots(figsize=(7.8, 5.0))
    if all(p[2] is not None and p[3] is not None for p in pts):
        ax.fill_between(xs, [p[2] for p in pts], [p[3] for p in pts],
                        color=_BLUE_FILL, alpha=0.9, zorder=1, label="95% CI")
    ax.plot(xs, ysv, "-o", color=_BLUE, lw=2.0, ms=6, zorder=2)
    m0 = (rr.get("models") or [{}])[0]
    ax.set_xlabel(_clean((rr.get("models") or [{}])[0].get("exposure")) or _clean(x_key), fontsize=11)
    ax.set_ylabel(_clean(m0.get("outcome")) or _clean(y_key).replace("predicted ", ""), fontsize=11)
    ax.set_title("Estimated dose-response (natural cubic spline, 95% CI)", fontsize=12, color=_INK)
    ax.tick_params(labelsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    return _save(fig, run_dir, DOSE)


def _box(ax: plt.Axes, x: float, y: float, w: float, h: float, text: str,
         ec: str, fc: str, fs: float = 9.5) -> None:
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                                boxstyle="round,pad=0.02,rounding_size=0.10", fc=fc, ec=ec, lw=1.4))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, color=_INK, linespacing=1.4)


def sample_flow(run_dir: Path, rr: dict[str, Any]) -> list[str]:
    """A flow diagram (identified -> merged -> exclusions -> analytic) from sample_flow
    counts. Generic: it enumerates whatever `excluded_*` keys the analysis recorded."""
    sf = rr.get("sample_flow") or {}
    if not sf:
        return []
    by_file = sf.get("identified_rows_by_file") or {}
    identified = sum(_num(v) or 0 for v in by_file.values()) if by_file else _num(sf.get("merged_rows"))
    merged = _num(sf.get("merged_rows"))
    analytic = _num(sf.get("analytic_rows"))
    if analytic is None:
        return []
    excl = [(_clean(k).replace("excluded ", ""), int(_num(v) or 0))
            for k, v in sf.items() if k.startswith("excluded_") and (_num(v) or 0) > 0]
    unit_label = _clean(sf.get("unit_label")) or "units"
    units = sf.get("analytic_units")
    if units is None:
        units = sf.get("analytic_countries")
    tmin = sf.get("time_min")
    if tmin is None:
        tmin = sf.get("analytic_year_min")
    tmax = sf.get("time_max")
    if tmax is None:
        tmax = sf.get("analytic_year_max")
    span = (f"\n{int(units)} {unit_label}, {tmin}–{tmax}" if units and tmin is not None and tmax is not None else "")

    fig, ax = plt.subplots(figsize=(6.8, 6.4))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 12)
    ax.axis("off")
    mx, ex = 5.2, 10.0
    ys = [10.6, 7.8, 5.0, 2.2]
    _box(ax, mx, ys[0], 7.0, 1.5, f"Identified source rows\n(n = {int(identified or 0):,})", _BLUE, _BLUE_FILL)
    _box(ax, mx, ys[1], 7.0, 1.5, f"Merged panel\n(n = {int(merged or 0):,})", _BLUE, _BLUE_FILL)
    if excl:
        body = "\n".join(f"{lbl} (n = {v:,})" for lbl, v in excl[:5])
        _box(ax, ex, ys[1], 3.4, 1.7, f"Excluded\n{body}", _RED, _RED_FILL, fs=7.6)
        _arrow_h(ax, mx + 3.5, ys[1], ex - 1.7, ys[1])
    _box(ax, mx, ys[2], 7.0, 1.5, f"Eligible after exclusions\n(n = {int(analytic or 0):,})", _BLUE, _BLUE_FILL)
    _box(ax, mx, ys[3], 7.0, 1.6, f"Analytic sample\n(n = {int(analytic or 0):,}){span}", _GREEN, _GREEN_FILL)
    for a, b in [(0, 1), (1, 2), (2, 3)]:
        _arrow_v(ax, mx, ys[a] - 0.75, mx, ys[b] + 0.8)
    ax.set_title("Sample construction flow", fontsize=12.5, fontweight="bold", color=_INK, pad=10)
    return _save(fig, run_dir, FLOW)


def _arrow_v(ax: plt.Axes, x1: float, y1: float, x2: float, y2: float) -> None:
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=_GRAY, lw=1.6, shrinkA=0, shrinkB=0))


def _arrow_h(ax: plt.Axes, x1: float, y1: float, x2: float, y2: float) -> None:
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=_RED, lw=1.6, shrinkA=0, shrinkB=0))


_BUILDERS = {FOREST: forest_plot, DOSE: dose_response, FLOW: sample_flow}


def generate(run_dir: Path) -> dict[str, list[str]]:
    """Generate every figure renderable from real_results.json. Returns {name: [files]}.
    Each builder is independent and fail-soft: a figure that cannot be drawn (its data is
    absent) is skipped, never crashing the run."""
    run_dir = Path(run_dir)
    rr_path = run_dir / "real_experiments" / "real_results.json"
    try:
        rr = json.loads(rr_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(rr, dict):
        return {}
    out: dict[str, list[str]] = {}
    for name, fn in _BUILDERS.items():
        try:
            files = fn(run_dir, rr)
            if files:
                out[name] = files
        except Exception:  # noqa: BLE001 - a figure failure must NOT kill the run
            pass
    return out


if __name__ == "__main__":
    import sys
    print(generate(Path(sys.argv[1] if len(sys.argv) > 1 else ".")))
