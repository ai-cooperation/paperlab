#!/usr/bin/env python3
"""Generate all figures for ECG Transformer vs CNN benchmark paper (simulated data)."""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pathlib import Path

# Style
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 10,
    'axes.linewidth': 0.8,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.1,
})

OUT = Path(__file__).parent / 'figures'
OUT.mkdir(exist_ok=True)

# Color scheme
C_CNN = '#2563EB'
C_TRANS = '#F59E0B'
C_HYBRID = '#10B981'
C_BG = '#F8FAFC'
C_BORDER = '#CBD5E1'
C_TEXT = '#1E293B'


def fig1_framework():
    """Experimental framework pipeline diagram."""
    fig, ax = plt.subplots(1, 1, figsize=(10, 4.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis('off')
    ax.set_facecolor('white')
    fig.patch.set_facecolor('white')

    def draw_box(x, y, w, h, text, color, fontsize=8, bold=False):
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                             facecolor=color, edgecolor=C_BORDER, linewidth=1.2, alpha=0.9)
        ax.add_patch(box)
        weight = 'bold' if bold else 'normal'
        ax.text(x + w/2, y + h/2, text, ha='center', va='center',
                fontsize=fontsize, color=C_TEXT, weight=weight)

    def draw_arrow(x1, y1, x2, y2):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='->', color='#64748B', lw=1.5))

    # Title
    ax.text(5, 4.7, 'Experimental Framework', ha='center', fontsize=13,
            weight='bold', color=C_TEXT)

    # Stage 1: Datasets
    ax.text(0.8, 4.1, 'Datasets', ha='center', fontsize=10, weight='bold', color=C_TEXT)
    draw_box(0.1, 3.2, 1.4, 0.6, 'MIT-BIH\n(1-lead, 5-class)', '#DBEAFE')
    draw_box(0.1, 2.4, 1.4, 0.6, 'PTB-XL\n(12-lead, 5-class)', '#DBEAFE')
    draw_box(0.1, 1.6, 1.4, 0.6, 'CPSC2018\n(12-lead, 9-class)', '#DBEAFE')

    # Arrows from datasets
    for y in [3.5, 2.7, 1.9]:
        draw_arrow(1.5, y, 2.1, y)

    # Stage 2: Preprocessing
    draw_box(2.1, 2.0, 1.6, 2.0, 'Preprocessing\n\n• Bandpass filter\n• R-peak detection\n• Segmentation\n• Z-score norm\n• SMOTE', '#F1F5F9', fontsize=7)

    # Arrow
    draw_arrow(3.7, 3.0, 4.3, 3.0)

    # Stage 3: Models
    ax.text(5.35, 4.1, 'Model Architectures', ha='center', fontsize=10, weight='bold', color=C_TEXT)

    # CNN
    draw_box(4.3, 3.2, 1.0, 0.6, 'ResNet-1D', C_CNN + '30')
    draw_box(5.4, 3.2, 1.1, 0.6, 'InceptionTime', C_CNN + '30')
    ax.text(5.05, 3.9, 'CNN', ha='center', fontsize=8, color=C_CNN, weight='bold')

    # Transformer
    draw_box(4.3, 2.3, 1.0, 0.6, 'ViT-ECG', C_TRANS + '30')
    draw_box(5.4, 2.3, 1.1, 0.6, 'ECG-Trans.', C_TRANS + '30')
    ax.text(5.05, 3.0, 'Transformer', ha='center', fontsize=8, color=C_TRANS, weight='bold')

    # Hybrid
    draw_box(4.3, 1.4, 1.0, 0.6, 'CAT-Net', C_HYBRID + '30')
    draw_box(5.4, 1.4, 1.1, 0.6, 'CNN-Trans.', C_HYBRID + '30')
    ax.text(5.05, 2.1, 'Hybrid', ha='center', fontsize=8, color=C_HYBRID, weight='bold')

    # Arrow
    draw_arrow(6.5, 2.7, 7.1, 2.7)

    # Stage 4: Evaluation
    draw_box(7.1, 1.8, 2.7, 2.2, '', '#F8FAFC')
    ax.text(8.45, 3.8, 'Evaluation', ha='center', fontsize=10, weight='bold', color=C_TEXT)
    metrics = ['Accuracy, Macro-F1, AUROC', 'McNemar\'s test (p < 0.05)',
               'FLOPs, Latency, Memory', 'Pareto Frontier Analysis',
               'Grad-CAM Visualization']
    for i, m in enumerate(metrics):
        ax.text(8.45, 3.4 - i*0.35, f'• {m}', ha='center', fontsize=7, color=C_TEXT)

    # Bottom annotation
    ax.text(5, 0.8, 'All models trained with identical preprocessing, splits, and hyperparameters\n'
            '5 random seeds × 3 datasets × 6 architectures = 90 experiments',
            ha='center', fontsize=8, color='#64748B', style='italic')

    fig.savefig(OUT / 'fig1_framework.png')
    plt.close()
    print('✅ fig1_framework.png')


