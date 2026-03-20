"""
Figure 1: FinMM-LLM Framework Architecture Diagram
Generates fig1_framework.png for the FinMM-LLM paper.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
import os

# ── Color palette ──────────────────────────────────────────────────────────────
BLUE    = "#4472C4"   # text / NLP path
ORANGE  = "#ED7D31"   # price path
PURPLE  = "#7030A0"   # cross-modal attention
GREEN   = "#548235"   # gated fusion / output
WHITE   = "#FFFFFF"
LTBLUE  = "#D9E2F3"   # light blue fill
LTORANGE= "#FBE5D6"   # light orange fill
LTPURPLE= "#E2D1F0"   # light purple fill
LTGREEN = "#E2EFDA"   # light green fill
GRAY    = "#404040"   # arrow / border grey

FS_LABEL   = 12   # box label font size
FS_SUBSCR  = 10   # subscript / annotation
FS_HEADER  = 11   # layer header

# ── Canvas ─────────────────────────────────────────────────────────────────────
fig_w, fig_h = 12, 6          # inches  →  1200×600 @ 100 DPI, ×1.5 @ 150 DPI
fig, ax = plt.subplots(figsize=(fig_w, fig_h))
ax.set_xlim(0, 12)
ax.set_ylim(0, 6)
ax.set_aspect("equal")
ax.axis("off")
fig.patch.set_facecolor(WHITE)

# ── Helper: rounded box ────────────────────────────────────────────────────────
def rbox(ax, x, y, w, h, fc, ec, lw=1.6, radius=0.22):
    """Draw a rounded rectangle centred at (x, y)."""
    patch = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        facecolor=fc, edgecolor=ec, linewidth=lw, zorder=3,
    )
    ax.add_patch(patch)


def label(ax, x, y, text, color, fs=FS_LABEL, bold=False, va="center", ha="center"):
    weight = "bold" if bold else "normal"
    ax.text(x, y, text, color=color, fontsize=fs, fontweight=weight,
            va=va, ha=ha, zorder=4)


def arrow(ax, x0, y0, x1, y1, color=GRAY, lw=1.4, arrowstyle="->", connectionstyle="arc3,rad=0.0"):
    ax.annotate(
        "", xy=(x1, y1), xytext=(x0, y0),
        arrowprops=dict(
            arrowstyle=arrowstyle,
            color=color, lw=lw,
            connectionstyle=connectionstyle,
        ),
        zorder=2,
    )


# ══════════════════════════════════════════════════════════════════════════════
# LAYER HEADER LABELS  (background bands)
# ══════════════════════════════════════════════════════════════════════════════
layer_info = [
    (0.9, "Input\nLayer"),
    (2.5, "Encoder\nLayer"),
    (4.5, "Embedding"),
    (6.1, "Cross-Modal\nAttention"),
    (8.1, "Gated\nFusion"),
    (10.2, "Output\nLayer"),
]
for lx, ltxt in layer_info:
    ax.text(lx, 5.72, ltxt, color="#888888", fontsize=FS_HEADER - 1,
            ha="center", va="top", style="italic", linespacing=1.3, zorder=1)

# Vertical separator lines
for lx in [1.75, 3.5, 5.3, 7.2, 9.3]:
    ax.plot([lx, lx], [0.4, 5.55], color="#E0E0E0", lw=1.0, ls="--", zorder=0)

# ══════════════════════════════════════════════════════════════════════════════
# INPUT LAYER
# ══════════════════════════════════════════════════════════════════════════════
# Text input box
rbox(ax, 0.9, 4.1, 1.55, 0.70, LTBLUE, BLUE)
label(ax, 0.9, 4.1, "Financial\nNews Text", BLUE, fs=FS_LABEL - 1, bold=True)

# Price input box
rbox(ax, 0.9, 1.9, 1.55, 0.70, LTORANGE, ORANGE)
label(ax, 0.9, 1.9, "OHLCV\nPrice Series", ORANGE, fs=FS_LABEL - 1, bold=True)

# ══════════════════════════════════════════════════════════════════════════════
# ENCODER LAYER
# ══════════════════════════════════════════════════════════════════════════════
rbox(ax, 2.65, 4.1, 1.55, 0.68, LTBLUE, BLUE)
label(ax, 2.65, 4.22, "FinBERT", BLUE, fs=FS_LABEL, bold=True)
label(ax, 2.65, 3.95, "Encoder", BLUE, fs=FS_LABEL - 1)

rbox(ax, 2.65, 1.9, 1.55, 0.68, LTORANGE, ORANGE)
label(ax, 2.65, 2.02, "PatchTST", ORANGE, fs=FS_LABEL, bold=True)
label(ax, 2.65, 1.75, "Encoder", ORANGE, fs=FS_LABEL - 1)

# ══════════════════════════════════════════════════════════════════════════════
# EMBEDDING OUTPUT (labels only — no box, just stylised text)
# ══════════════════════════════════════════════════════════════════════════════
# Text embedding label
ax.text(4.55, 4.1, r"$\mathbf{T}_{i,t}$", color=BLUE,
        fontsize=14, ha="center", va="center", zorder=4)
ax.text(4.55, 3.72, "text emb.", color=BLUE, fontsize=9,
        ha="center", va="center", zorder=4, style="italic")

# Price embedding label
ax.text(4.55, 1.9, r"$\mathbf{S}_{i,t}$", color=ORANGE,
        fontsize=14, ha="center", va="center", zorder=4)
ax.text(4.55, 1.52, "price emb.", color=ORANGE, fontsize=9,
        ha="center", va="center", zorder=4, style="italic")

# ══════════════════════════════════════════════════════════════════════════════
# CROSS-MODAL ATTENTION
# ══════════════════════════════════════════════════════════════════════════════
# Main box — taller to accommodate both directions
rbox(ax, 6.25, 3.0, 1.75, 2.60, LTPURPLE, PURPLE, lw=2.0)
label(ax, 6.25, 4.05, "Bidirectional", PURPLE, fs=FS_LABEL - 1, bold=True)
label(ax, 6.25, 3.72, "Cross-Modal", PURPLE, fs=FS_LABEL - 1, bold=True)
label(ax, 6.25, 3.39, "Attention", PURPLE, fs=FS_LABEL, bold=True)

# Internal sub-labels
label(ax, 6.25, 2.78, "Text → Price", PURPLE, fs=FS_SUBSCR - 1)
label(ax, 6.25, 2.48, "Price → Text", PURPLE, fs=FS_SUBSCR - 1)

# Internal bidirectional arrows (within the box)
ax.annotate("", xy=(6.65, 2.78), xytext=(5.85, 2.78),
            arrowprops=dict(arrowstyle="->", color=BLUE, lw=1.2), zorder=5)
ax.annotate("", xy=(5.85, 2.48), xytext=(6.65, 2.48),
            arrowprops=dict(arrowstyle="->", color=ORANGE, lw=1.2), zorder=5)

# ══════════════════════════════════════════════════════════════════════════════
# GATED FUSION
# ══════════════════════════════════════════════════════════════════════════════
rbox(ax, 8.2, 3.0, 1.65, 1.10, LTGREEN, GREEN, lw=2.0)
label(ax, 8.2, 3.18, "Gated Fusion", GREEN, fs=FS_LABEL, bold=True)
# sigma gate symbol
ax.text(8.2, 2.82, r"$\sigma(\mathbf{g}) \odot$", color=GREEN,
        fontsize=13, ha="center", va="center", zorder=4)

# ══════════════════════════════════════════════════════════════════════════════
# OUTPUT LAYER
# ══════════════════════════════════════════════════════════════════════════════
# Decision Head
rbox(ax, 10.2, 3.55, 1.55, 0.68, LTGREEN, GREEN)
label(ax, 10.2, 3.67, "Decision", GREEN, fs=FS_LABEL, bold=True)
label(ax, 10.2, 3.42, "Head", GREEN, fs=FS_LABEL - 1)

# Portfolio Signal
rbox(ax, 10.2, 2.35, 1.65, 0.78, LTGREEN, GREEN)
label(ax, 10.2, 2.50, "Portfolio Signal", GREEN, fs=FS_LABEL - 1, bold=True)
ax.text(10.2, 2.22, r"$s_{i,t}$", color=GREEN, fontsize=13,
        ha="center", va="center", zorder=4)

# ══════════════════════════════════════════════════════════════════════════════
# ARROWS
# ══════════════════════════════════════════════════════════════════════════════
# Input → Encoder
arrow(ax, 1.68, 4.10, 1.88, 4.10, color=BLUE)
arrow(ax, 1.68, 1.90, 1.88, 1.90, color=ORANGE)

# Encoder → Embedding
arrow(ax, 3.43, 4.10, 3.93, 4.10, color=BLUE)
arrow(ax, 3.43, 1.90, 3.93, 1.90, color=ORANGE)

# Embedding → Cross-Modal Attention (converging)
arrow(ax, 5.17, 4.10, 5.33, 4.10, color=BLUE, connectionstyle="arc3,rad=-0.25")
arrow(ax, 5.17, 1.90, 5.33, 1.90, color=ORANGE, connectionstyle="arc3,rad=0.25")

# Cross-Modal Attention → Gated Fusion
arrow(ax, 7.13, 3.0, 7.38, 3.0, color=PURPLE, lw=1.8)

# Gated Fusion → Decision Head
arrow(ax, 9.03, 3.30, 9.43, 3.55, color=GREEN, lw=1.6)

# Decision Head → Portfolio Signal
arrow(ax, 10.2, 3.22, 10.2, 2.74, color=GREEN, lw=1.6)

# ══════════════════════════════════════════════════════════════════════════════
# ANNOTATIONS
# ══════════════════════════════════════════════════════════════════════════════
# Dimension hints
ax.text(4.02, 4.30, "d=768", color=BLUE, fontsize=8.5,
        ha="left", va="bottom", style="italic", zorder=4)
ax.text(4.02, 2.10, "d=768", color=ORANGE, fontsize=8.5,
        ha="left", va="bottom", style="italic", zorder=4)

# "* Simulated Data" bottom-right
ax.text(11.85, 0.25, "* Simulated Data", color="#999999",
        fontsize=9, ha="right", va="bottom", style="italic", zorder=4)

# ── Final layout & save ────────────────────────────────────────────────────────
plt.tight_layout(pad=0.3)

out_dir  = os.path.dirname(os.path.abspath(__file__))
out_path = os.path.join(out_dir, "fig1_framework.png")
fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=WHITE)
out_svg = os.path.join(out_dir, "fig1_framework.svg")
fig.savefig(out_svg, format="svg", bbox_inches="tight", facecolor=WHITE)
plt.close(fig)
print(f"Saved: {out_path}")
print(f"Saved: {out_svg}")
