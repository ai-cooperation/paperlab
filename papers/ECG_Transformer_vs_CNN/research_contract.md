# Research Contract — ECG Transformer vs CNN Benchmark

## Scope
- **IN**: Systematic benchmark of CNN vs Transformer vs Hybrid for ECG arrhythmia classification
- **OUT**: Novel architecture proposal, clinical trial validation, real-time streaming evaluation

## Claims
1. Hybrid CNN-Transformer models achieve the highest macro-F1 across all three datasets
2. Pure Transformers outperform pure CNNs on multi-lead (PTB-XL, CPSC2018) but not single-lead (MIT-BIH) when dataset is small
3. CNNs offer 3–5× better computational efficiency (FLOPs, latency) than Transformers
4. The performance gap narrows under computational constraints (< 1M parameters)

## Methodology Contract
- 6 architectures (2 CNN, 2 Transformer, 2 Hybrid)
- 3 datasets (MIT-BIH, PTB-XL, CPSC2018)
- Inter-patient evaluation (AAMI standard for MIT-BIH)
- Statistical significance testing (McNemar's, DeLong's)
- Computational profiling (Parameters, FLOPs, Latency, Memory)

## Evidence Requirements
- Each claim must be supported by ≥1 table/figure
- Statistical significance: p < 0.05 for all pairwise claims
- Computational measurements on identical hardware (RTX 3090)
