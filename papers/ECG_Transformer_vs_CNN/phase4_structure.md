# Phase 4 — Paper Structure

## Title
**Transformer, CNN, or Both? A Systematic Benchmark for ECG Arrhythmia Classification Across Architectures, Datasets, and Deployment Constraints**

## Section Outline

### Abstract (200–250 words)
- Background: ECG arrhythmia classification + proliferation of DL architectures
- Gap: No fair, controlled comparison exists across CNN/Transformer/Hybrid
- Method: 6 architectures × 3 datasets × unified evaluation protocol
- Key finding: Hybrid > Transformer > CNN in accuracy; CNN wins in efficiency
- Practical: Architecture selection guideline for deployment scenarios

### 1. Introduction (~700 words, 4 paragraphs)
- **P1** (Background): CVD burden → ECG as diagnostic tool → deep learning promise
  - Cite: LeCun2015, Hannun2019, Ribeiro2020
- **P2** (Problem): Architecture proliferation without fair comparison → reproducibility crisis
  - Cite: AnsariReview2023, AnsariSurvey2025, Strodthoff2021
- **P3** (Contributions): 3-point contribution list
  - C1: Benchmarking framework (6 models, 3 datasets, unified protocol)
  - C2: Cross-dataset empirical evidence with statistical tests
  - C3: Architecture selection guidelines for clinical deployment
  - Cite: DeChazal2004, Imtiaz2024
- **P4** (Organization): Paper structure overview

### 2. Related Work (~700 words, 4 subsections)
- **2.1 CNN-based ECG Classification**: He2016, Fawaz2020, Oh2018, Khan2023, Mathunjwa2022, Yao2020
- **2.2 Transformer-based ECG Classification**: Vaswani2017, Dosovitskiy2021, Meng2022, Dong2023, Varghese2023, Xia2023
- **2.3 Hybrid CNN-Transformer Approaches**: Islam2024, Li2024, Kim2025, Alghieth2025
- **2.4 Lightweight Models and Edge Deployment**: Alamatsaz2024, An2024, Gu2023, Makynen2024
- **Concluding paragraph**: Identifies 3 gaps (unfair comparison, single dataset, no compute profiling)

### 3. Methodology (~1000 words, 6 subsections)
- **3.1 Experimental Framework Overview**: @fig-framework
  - Unified pipeline diagram: Data → Preprocessing → Model → Evaluation
- **3.2 Datasets**: @tbl-datasets
  - MIT-BIH: AAMI 5-class, inter-patient split (DS1/DS2 per DeChazal2004)
  - PTB-XL: 5 superclasses, stratified 10-fold, 500 Hz
  - CPSC2018: 9 rhythm classes, 5-fold cross-validation
  - Cite: Moody2001, Goldberger2000, Wagner2020, Chen2020, PerezAlday2021
- **3.3 Preprocessing Pipeline**:
  - Bandpass filter (0.5–45 Hz), baseline wander removal
  - R-peak detection (Pan-Tompkins), beat segmentation (300 samples)
  - Z-score normalization, SMOTE for class imbalance
  - Cite: Rahman2023
- **3.4 Model Architectures**: @fig-architectures
  - CNN: ResNet-1D-34, InceptionTime (Fawaz2020)
  - Transformer: ViT-ECG, ECG-TransFormer
  - Hybrid: CAT-Net variant (Islam2024), CNN-TransFormer (proposed)
  - Mathematical formulation of key modules (self-attention, residual block)
- **3.5 Training Protocol**:
  - Optimizer: AdamW, LR scheduler: cosine annealing
  - Epochs: 100, early stopping (patience=15)
  - Hardware: NVIDIA RTX 3090, PyTorch 2.x
- **3.6 Evaluation Metrics**:
  - Accuracy, Macro-F1, Precision, Recall, AUROC, Specificity
  - McNemar's test for pairwise comparison, DeLong's test for AUC
  - Computational: Parameters, FLOPs, Inference latency (ms), Memory (MB)

### 4. Results (~900 words, 4 subsections)
- **4.1 Main Results**: @tbl-main-results
  - 6 models × 3 datasets × 7 metrics, bold best, underline second-best
- **4.2 Statistical Significance**: @tbl-significance
  - McNemar's test p-values, pairwise comparison matrix
- **4.3 Computational Efficiency Analysis**: @fig-pareto, @tbl-compute
  - Accuracy vs FLOPs Pareto frontier
  - Latency comparison (GPU vs CPU vs edge)