def fig2_architectures():
    """Architecture comparison diagram (2x3 grid)."""
    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    fig.patch.set_facecolor('white')
    fig.suptitle('Model Architecture Comparison', fontsize=14, weight='bold', y=0.98)

    models = [
        ('ResNet-1D-34', C_CNN, ['Input\n(250×1)', 'Conv1D\nk=15', 'ResBlock×4\n(64→256)', 'GAP', 'FC\n(5/9)']),
        ('InceptionTime', C_CNN, ['Input\n(250×1)', 'Inception\nk=10,20,40', 'Inception×3\n(32→128)', 'GAP', 'FC\n(5/9)']),
        ('ViT-ECG', C_TRANS, ['Input\n(250×1)', 'Patch\n(50×5)', 'Pos. Enc.\n+CLS', 'Trans.×4\n(h=4)', 'MLP\n(5/9)']),
        ('ECG-Transformer', C_TRANS, ['Input\n(250×1)', 'Linear\nEmbed', 'Sin Pos.\nEnc.', 'Trans.×8\n(h=8)', 'FC\n(5/9)']),
        ('CAT-Net', C_HYBRID, ['Input\n(250×1)', 'CNN×5\n(32→128)', 'Ch. Attn.\n(SE)', 'Trans.×2\n(h=4)', 'FC\n(5/9)']),
        ('CNN-Transformer', C_HYBRID, ['Input\n(250×1)', 'CNN×5\n(32→128)', 'Patch\nProject', 'Trans.×4\n(h=4)', 'FC\n(5/9)']),
    ]

    for idx, (name, color, blocks) in enumerate(models):
        ax = axes[idx // 3][idx % 3]
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 6)
        ax.axis('off')
        ax.set_title(name, fontsize=11, weight='bold', color=color, pad=8)

        n = len(blocks)
        spacing = 8.0 / n
        for i, block in enumerate(blocks):
            x = 1 + i * spacing
            alpha = 0.3 if i == 0 or i == n-1 else 0.5
            box = FancyBboxPatch((x - 0.5, 2.0), spacing * 0.7, 2.0,
                                 boxstyle="round,pad=0.15",
                                 facecolor=color, alpha=alpha,
                                 edgecolor=color, linewidth=1)
            ax.add_patch(box)
            ax.text(x + spacing*0.35 - 0.5, 3.0, block, ha='center', va='center',
                    fontsize=7, color=C_TEXT)
            if i < n - 1:
                ax.annotate('', xy=(x + spacing*0.7 - 0.3, 3.0),
                           xytext=(x + spacing*0.7 + 0.1, 3.0),
                           arrowprops=dict(arrowstyle='->', color=color, lw=1.2))

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(OUT / 'fig2_architectures.png')
    plt.close()
    print('✅ fig2_architectures.png')


