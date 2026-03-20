"""
gen_fig4_attention_heatmap.py
Figure 4: Cross-Attention Heatmap — Earnings vs Normal Period
Simulated Data — publication-quality figure for FinMM-LLM paper.
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable

matplotlib.rcParams['font.family'] = 'DejaVu Sans'

np.random.seed(42)

# ── Axes labels ───────────────────────────────────────────────────────────────
# X: 4 price patches (5-day windows: Day-10→-6, -5→-1, +1→+5, +6→+10)
patch_labels = ['Day −10 to −6', 'Day −5 to −1', 'Day +1 to +5', 'Day +6 to +10']
# Y: 4 text token categories
token_labels = ['Sentiment', 'Financial Terms', 'Entity Names', 'Other']

n_tokens = len(token_labels)
n_patches = len(patch_labels)

# ── Simulate attention weights ────────────────────────────────────────────────
# Earnings window: high, concentrated on Sentiment × near-event patches
earnings_base = np.array([
    [0.82, 0.91, 0.78, 0.55],   # Sentiment — highest, peaks at Day-5→-1
    [0.62, 0.74, 0.69, 0.48],   # Financial Terms
    [0.45, 0.52, 0.47, 0.35],   # Entity Names
    [0.22, 0.28, 0.25, 0.18],   # Other
], dtype=float)
earnings_noise = np.random.default_rng(42).normal(0, 0.03, earnings_base.shape)
earnings = np.clip(earnings_base + earnings_noise, 0.05, 1.0)

# Normal period: lower, more diffuse
normal_base = np.array([
    [0.38, 0.42, 0.40, 0.35],
    [0.33, 0.36, 0.34, 0.30],
    [0.28, 0.30, 0.29, 0.25],
    [0.20, 0.22, 0.21, 0.18],
], dtype=float)
normal_noise = np.random.default_rng(99).normal(0, 0.025, normal_base.shape)
normal = np.clip(normal_base + normal_noise, 0.05, 1.0)

# ── Plot ──────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(10, 5))

vmin, vmax = 0.0, 1.0
cmap = 'viridis'

for ax, data, title in zip(
    axes,
    [earnings, normal],
    ['(a) Earnings Window', '(b) Normal Period'],
):
    im = ax.imshow(data, cmap=cmap, aspect='auto',
                   vmin=vmin, vmax=vmax, interpolation='nearest')

    # Axis ticks
    ax.set_xticks(np.arange(n_patches))
    ax.set_yticks(np.arange(n_tokens))
    ax.set_xticklabels(patch_labels, fontsize=10, rotation=20, ha='right')
    ax.set_yticklabels(token_labels, fontsize=11)

    # Cell value annotations
    for i in range(n_tokens):
        for j in range(n_patches):
            val = data[i, j]
            text_color = 'white' if val < 0.55 else 'black'
            ax.text(j, i, f'{val:.2f}',
                    ha='center', va='center',
                    fontsize=10, color=text_color, fontweight='bold')

    ax.set_title(title, fontsize=13, fontweight='bold', pad=10)
    ax.set_xlabel('Price Patches', fontsize=12)
    if ax is axes[0]:
        ax.set_ylabel('Text Token Category', fontsize=12)

    # Individual colorbar per panel
    divider = make_axes_locatable(ax)
    cax = divider.append_axes('right', size='4%', pad=0.12)
    cbar = fig.colorbar(im, cax=cax)
    cbar.set_label('Attention Weight', fontsize=10)
    cbar.ax.tick_params(labelsize=9)

# Simulated data annotation
axes[1].annotate(
    '* Simulated Data',
    xy=(1.15, -0.32), xycoords='axes fraction',
    ha='right', va='bottom', fontsize=9, color='#666666',
    style='italic'
)

plt.suptitle('Cross-Attention Weights: Text Tokens × Price Patches',
             fontsize=14, fontweight='bold', y=1.02)

plt.tight_layout()
plt.savefig('fig4_attention_heatmap.png', dpi=150, bbox_inches='tight')
print("Saved: fig4_attention_heatmap.png")
plt.close()
