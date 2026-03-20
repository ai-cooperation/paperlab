"""
gen_fig2_cumulative_returns.py
Figure 2: Cumulative Returns — Out-of-Sample Period (2023-01 to 2024-12)
Simulated Data — publication-quality figure for FinMM-LLM paper.
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

matplotlib.rcParams['font.family'] = 'DejaVu Sans'
matplotlib.rcParams['axes.spines.top'] = False
matplotlib.rcParams['axes.spines.right'] = False

# ── Reproducibility ─────────────────────────────────────────────────────────
np.random.seed(42)

# ── Trading calendar ─────────────────────────────────────────────────────────
dates = pd.bdate_range(start='2023-01-02', end='2024-12-31')
n = len(dates)  # ~522 trading days

# ── Simulate daily log-returns with drift ───────────────────────────────────
# Target final cumulative returns: MM ~45%, TS ~28%, Text ~18%, FF5 ~12%
# Over n days, annualised ≈ 252 days → match 2-year cumulative target.
annualised_mu = {
    'MM':   np.log(1.45) / 2,   # ~19% p.a.
    'TS':   np.log(1.28) / 2,   # ~12% p.a.
    'Text': np.log(1.18) / 2,   # ~ 8% p.a.
    'FF5':  np.log(1.12) / 2,   # ~ 6% p.a.
}
vol = {'MM': 0.12, 'TS': 0.10, 'Text': 0.09, 'FF5': 0.08}  # annual vol

def simulate_cum_returns(mu_annual, vol_annual, n_days, seed_offset=0):
    dt = 1 / 252
    daily_mu = mu_annual * dt
    daily_vol = vol_annual * np.sqrt(dt)
    rng = np.random.default_rng(42 + seed_offset)
    dr = rng.normal(daily_mu, daily_vol, n_days)
    cum = np.exp(np.cumsum(dr)) - 1        # cumulative return, starts at 0
    return np.concatenate([[0.0], cum])    # prepend t=0

cum = {
    'Multi-Modal (FinMM-LLM)': simulate_cum_returns(annualised_mu['MM'],   vol['MM'],   n, 0),
    'TS-Only Baseline':        simulate_cum_returns(annualised_mu['TS'],   vol['TS'],   n, 1),
    'Text-Only Baseline':      simulate_cum_returns(annualised_mu['Text'], vol['Text'], n, 2),
    'FF5 Benchmark':           simulate_cum_returns(annualised_mu['FF5'],  vol['FF5'],  n, 3),
}

# Prepend the start date so x-axis aligns with the 0-point
plot_dates = pd.DatetimeIndex([dates[0] - pd.tseries.offsets.BDay(1)]).append(dates)

# ── Earnings season shading: Jan, Apr, Jul, Oct ──────────────────────────────
earnings_months = {1, 4, 7, 10}

def earnings_intervals(date_index):
    """Return (start, end) pairs for contiguous earnings-season runs."""
    in_season = [d.month in earnings_months for d in date_index]
    intervals = []
    start = None
    for i, flag in enumerate(in_season):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            intervals.append((start, i - 1))
            start = None
    if start is not None:
        intervals.append((start, len(in_season) - 1))
    return intervals

intervals = earnings_intervals(plot_dates)

# ── Plot ─────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 5))

# Earnings season shading
for (s, e) in intervals:
    ax.axvspan(plot_dates[s], plot_dates[e],
               color='#cccccc', alpha=0.30, linewidth=0, zorder=0)

# Return curves
colors = {
    'Multi-Modal (FinMM-LLM)': '#d62728',   # red
    'TS-Only Baseline':        '#1f77b4',   # blue
    'Text-Only Baseline':      '#2ca02c',   # green
    'FF5 Benchmark':           '#7f7f7f',   # gray
}
styles = {
    'Multi-Modal (FinMM-LLM)': '-',
    'TS-Only Baseline':        '-',
    'Text-Only Baseline':      '-',
    'FF5 Benchmark':           '--',
}
lws = {
    'Multi-Modal (FinMM-LLM)': 2.2,
    'TS-Only Baseline':        1.8,
    'Text-Only Baseline':      1.8,
    'FF5 Benchmark':           1.6,
}

for label, series in cum.items():
    ax.plot(plot_dates, series * 100,
            color=colors[label],
            linestyle=styles[label],
            linewidth=lws[label],
            label=label)

# Earnings season legend patch
earnings_patch = mpatches.Patch(color='#cccccc', alpha=0.60,
                                label='Earnings Season (Jan/Apr/Jul/Oct)')

# ── Formatting ───────────────────────────────────────────────────────────────
ax.set_xlabel('Date', fontsize=13)
ax.set_ylabel('Cumulative Return (%)', fontsize=13)
ax.set_title('Out-of-Sample Cumulative Returns (2023–2024)', fontsize=14, fontweight='bold')
ax.tick_params(axis='both', labelsize=11)
ax.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter('%d%%'))

handles, labels = ax.get_legend_handles_labels()
handles.append(earnings_patch)
labels.append('Earnings Season (Jan/Apr/Jul/Oct)')
ax.legend(handles, labels, fontsize=11, loc='upper left', frameon=False)

ax.set_xlim(plot_dates[0], plot_dates[-1])

# Simulated data annotation (bottom-right, inside axes)
ax.annotate(
    '* Simulated Data',
    xy=(1.0, 0.01), xycoords='axes fraction',
    ha='right', va='bottom', fontsize=9, color='#666666',
    style='italic'
)

plt.tight_layout()
plt.savefig('fig2_cumulative_returns.png', dpi=150, bbox_inches='tight')
plt.savefig('fig2_cumulative_returns.svg', format='svg', bbox_inches='tight')
print("Saved: fig2_cumulative_returns.png")
print("Saved: fig2_cumulative_returns.svg")
plt.close()