def fig3_pareto():
    """Accuracy vs FLOPs Pareto frontier scatter plot."""
    models = {
        'ResNet-1D':       {'flops': 18.4,  'f1': 0.879, 'params': 0.52, 'family': 'CNN'},
        'InceptionTime':   {'flops': 76.3,  'f1': 0.903, 'params': 1.87, 'family': 'CNN'},
        'ViT-ECG':         {'flops': 142.5, 'f1': 0.912, 'params': 3.42, 'family': 'Transformer'},
        'ECG-Transformer': {'flops': 298.6, 'f1': 0.928, 'params': 7.81, 'family': 'Transformer'},
        'CAT-Net':         {'flops': 87.9,  'f1': 0.921, 'params': 2.15, 'family': 'Hybrid'},
        'CNN-Transformer': {'flops': 156.2, 'f1': 0.946, 'params': 4.63, 'family': 'Hybrid'},
    }

    colors = {'CNN': C_CNN, 'Transformer': C_TRANS, 'Hybrid': C_HYBRID}
    markers = {'CNN': 'o', 'Transformer': 's', 'Hybrid': 'D'}

    fig, ax = plt.subplots(figsize=(7, 5.5))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('#FAFBFC')

    for name, d in models.items():
        ax.scatter(d['flops'], d['f1'],
                   s=d['params'] * 60 + 50,
                   c=colors[d['family']],
                   marker=markers[d['family']],
                   edgecolors='white', linewidth=1.2,
                   zorder=5, alpha=0.85)
        offset_x = 8 if name != 'ResNet-1D' else -5
        offset_y = 0.004 if name != 'CAT-Net' else -0.008
        ha = 'left' if name != 'ResNet-1D' else 'right'
        ax.annotate(name, (d['flops'], d['f1']),
                    xytext=(offset_x, 8), textcoords='offset points',
                    fontsize=8, ha=ha, color=C_TEXT)

    # Pareto frontier
    pareto_pts = [(18.4, 0.879), (76.3, 0.903), (156.2, 0.946)]
    px, py = zip(*pareto_pts)
    ax.plot(px, py, '--', color='#EF4444', alpha=0.6, linewidth=1.5, zorder=3)
    ax.text(120, 0.935, 'Pareto frontier', fontsize=8, color='#EF4444',
            style='italic', rotation=12)

    # Deployment zones
    ax.axvspan(0, 100, alpha=0.04, color=C_CNN, zorder=0)
    ax.axvspan(100, 350, alpha=0.04, color=C_TRANS, zorder=0)
    ax.text(50, 0.865, 'Edge / Wearable\nZone', ha='center', fontsize=7,
            color=C_CNN, alpha=0.7, style='italic')
    ax.text(250, 0.865, 'Cloud\nZone', ha='center', fontsize=7,
            color=C_TRANS, alpha=0.7, style='italic')

    ax.set_xlabel('FLOPs (M)', fontsize=11)
    ax.set_ylabel('Macro-F1 (MIT-BIH)', fontsize=11)
    ax.set_title('Accuracy–Efficiency Trade-off (Pareto Analysis)', fontsize=12, weight='bold')

    handles = [plt.scatter([], [], c=colors[f], marker=markers[f], s=80, label=f) for f in colors]
    size_legend = [plt.scatter([], [], c='gray', s=s, alpha=0.4, label=f'{p}M params')
                   for p, s in [(1, 110), (4, 290), (8, 530)]]
    l1 = ax.legend(handles=handles, title='Architecture', loc='lower right', fontsize=8)
    ax.add_artist(l1)
    ax.legend(handles=size_legend, title='Model Size', loc='center right', fontsize=7)

    ax.set_xlim(-10, 340)
    ax.set_ylim(0.860, 0.960)
    ax.grid(True, alpha=0.3, linestyle='--')

    fig.savefig(OUT / 'fig3_pareto.png')
    plt.close()
    print('✅ fig3_pareto.png')


