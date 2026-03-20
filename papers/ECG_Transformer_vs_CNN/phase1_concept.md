# Research Concept — ECG Arrhythmia Classification: Transformer vs CNN

## Research Question

**RQ**: Under controlled experimental conditions (identical preprocessing, dataset splits, and evaluation protocols), do Transformer-based architectures consistently outperform CNN-based architectures for multi-class ECG arrhythmia classification, and if so, under what clinical and computational constraints does this advantage hold?

## Core Hypothesis

**H1**: Transformer-based models achieve statistically significantly higher macro-F1 scores than CNN-based models on inter-patient ECG arrhythmia classification (AAMI standard) due to their ability to capture long-range temporal dependencies in ECG morphology.

**H2**: The performance advantage of Transformers diminishes under computational constraints (model size < 1M parameters, inference latency < 10ms), where lightweight CNNs remain competitive.

**H3**: Hybrid CNN-Transformer architectures outperform both pure CNN and pure Transformer models by combining local morphological feature extraction with global temporal attention.

## Three Contributions

1. **Methodological Contribution** — A rigorous, reproducible benchmarking framework that evaluates 6 representative architectures (2 CNN, 2 Transformer, 2 Hybrid) under strictly controlled conditions including identical preprocessing, AAMI-standard inter-patient splits, and unified evaluation metrics, addressing the lack of fair comparisons in existing literature.

2. **Empirical Contribution** — Comprehensive empirical evidence quantifying the accuracy–efficiency trade-off between Transformer and CNN architectures across three public ECG datasets (MIT-BIH, PTB-XL, CPSC2018), with statistical significance testing (McNemar's test, DeLong's test for AUC) and computational profiling (FLOPs, latency, memory).

3. **Practical Contribution** — An architecture selection guideline for clinical deployment scenarios, providing decision criteria based on target device constraints (cloud server, edge device, wearable), number of arrhythmia classes, and acceptable latency thresholds.

## Three Limitations in Existing Literature

1. **Unfair Comparison Protocols** — Most existing studies compare Transformer vs CNN using different preprocessing pipelines, dataset splits (random vs inter-patient), and evaluation metrics, making results non-comparable. For example, studies reporting >99% accuracy often use intra-patient splits that inflate performance due to data leakage.

2. **Narrow Dataset Scope** — The majority of ECG classification studies exclusively use MIT-BIH (48 patients, 1980s data), ignoring cross-dataset generalizability. Few studies validate on modern, multi-lead datasets like PTB-XL (21,837 records) or CPSC2018 (6,877 records).

3. **Missing Computational Cost Analysis** — While Transformer models show accuracy improvements, most studies omit computational profiling (FLOPs, inference latency, memory footprint), which is critical for clinical deployment on resource-constrained devices such as wearable monitors and bedside monitors.

## Target Journal

- **Journal**: Computers in Biology and Medicine
- **Impact Factor**: 6.3 (JCR 2024) / 8.43 (Scopus CiteScore)
- **SJR**: 1.447 (Q1)
- **h-index**: 142
- **Scope fit**: The journal explicitly covers biomedical signal processing, deep learning for medical applications, and ECG analysis. Recent publications include multiple ECG classification studies using CNN, Transformer, and hybrid architectures, confirming strong topical alignment.

## Expected Results (MVP — for simulated data generation)

| Metric | Pure CNN (best) | Pure Transformer (best) | Hybrid (best) |
|--------|----------------|------------------------|----------------|
| Accuracy (MIT-BIH, 5-class) | 96.2 ± 0.8% | 97.5 ± 0.6% | 98.3 ± 0.4% |
| Macro-F1 (MIT-BIH, 5-class) | 0.891 ± 0.025 | 0.923 ± 0.018 | 0.946 ± 0.015 |
| Macro-F1 (PTB-XL, superclass) | 0.842 ± 0.030 | 0.878 ± 0.022 | 0.901 ± 0.019 |
| Macro-F1 (CPSC2018, 9-class) | 0.811 ± 0.035 | 0.845 ± 0.028 | 0.867 ± 0.024 |
| Parameters (M) | 0.5–2.0 | 1.5–8.0 | 1.0–5.0 |
| Inference Latency (ms/sample) | 2–5 | 8–25 | 5–15 |
| FLOPs (M) | 15–80 | 50–300 | 30–150 |

## Datasets

1. **MIT-BIH Arrhythmia Database** — 48 patients, 109,446 beats, 5 AAMI classes (N, S, V, F, Q), single-lead (MLII), 360 Hz
2. **PTB-XL** — 21,837 12-lead ECG records, 18,885 patients, 5 superclasses + 23 subclasses, 500 Hz
3. **CPSC2018** — 6,877 12-lead ECG records, 9 rhythm classes, 500 Hz

## Models to Compare

### CNN-based
1. **ResNet-1D** — 1D ResNet-34 adapted for ECG (baseline, well-established)
2. **InceptionTime** — Multi-scale temporal convolution (state-of-the-art for time-series)

### Transformer-based
3. **Vanilla ViT-ECG** — Vision Transformer adapted for 1D ECG signals (patch embedding + position encoding)
4. **ECG-DETR** — Detection Transformer for continuous ECG segments

### Hybrid CNN-Transformer
5. **CAT-Net** — CNN + Multi-Head Self-Attention + Transformer encoder
6. **CNN-Transformer** — CNN feature extractor + Transformer encoder (proposed lightweight variant)
