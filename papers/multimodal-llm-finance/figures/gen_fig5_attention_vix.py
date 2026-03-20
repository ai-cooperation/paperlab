"""
gen_fig5_attention_vix.py
Figure 5: Cross-Attention Intensity vs VIX (Dual-Axis Time Series)
Simulated Data — publication-quality figure for FinMM-LLM paper.
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.rcParams['font.family'] = 'DejaVu Sans'
matplotlib.rcParams['axes.spines.top'] = False

np.random.seed(42)

# ── Date range ────────────────────────────────────────────────────────────────
dates = pd.bdate_range(start='2023-01-02', end='2024-12-31')
n = len(dates)

# ── Simulate VIX-like series ──────────────────────────────────────────────────
# VIX: mean-reverting around 20, with spikes
rng = np.random.default_rng(42)

def simulate_vix(n_days, rng):
    vix = np.empty(n_days)
    vix[0] = 21.0
    theta, kappa, sigma = 20.0, 0.08, 1.8
    for t in range(1, n_days):
        shock = rng.normal(0, sigma)
        vix[t] = vix[t-1] + kappa * (theta - vix[t-1]) + shock
        vix[t] = max(vix[t], 10.0)
    return vix

vix_raw = simulate_vix(n, rng)

# Inject key event spikes (aligned to approximate business day indices)
def date_to_idx(date_str):
    target = pd.Timestamp(date_str)
    diffs = np.abs((dates - target).days)
    return int(np.argmin(diffs))

svb_idx    = date_to_idx('2023-03-13')
oct23_idx  = date_to_idx('2023-10-20')
elect_idx  = date_to_idx('2024-11-05')

for idx, spike in [(svb_idx, 18), (oct23_idx, 14), (elect_idx, 10)]:
    width = 15
    for d in range(-5, width):
        if 0 <= idx + d < n:
            decay = np.exp(-abs(d) / 6)
            vix_raw[idx + d] += spike * decay

# Smooth VIX slightly
vix_smooth = pd.Series(vix_raw).rolling(window=5, min_periods=1, center=True).mean().values

# ── Simulate attention intensity correlated with VIX ─────────────────────────
# Target Pearson r ≈ 0.65
# Method: attention = a * vix_normalized + b * independent_noise
vix_norm = (vix_smooth - vix_smooth.mean()) / vix_smooth.std()
noise = rng.normal(0, 1, n)
noise_norm = (noise - noise.mean()) / noise.std()

r_target = 0.65
raw_attn = r_target * vix_norm + np.sqrt(1 - r_target**2) * noise_norm
# Scale to a plausible attention intensity range [0.2, 0.9]
attn_norm = (raw_attn - raw_attn.min()) / (raw_attn.max() - raw_attn.min())
attn_raw = 0.2 + 0.7 * attn_norm

# Verify raw correlation before smoothing (what the paper reports)
r_raw = np.corrcoef(attn_raw, vix_smooth)[0, 1]
print(f"Simulated Pearson r(attention_raw, VIX) = {r_raw:.3f}")

# Rolling 20-day average (for display)
attn_series = pd.Series(attn_raw).rolling(window=20, min_periods=1).mean().values

# Smoothed series correlation (lower due to rolling averaging)
r = np.corrcoef(attn_series, vix_smooth)[0, 1]
print(f"Simulated Pearson r(attention_smoothed, VIX) = {r:.3f}")

# ── Plot ──────────────────────────────────────────────────────────────────────
fig, ax1 = plt.subplots(figsize=(10, 4))

color_attn = '#d62728'   # red
color_vix  = '#555555'   # dark gray

# Left axis: attention intensity
ax1.plot(dates, attn_series, color=color_attn, linewidth=1.8,
         label='Cross-Attention Intensity (20d MA)')
ax1.set_xlabel('Date', fontsize=13)
ax1.set_ylabel('Attention Intensity', fontsize=12, color=color_attn)
ax1.tick_params(axis='y', labelcolor=color_attn, labelsize=10)
ax1.tick_params(axis='x', labelsize=10)
ax1.set_ylim(0.10, 1.05)
ax1.spines['right'].set_visible(False)

# Right axis: VIX
ax2 = ax1.twinx()
ax2.plot(dates, vix_smooth, color=color_vix, linewidth=1.4,
         linestyle='--', alpha=0.85, label='VIX Index')
ax2.set_ylabel('VIX Index', fontsize=12, color=color_vix)
ax2.tick_params(axis='y', labelcolor=color_vix, labelsize=10)
ax2.set_ylim(5, 75)
ax2.spines['top'].set_visible(False)

# ── Event annotations ────────────────────────────────────────────────────────
events = [
    ('2023-03-13', 'SVB Crisis',     0.88, -12),
    ('2023-10-20', 'Oct 2023 Spike', 0.82, +8),
    ('2024-11-05', 'Election 2024',  0.72, -12),
]

for date_str, label, attn_level, vix_offset in events:
    idx = date_to_idx(date_str)
    event_date = dates[idx]
    # Vertical line
    ax1.axvline(event_date, color='#888888', linewidth=1.0,
                linestyle=':', alpha=0.8, zorder=2)
    # Label on top
    ax1.annotate(
        label,
        xy=(event_date, attn_series[idx]),
        xytext=(event_date, 0.96),
        fontsize=9, ha='center', color='#333333',
        arrowprops=dict(arrowstyle='->', color='#888888',
                        connectionstyle='arc3,rad=0.0', lw=0.8),
    )

# ── Combined legend ───────────────────────────────────────────────────────────
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2,
           loc='upper left', fontsize=11, frameon=False)

ax1.set_title('Cross-Attention Intensity vs. VIX (2023–2024)',
              fontsize=14, fontweight='bold')

# Correlation note — report raw (pre-smoothing) Pearson r as paper would state
ax1.annotate(
    f'Simulated r = {r_raw:.2f} (raw daily)',
    xy=(0.01, 0.04), xycoords='axes fraction',
    ha='left', va='bottom', fontsize=10, color=color_attn, style='italic'
)

# Simulated data annotation
ax2.annotate(
    '* Simulated Data',
    xy=(1.12, -0.18), xycoords='axes fraction',
    ha='right', va='bottom', fontsize=9, color='#666666',
    style='italic'
)

plt.tight_layout()
plt.savefig('fig5_attention_vix.png', dpi=150, bbox_inches='tight')
print("Saved: fig5_attention_vix.png")
plt.close()