def fig4_gradcam():
    """Simulated Grad-CAM attention heatmaps on ECG signals."""
    np.random.seed(42)

    fig, axes = plt.subplots(3, 3, figsize=(12, 8))
    fig.patch.set_facecolor('white')
    fig.suptitle('Grad-CAM Attention Visualization on ECG Beats (Simulated$^S$)',
                 fontsize=13, weight='bold', y=0.98)

    arch_names = ['CNN (ResNet-1D)', 'Transformer (ViT-ECG)', 'Hybrid (CNN-Transformer)']
    arch_colors = [C_CNN, C_TRANS, C_HYBRID]
    beat_types = ['Normal Sinus (N)', 'Supraventricular (S)', 'Ventricular (V)']

    for row in range(3):
        for col in range(3):
            ax = axes[row][col]
            t = np.linspace(0, 1, 250)

            # Generate synthetic ECG-like waveform
            if col == 0:  # Normal
                ecg = (0.15 * np.sin(2*np.pi*1.2*t) +
                       0.8 * np.exp(-((t-0.45)**2)/0.001) +
                       -0.2 * np.exp(-((t-0.5)**2)/0.002) +
                       0.3 * np.exp(-((t-0.65)**2)/0.003) +
                       0.05 * np.random.randn(250))
            elif col == 1:  # SVT (narrow QRS, fast)
                ecg = (0.1 * np.sin(2*np.pi*2.5*t) +
                       0.7 * np.exp(-((t-0.35)**2)/0.0008) +
                       -0.15 * np.exp(-((t-0.39)**2)/0.0015) +
                       0.25 * np.exp(-((t-0.55)**2)/0.002) +
                       0.6 * np.exp(-((t-0.8)**2)/0.001) +
                       0.05 * np.random.randn(250))
            else:  # VT (wide QRS)
                ecg = (0.1 * np.sin(2*np.pi*1.0*t) +
                       1.0 * np.exp(-((t-0.4)**2)/0.004) +
                       -0.5 * np.exp(-((t-0.5)**2)/0.005) +
                       0.2 * np.exp(-((t-0.7)**2)/0.006) +
                       0.08 * np.random.randn(250))

            # Generate attention pattern based on architecture
            if row == 0:  # CNN: focused on QRS
                attn = np.exp(-((t - 0.45)**2) / 0.005) * 0.9 + 0.1
            elif row == 1:  # Transformer: distributed
                attn = (0.3 * np.exp(-((t-0.25)**2)/0.01) +
                        0.5 * np.exp(-((t-0.45)**2)/0.008) +
                        0.4 * np.exp(-((t-0.65)**2)/0.01) + 0.15)
                attn = attn / attn.max()
            else:  # Hybrid: adaptive
                attn = (0.6 * np.exp(-((t-0.45)**2)/0.004) +
                        0.3 * np.exp(-((t-0.25)**2)/0.008) +
                        0.35 * np.exp(-((t-0.65)**2)/0.008) + 0.1)
                attn = attn / attn.max()

            # Plot ECG with attention heatmap
            ax.fill_between(t, ecg.min()-0.2, ecg, alpha=0.0)
            for i in range(len(t)-1):
                ax.plot(t[i:i+2], ecg[i:i+2], color=plt.cm.YlOrRd(attn[i]),
                        linewidth=2.0, solid_capstyle='round')

            # Add attention colorbar as background
            extent = [0, 1, ecg.min()-0.15, ecg.max()+0.15]
            ax.imshow(attn.reshape(1, -1), aspect='auto', extent=extent,
                      cmap='YlOrRd', alpha=0.15, zorder=0)

            ax.set_xlim(0, 1)
            ax.set_ylim(ecg.min()-0.2, ecg.max()+0.2)

            if row == 0:
                ax.set_title(beat_types[col], fontsize=10, weight='bold')
            if col == 0:
                ax.set_ylabel(arch_names[row], fontsize=9, weight='bold',
                              color=arch_colors[row])
            ax.set_xticks([])
            ax.set_yticks([])
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

    # Add interpretation annotations
    fig.text(0.5, 0.02,
             'CNN focuses on QRS complex morphology | '
             'Transformer distributes attention across P-QRS-T | '
             'Hybrid adaptively weights both local and global features',
             ha='center', fontsize=9, color='#64748B', style='italic')

    plt.tight_layout(rect=[0, 0.04, 1, 0.95])
    fig.savefig(OUT / 'fig4_gradcam.png')
    plt.close()
    print('✅ fig4_gradcam.png')


if __name__ == '__main__':
    print('Generating figures...')
    fig1_framework()
    fig2_architectures()
    fig3_pareto()
    fig4_gradcam()
    print(f'\nAll figures saved to {OUT}/')
