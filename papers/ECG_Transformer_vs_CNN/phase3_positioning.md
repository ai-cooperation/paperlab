# Research Positioning — ECG Transformer vs CNN Benchmark

## Literature Landscape

### CNN-Dominated Era (2017–2021)

The application of deep learning to ECG arrhythmia classification has been dominated by convolutional neural networks since the landmark work of @Hannun2019, which demonstrated cardiologist-level performance using a 34-layer CNN on single-lead ECG data. Subsequent studies established ResNet and InceptionTime as strong baselines: @Strodthoff2021 benchmarked multiple architectures on PTB-XL and found CNN-based models (particularly ResNet and Inception) consistently outperformed other approaches. @Oh2018 combined CNN with LSTM for variable-length heartbeat classification, while @Khan2023 and @Mathunjwa2022 explored 1D residual networks and recurrence plot representations respectively. This body of work established CNNs as the default architecture, but evaluation protocols varied widely — most studies used intra-patient splits that inflate accuracy due to inter-beat correlation within patients [@DeChazal2004].

### Transformer Emergence (2022–2024)

The introduction of Transformer architectures to ECG analysis followed the success of Vision Transformers [@Dosovitskiy2021] in computer vision. @Meng2022 proposed a lightweight transformer with LightConv Attention, reducing computational cost while maintaining competitive accuracy. @Dong2023 adapted vision transformers with deformable attention for 12-lead ECG classification. @Varghese2023 demonstrated that transformer-based temporal sequence learners capture long-range dependencies that CNNs miss, particularly for arrhythmias involving subtle rhythm irregularities. @Xia2023 blended transformers with denoising autoencoders for robust inter-patient classification. However, most transformer studies benchmarked only against their own baselines, lacking controlled comparisons with state-of-the-art CNNs under identical conditions.

### Hybrid Architectures (2023–2025)

Recent work increasingly combines CNN local feature extraction with transformer global attention. @Islam2024 proposed CAT-Net achieving 99.14% accuracy on MIT-BIH by integrating convolution, channel attention, and transformer encoding. @Li2024 developed a clinical knowledge-inspired dual-view CNN-Transformer mimicking cardiologist diagnostic workflow. @Kim2025 introduced Stockwell transform-based hybrid models that eliminate R-peak detection requirements, while @Alghieth2025 deployed DeepECG-Net on Raspberry Pi with sub-50ms latency. The hybrid trend suggests neither pure CNN nor pure Transformer is optimal, but the precise conditions under which each architecture excels remain uncharacterized due to inconsistent evaluation protocols across studies.

### Deployment Considerations

A parallel thread of research addresses model compression for wearable deployment. @An2024 achieved 1242× model size reduction through knowledge distillation, @Gu2023 implemented a hardware CNN consuming only 1.14mW, and @Makynen2024 used attention-based compression for AF detection. These studies highlight that computational cost — not just accuracy — is critical for clinical adoption, yet most architecture comparison studies omit computational profiling entirely.

## Gap Matrix

| Gap | Description | Existing Work | Our Approach |
|-----|-------------|---------------|-------------|
| **G1: Unfair Comparison** | Studies compare architectures using different preprocessing, splits, and metrics; results are non-comparable. @AnsariReview2023 noted that reported accuracies range from 92% to 99.9% for the same dataset depending on evaluation protocol. | Individual papers use custom pipelines; no standardized benchmark exists for Transformer vs CNN comparison. | Unified benchmarking framework with identical preprocessing (bandpass filter, R-peak segmentation, Z-score normalization), AAMI inter-patient splits, and 7 evaluation metrics for all 6 models. |
| **G2: Single-Dataset Validation** | Most studies validate on MIT-BIH only (48 patients, 1980s data). @Strodthoff2021 showed performance drops significantly on PTB-XL. @Imtiaz2024 demonstrated cross-database degradation. | @Strodthoff2021 benchmarked on PTB-XL but only for CNN models. No study systematically evaluates Transformer vs CNN across MIT-BIH, PTB-XL, AND CPSC2018. | Three-dataset evaluation (MIT-BIH, PTB-XL, CPSC2018) covering single-lead, 12-lead, diverse populations, and different annotation schemes. |
| **G3: Missing Computational Profiling** | Architecture comparisons omit FLOPs, inference latency, and memory footprint. @AnsariSurvey2025 identified this as a critical gap for clinical deployment. | @Alamatsaz2024 and @An2024 profile lightweight models but don't compare against full-scale Transformers. | Complete computational profiling (parameters, FLOPs, GPU/CPU latency, memory) for all 6 architectures, with accuracy-efficiency Pareto frontier analysis. |

## Differentiation Statement

"Unlike previous work that proposes novel architectures and evaluates them against ad hoc baselines under study-specific conditions [@Islam2024; @Dong2023; @Xia2023], our study provides a systematic, controlled benchmark comparing six representative architectures — two pure CNN, two pure Transformer, and two hybrid — across three public datasets under strictly identical experimental conditions, with both classification performance and computational cost analysis, yielding evidence-based architecture selection guidelines for clinical deployment scenarios."

## Contribution Echo (for Introduction)

1. **Methodological**: The first controlled benchmarking framework for CNN vs Transformer vs Hybrid architectures in ECG classification, addressing the reproducibility crisis identified by @AnsariReview2023 and @AnsariSurvey2025.

2. **Empirical**: Cross-dataset evidence (MIT-BIH → PTB-XL → CPSC2018) with statistical significance testing, filling the single-dataset validation gap noted by @Strodthoff2021 and @Imtiaz2024.

3. **Practical**: Architecture selection guidelines mapping clinical deployment constraints (latency, memory, power) to optimal model families, bridging the gap between accuracy-focused research and deployment-focused engineering [@Gu2023; @An2024; @Alamatsaz2024].
