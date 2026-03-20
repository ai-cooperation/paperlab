# Research Positioning — Multi-modal LLM for Financial Decision Intelligence

## Literature Landscape

### Stream 1: Financial Text Mining and Sentiment (11 papers)

The use of textual data for predicting financial outcomes has evolved through three generations. The **dictionary-based era** began with @Tetlock2007 demonstrating that media pessimism predicts downward price pressure, followed by @Tetlock2008 showing that negative word fractions forecast earnings and returns. @LoughranMcDonald2011 refined this approach by developing a finance-specific sentiment lexicon that outperforms general-purpose dictionaries. The **supervised NLP era** emerged with @Ding2015 applying neural networks to structured event representations from news, and @Xu2018 jointly modeling tweets and historical prices via the StockNet architecture. The **LLM era** has seen rapid adoption: @Araci2019 and @Yang2020 adapted BERT for financial sentiment (FinBERT), @Wu2023 trained a 50B-parameter domain-specific LLM (BloombergGPT), and @Yang2023 introduced the open-source FinGPT framework. Most recently, @LopezLiraTang2023 provided direct evidence that ChatGPT sentiment scores predict next-day returns, while @KirtacGermano2024 achieved a Sharpe ratio of 3.05 using LLM-based sentiment trading. @ChenKellyXiu2023 demonstrated that LLM embeddings from financial news generate economically significant cross-sectional return predictability.

### Stream 2: Machine Learning for Asset Pricing (6 papers)

The integration of machine learning into asset pricing has been formalized by @Gu2020, who showed that neural networks approximately double the performance of leading regression-based strategies for cross-sectional return prediction. @Kelly2019 provided the theoretical foundation through Instrumented PCA, demonstrating that firm characteristics serve as latent factor loadings. @KeKellyXiu2019 extended this to text data, proposing supervised sentiment extraction that outperforms commercial sentiment vendors. @Jiang2023 applied CNNs to raw price chart images, establishing that learned visual representations outperform hand-crafted technical indicators — a key precedent for multi-modal approaches. The evaluation framework centers on @Fama1993 three-factor and @Fama2015 five-factor models for measuring risk-adjusted alpha.

### Stream 3: Time-Series Transformers and Multi-Modal Learning (12 papers)

The Transformer architecture (@Vaswani2017) has spawned a family of time-series forecasting models: @Zhou2021 introduced ProbSparse attention for long-horizon efficiency, @Wu2021 embedded trend-seasonal decomposition, @Lim2021 combined interpretable attention with multi-horizon forecasting, @Nie2023 proposed patch-based tokenization (PatchTST), and @Liu2024 demonstrated that inverted attention over variates captures multivariate correlations. These models represent the state-of-the-art for the price time-series encoder. For cross-modal learning, @Radford2021 (CLIP) established contrastive pre-training as the dominant paradigm for aligning heterogeneous modalities, and @Baltrusaitis2019 provided the canonical taxonomy of five multi-modal challenges. In multi-modal finance specifically, @DeepFusion2024 combined BERT with LSTM, @Ye2024 fused stock prices with news embeddings, and @Zong2025 proposed gated cross-attention for trimodal fusion.

### Stream 4: Information Economics Theory (4 papers)

The theoretical foundations rest on @HongStein1999's model of gradual information diffusion (explaining why news-based signals predict returns), @Da2011's investor attention framework (establishing demand-driven price pressure from attention shocks), and @GlostenMilgrom1985's information asymmetry model (linking informed trading to price discovery). These theories provide the economic mechanisms that our cross-modal attention decomposition aims to empirically validate.

## Gap Matrix

| Gap | Description | Existing Work | Limitation | Our Approach |
|-----|-------------|---------------|------------|-------------|
| **G1: Single-Modality Silos** | Text-based and time-series models operate independently | FinBERT sentiment [@Yang2020], PatchTST [@Nie2023], Gu et al. ML [@Gu2020] | No unified framework jointly optimizes both modalities with economic identification | Cross-modal attention architecture (FinMM-LLM) with Fama-MacBeth validation |
| **G2: Prediction Without Mechanism** | LLM-for-finance papers maximize accuracy without explaining *why* | ChatGPT predictions [@LopezLiraTang2023], LLM sentiment trading [@KirtacGermano2024] | Black-box signals lack economic interpretation; insufficient for econometrics journals | Attention weight decomposition reveals when/why text-price interaction matters |
| **G3: Unconditional Performance** | Prior work reports average performance across all periods | StockNet [@Xu2018], DeepFusion [@DeepFusion2024], MSGCA [@Zong2025] | No systematic conditional analysis by market regime, event type, or information asymmetry | Conditional analysis across volatility regimes, earnings windows, FOMC events |

## Differentiation Statement

> "Unlike previous work that either processes financial text in isolation from price dynamics [@LopezLiraTang2023; @ChenKellyXiu2023] or combines modalities without economic identification [@Zong2025; @DeepFusion2024], our study proposes FinMM-LLM — a cross-modal attention architecture that not only achieves superior risk-adjusted returns but also decomposes the attention mechanism to reveal when and why multi-modal integration matters. Through Fama-MacBeth regressions, event studies, and placebo tests, we provide causal evidence that the incremental value of text-price fusion is concentrated in high-information-asymmetry periods, offering micro-level empirical support for theories of gradual information diffusion [@HongStein1999] and investor attention [@Da2011]."

## Contribution Echo (for Introduction)

| Contribution | Literature Support | Differentiation |
|-------------|-------------------|-----------------|
| **C1: Cross-Modal Fusion Architecture** | Extends @Baltrusaitis2019 taxonomy to finance; advances beyond @Xu2018 StockNet and @Zong2025 MSGCA | First to use LLM-grade text encoders (not BERT-level) with Transformer time-series encoders in a unified cross-attention framework |
| **C2: Incremental Information Content** | Builds on @Gu2020 ML asset pricing and @KeKellyXiu2019 text-based returns | Multi-modal signals are incremental to both text-only and TS-only after FF5 adjustment; larger sample (S&P 500, 7 years) than prior multi-modal studies |
| **C3: Information Channel Decomposition** | Empirically tests @HongStein1999 and @Da2011 theories | Cross-attention weights provide a new lens to measure text-price information interaction at the token/patch level |

## Positioning Map

```
                    Economic Interpretation
                    High ↑
                         │
     Tetlock2007 ●       │       ● Our Paper (FinMM-LLM)
     Gu2020 ●            │      ↗
     KeKellyXiu2019 ●    │    ↗
                         │  ↗
     Fama1993 ●          │↗         ● Jiang2023
    ─────────────────────┼──────────────────────────→
    Single-Modal         │                Multi-Modal
                         │
     LopezLira2023 ●     │       ● Zong2025 (MSGCA)
     KirtacGermano2024 ● │       ● DeepFusion2024
     ChenKellyXiu2023 ●  │       ● Xu2018 (StockNet)
                         │
                    Low  ↓
```

Our paper occupies the upper-right quadrant: **multi-modal + high economic interpretation** — a position currently vacant in the literature.
