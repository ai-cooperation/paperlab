"""Litmus tests for the GENERAL dataset-lane figures + lane-aware injection.

The point of these tests is GENERALITY: a dataset the engine has never seen (here a fake
PM2.5-vs-mortality district panel — names that share NOTHING with the renewable-energy run)
must produce a forest, a dose-response, and a sample-flow figure with ZERO source change,
labelled from its OWN result fields. If a future change hard-codes a variable name, these
fail.
"""
from __future__ import annotations

import json
from pathlib import Path

import dataset_lane.figures as figures
import tables


# A dataset with names that DELIBERATELY overlap nothing in the renewable-energy run.
FAKE_RR = {
    "source": "PM2.5 exposure and mortality, district panel",
    "rows": 4700,
    "models": [
        {"id": "m1_twfe", "family": "twfe_linear", "outcome": "log_mortality_rate",
         "exposure": "pm25", "estimate": 0.0123, "beta": 0.0123,
         "ci_low": 0.004, "ci_high": 0.021, "p_value": 0.002},
        {"id": "m2_lag1", "family": "twfe_lag", "outcome": "log_mortality_rate",
         "exposure": "pm25", "estimate": 0.009, "ci_low": -0.001, "ci_high": 0.019,
         "p_value": 0.08},
        {"id": "m3_region", "family": "twfe_region", "outcome": "log_mortality_rate",
         "exposure": "pm25", "estimate": 0.015, "ci_low": 0.002, "ci_high": 0.028,
         "p_value": 0.03},
    ],
    "spline_results": {"m4_spline": {"predicted_values_at_predefined_percentiles": [
        {"percentile": 5, "pm25_value": 3.0, "predicted_log_mortality_rate": 6.1,
         "ci_low": 6.0, "ci_high": 6.2},
        {"percentile": 50, "pm25_value": 12.0, "predicted_log_mortality_rate": 6.4,
         "ci_low": 6.3, "ci_high": 6.5},
        {"percentile": 95, "pm25_value": 45.0, "predicted_log_mortality_rate": 7.0,
         "ci_low": 6.7, "ci_high": 7.3},
    ]}},
    "sample_flow": {"identified_rows_by_file": {"exposure.csv": 6000, "mortality.csv": 5200},
                    "merged_rows": 5000, "excluded_missing_pm25": 300,
                    "analytic_rows": 4700, "analytic_countries": 40,
                    "analytic_year_min": 2000, "analytic_year_max": 2020},
}


def _seed(run_dir: Path, rr: dict) -> None:
    (run_dir / "real_experiments").mkdir(parents=True, exist_ok=True)
    (run_dir / "real_experiments" / "real_results.json").write_text(
        json.dumps(rr), encoding="utf-8")


def test_figures_generate_on_unseen_dataset(tmp_path):
    """A never-seen dataset -> all three figures, zero source change (the litmus)."""
    _seed(tmp_path, FAKE_RR)
    out = figures.generate(tmp_path)
    assert figures.FOREST in out and figures.DOSE in out and figures.FLOW in out
    for name in (figures.FOREST, figures.DOSE, figures.FLOW):
        assert (tmp_path / "figures" / f"{name}.png").is_file()
        assert (tmp_path / "figures" / f"{name}.svg").is_file()


def test_dose_response_detects_xy_by_pattern_not_name(tmp_path):
    """x/y columns are found by PATTERN (*_value / predicted_*), so the renderer never
    needs to know the variable is called pm25 — a different dataset just works."""
    _seed(tmp_path, FAKE_RR)
    out = figures.generate(tmp_path)
    svg = (tmp_path / "figures" / f"{figures.DOSE}.svg").read_text(encoding="utf-8")
    # axis labels come from the artifact's own fields (svg keeps text: svg.fonttype=none)
    assert "pm25" in svg and "mortality" in svg


def test_no_spline_skips_dose_only(tmp_path):
    """A dataset with no spline still gets forest + flow; dose is simply skipped."""
    rr = {k: v for k, v in FAKE_RR.items() if k != "spline_results"}
    _seed(tmp_path, rr)
    out = figures.generate(tmp_path)
    assert figures.FOREST in out and figures.FLOW in out
    assert figures.DOSE not in out


def test_figspec_for_picks_lane():
    assert tables.figspec_for({"data_source": {"type": "dataset", "name": "pm25 panel"}}) \
        is tables.DATASET_FIGSPEC
    assert tables.figspec_for({"data_source": {"type": "meta-analysis"}}) is tables._FIGSPEC
    assert tables.figspec_for({"data_source": {"type": "dataset", "name": "HUPD patents"}}) \
        is tables._FIGSPEC                         # registered HUPD lane != general dataset lane


def test_available_fig_refs_only_existing(tmp_path):
    _seed(tmp_path, {k: v for k, v in FAKE_RR.items() if k != "spline_results"})
    figures.generate(tmp_path)
    refs = tables.available_fig_refs(tmp_path, tables.DATASET_FIGSPEC)
    assert "@fig-forest" in refs and "@fig-flow" in refs
    assert "@fig-dose" not in refs                 # no spline -> not referenced


def test_inject_figures_dataset_embeds_and_resolves(tmp_path):
    """The writer references @fig-forest/@fig-dose/@fig-flow; inject_figures embeds each
    real figure once as a labelled float and is idempotent."""
    _seed(tmp_path, FAKE_RR)
    figures.generate(tmp_path)
    (tmp_path / "paper_draft_v0.qmd").write_text(
        "# Introduction\n\nWe report @fig-forest, @fig-dose and @fig-flow here.\n\nMore text.\n",
        encoding="utf-8")
    n = tables.inject_figures(tmp_path, figspec=tables.DATASET_FIGSPEC)
    assert n == 3
    qmd = (tmp_path / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    for _, fname, _ in tables.DATASET_FIGSPEC:
        assert f"](figures/{fname})" in qmd        # each figure embedded as a float
    # idempotent: a second pass does not duplicate the embeds
    tables.inject_figures(tmp_path, figspec=tables.DATASET_FIGSPEC)
    qmd2 = (tmp_path / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    for _, fname, _ in tables.DATASET_FIGSPEC:
        assert qmd2.count(f"](figures/{fname})") == 1


def test_inject_strips_ref_to_missing_figure(tmp_path):
    """If the analysis produced no dose figure but the writer still wrote @fig-dose, the
    dangling ref is neutralized (no broken ?@fig- in the PDF)."""
    _seed(tmp_path, {k: v for k, v in FAKE_RR.items() if k != "spline_results"})
    figures.generate(tmp_path)
    (tmp_path / "paper_draft_v0.qmd").write_text(
        "# Introduction\n\nSee @fig-forest and @fig-dose.\n\nMore.\n", encoding="utf-8")
    tables.inject_figures(tmp_path, figspec=tables.DATASET_FIGSPEC)
    qmd = (tmp_path / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    assert "@fig-dose" not in qmd                  # neutralized
    assert "](figures/fig_model_forest.png)" in qmd