- **4.4 Ablation Study**: @tbl-ablation
  - Effect of attention mechanism, patch size, number of layers
  - Effect of preprocessing (with/without augmentation)

### 5. Discussion (~600 words, 4 subsections)
- **5.1 When Do Transformers Excel?**: Long-range dependencies, multi-lead analysis
- **5.2 When Do CNNs Remain Competitive?**: Small datasets, edge deployment, morphology-focused
- **5.3 The Case for Hybrid Architectures**: Best of both worlds, when to use
- **5.4 Limitations**:
  - L1: Single-center label quality (MIT-BIH annotations from 1980s)
  - L2: No real-time streaming evaluation (offline batch processing)
  - L3: Limited to standard rhythm classes; rare arrhythmias underrepresented
  - Cite: Berger2023, Hu2023

### 6. Conclusion (~200 words)
- Summary of key findings
- Practical recommendations
- Future work: foundation models, federated learning, real-time deployment
- "We believe this benchmark will serve as a reference..."

## Figure & Table Plan

### Figures (≥ 3) ✅

| ID | Role | Type | Description |
|----|------|------|-------------|
| @fig-framework | Framework | Multi-panel SVG | Overall experimental pipeline: datasets → preprocessing → 6 models → evaluation. 3 panels showing data flow. |
| @fig-architectures | Comparison | Multi-panel SVG | Side-by-side architecture diagrams of 6 models: ResNet-1D, InceptionTime, ViT-ECG, ECG-TransFormer, CAT-Net, CNN-TransFormer. 6 panels (2×3 grid). |
| @fig-pareto | Main Results | Scatter + Pareto | Accuracy vs FLOPs scatter plot with Pareto frontier. Point size = model parameters. Color = architecture family (CNN=blue, Transformer=orange, Hybrid=green). |
| @fig-gradcam | Mechanism | Heatmap | Grad-CAM attention visualization on sample ECG beats: 3 rows (CNN, Transformer, Hybrid) × 3 columns (Normal, SVT, VT). Shows where each model "looks". |

### Tables (≥ 2) ✅

| ID | Role | Description |
|----|------|-------------|
| @tbl-datasets | Setup | Dataset statistics: name, #records, #patients, #classes, leads, sampling rate, split method |
| @tbl-main-results | Main Results | 6 models × 3 datasets: Accuracy, Macro-F1, Precision, Recall, AUROC. Bold best, underline 2nd. |
| @tbl-compute | Efficiency | 6 models: Parameters (M), FLOPs (M), GPU latency (ms), CPU latency (ms), Memory (MB) |
| @tbl-ablation | Ablation | Ablation study: effect of attention, patch size, augmentation, layer depth |
| @tbl-significance | Statistical | McNemar's test p-values for pairwise model comparisons across 3 datasets |

### Total: 4 figures + 5 tables = 9 (≥ 5 ✅)

## Figure Specs

```json
{
  "figures": [
    {
      "id": "fig-framework",
      "narrative_role": "Framework",
      "type": "flow_diagram",
      "panels": 3,
      "color_scheme": "blue_gray_accent",
      "data_source": "conceptual",
      "dimensions": "180mm × 80mm"
    },
    {
      "id": "fig-architectures",
      "narrative_role": "Comparison",
      "type": "architecture_diagram",
      "panels": 6,
      "color_scheme": "blue_orange_green_families",
      "data_source": "conceptual",
      "dimensions": "180mm × 120mm"
    },
    {
      "id": "fig-pareto",
      "narrative_role": "Main Results",
      "type": "scatter_pareto",
      "panels": 1,
      "color_scheme": "blue_orange_green_families",
      "data_source": "tbl-main-results + tbl-compute",
      "dimensions": "90mm × 80mm"
    },
    {
      "id": "fig-gradcam",
      "narrative_role": "Mechanism",
      "type": "heatmap_grid",
      "panels": 9,
      "color_scheme": "jet_colormap",
      "data_source": "model_attention_weights",
      "dimensions": "180mm × 100mm"
    }
  ]
}
```

## Word Count Budget

| Section | Target | Flex |
|---------|--------|------|
| Abstract | 225 | 200–250 |
| Introduction | 700 | 600–800 |
| Related Work | 700 | 500–800 |
| Methodology | 1000 | 800–1200 |
| Results | 900 | 800–1000 |
| Discussion | 600 | 500–700 |
| Conclusion | 200 | 150–250 |
| **Total** | **4325** | **3550–5000** |
