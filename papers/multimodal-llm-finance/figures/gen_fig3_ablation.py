"""
gen_fig3_ablation.py
Figure 3: Ablation Study — Grouped Bar Chart (3 panels)
Simulated Data — publication-quality figure for FinMM-LLM paper.
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt

matplotlib.rcParams['font.family'] = 'DejaVu Sans'
matplotlib.rcParams['axes.spines.top'] = False
matplotlib.rcParams['axes.spines.right'] = False

np.random.seed(42)

# ── Data ─────────────────────────────────────────────────────────────────────
panels = [
    {
        'title': '(a) Text Encoder',
        'labels': ['FinBERT', 'GPT-Embed', 'LM-Dict'],
        'values': [1.55, 1.42, 1.15],
    },
    {
        'title': '(b) TS Encoder',
        'labels': ['PatchTST', 'iTransformer', 'LSTM'],
        'values': [1.55, 1.48, 1.25],
    },
    {
        'title': '(c) Fusion Method',
        'labels': ['CrossAttn', 'Concat', 'Ensemble'],
        'values': [1.55, 1.30, 1.20],
    },
]

# Blue sequential palette (light → dark)
palette = ['#084594', '#2171b5', '#6baed6']

# ── Plot ─────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharey=False)

bar_width = 0.50
x = np.arange(3)

for ax, panel in zip(axes, panels):
    bars = ax.bar(
        x,
        panel['values'],
        width=bar_width,
        color=palette,
        edgecolor='white',
        linewidth=0.8,
        zorder=3,
    )

    # Value labels on top of bars
    for bar, val in zip(bars, panel['values']):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            f'{val:.2f}',
            ha='center', va='bottom',
            fontsize=11, fontweight='bold',
        )

    ax.set_xticks(x)
    ax.set_xticklabels(panel['labels'], fontsize=11)
    ax.set_title(panel['title'], fontsize=13, fontweight='bold', pad=8)
    ax.set_ylabel('Sharpe Ratio' if ax is axes[0] else '', fontsize=12)
    ax.tick_params(axis='y', labelsize=10)
    ax.set_ylim(0.9, 1.80)
    ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(0.20))

    # Highlight the best bar (first, always 1.55 = FinMM-LLM full model)
    bars[0].set_edgecolor('#d62728')
    bars[0].set_linewidth(2.0)

    # No vertical gridlines; optional light horizontal gridlines
    ax.yaxis.grid(False)
    ax.set_axisbelow(False)

# Simulated data annotation on last panel
axes[2].annotate(
    '* Simulated Data',
    xy=(1.0, -0.18), xycoords='axes fraction',
    ha='right', va='bottom', fontsize=9, color='#666666',
    style='italic'
)

plt.suptitle('Ablation Study: Component Contribution to Sharpe Ratio',
             fontsize=14, fontweight='bold', y=1.03)

plt.tight_layout()
plt.savefig('fig3_ablation.png', dpi=150, bbox_inches='tight')
plt.savefig('fig3_ablation.svg', format='svg', bbox_inches='tight')
print("Saved: fig3_ablation.png")
print("Saved: fig3_ablation.svg")
plt.close()
