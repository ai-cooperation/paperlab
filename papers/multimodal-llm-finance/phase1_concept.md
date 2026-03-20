# Research Concept — Multi-modal LLM for Financial Decision Intelligence

## Research Question

**Does multi-modal information fusion — combining financial news text and stock price time-series through large language models — reveal incremental information content beyond traditional single-modal approaches in investment decision-making?**

Sub-questions:
1. How do textual (news sentiment, event narratives) and temporal (price patterns, volume dynamics) information channels interact in financial decision intelligence?
2. Does cross-modal attention between text and time-series capture complementary signals that neither modality alone can identify?
3. Under what market conditions (high volatility, earnings announcements, macro shocks) does multi-modal fusion yield the greatest incremental value?

## Core Hypotheses

- **H1 (Information Complementarity)**: Multi-modal LLM fusion of news text and price time-series produces investment signals with significantly higher Sharpe ratio than either single-modal approach (text-only or time-series-only).
- **H2 (Cross-Modal Attention Mechanism)**: The cross-attention weights between text tokens and time-series patches reveal economically meaningful patterns — e.g., higher text-to-price attention during earnings announcements and macro events.
- **H3 (Conditional Superiority)**: The incremental value of multi-modal fusion is concentrated in high-information-asymmetry periods (pre-earnings, M&A rumors, policy announcements), consistent with information economics theory.

## Three Contributions

1. **Methodological Contribution — Cross-Modal Fusion Architecture**
   We propose FinMM-LLM (Financial Multi-Modal LLM), a novel architecture that aligns financial news embeddings with stock price time-series patches through a cross-modal attention mechanism, enabling joint reasoning over heterogeneous financial data modalities. Unlike existing approaches that concatenate features or use simple ensembles, our architecture learns modality-specific and cross-modal representations simultaneously.

2. **Empirical Contribution — Incremental Information Content**
   Using a comprehensive dataset of U.S. equity markets (S&P 500 constituents, 2018–2024), we provide large-scale empirical evidence that multi-modal fusion captures information content incremental to both (a) traditional NLP sentiment scores (FinBERT, Loughran-McDonald dictionary) and (b) technical time-series models (LSTM, Transformer). We demonstrate economically significant portfolio alpha (annualized excess return) after controlling for Fama-French five factors.

3. **Economic Mechanism Contribution — Information Channel Decomposition**
   We decompose the model's cross-attention weights to identify when and why text-price interaction matters most. This reveals that the incremental value of multi-modal fusion is driven by information asymmetry events — providing micro-level evidence for theories of gradual information diffusion (Hong & Stein, 1999) and investor attention (Da, Engelberg & Gao, 2011).

## Three Limitations in Existing Literature

1. **Single-Modality Silos**: Existing financial NLP studies (e.g., FinBERT sentiment, GPT-based news analysis) and time-series models (LSTM, Temporal Fusion Transformer) operate in isolation. No rigorous study examines their information complementarity through a unified multi-modal framework with economic identification.

2. **Prediction Without Economic Mechanism**: Current LLM-for-finance papers focus on prediction accuracy (F1, RMSE) without explaining *why* the model works — lacking the causal mechanism analysis required by top finance journals. The "black box" problem limits both academic contribution and practical adoption.

3. **Lack of Conditional Analysis**: Prior work reports unconditional average performance. No study systematically examines under what market regimes (volatility states, information events, market microstructure conditions) multi-modal integration provides incremental value, missing the conditional heterogeneity central to finance theory.

## Target Journal

- **Journal**: Journal of Financial Econometrics (JFEC) — Machine Learning Special Issue
- **Publisher**: Oxford Academic
- **Submission Deadline**: September 1, 2026
- **Scope fit**: JFEC ML special issue explicitly seeks research "strengthening the growing link between ML methodologies and economic analysis." Our multi-modal fusion architecture with cross-attention interpretability and Fama-MacBeth identification directly addresses this call. The econometric rigor (factor-adjusted alpha, cross-sectional regressions, placebo tests) fits JFEC's methodological standards.
- **Backup targets**:
  - Management Science (cross-domain ML + economics)
  - Journal of Financial and Quantitative Analysis

## Methodology Overview (MVP)

### Data
- **Text**: Financial news articles from major wire services (Reuters, Bloomberg) for S&P 500 companies, 2018–2024
- **Time-Series**: Daily OHLCV (Open, High, Low, Close, Volume) price data + intraday features
- **Labels**: Forward returns at 1-day, 5-day, 20-day horizons; portfolio construction signals
- **Events**: Earnings announcement dates, FOMC meetings, M&A filings (for conditional analysis)

### Model Architecture — FinMM-LLM
```
┌─────────────────────────────────────────────────────────┐
│                    FinMM-LLM Framework                   │
├──────────────────┬──────────────────────────────────────┤
│  Text Encoder    │  Time-Series Encoder                  │
│  (FinBERT/LLM)   │  (Patch-TST / Temporal Transformer)  │
│  News → T_emb    │  OHLCV → S_emb                       │
├──────────────────┴──────────────────────────────────────┤
│              Cross-Modal Attention Layer                  │
│         T_emb ⊗ S_emb → Fused Representation            │
│         (Interpretable attention weights)                 │
├─────────────────────────────────────────────────────────┤
│              Decision Head                               │
│   Signal → Portfolio Construction → Risk-Adjusted Return │
└─────────────────────────────────────────────────────────┘
```

### Evaluation Strategy
- **Financial metrics**: Sharpe ratio, annualized alpha (FF5), maximum drawdown, turnover
- **Information content tests**: Fama-MacBeth regressions of signals on future returns
- **Ablation**: Text-only vs. Time-series-only vs. Multi-modal
- **Conditional analysis**: Performance by volatility regime, event type, information asymmetry proxy

### Identification Strategy (Critical for JFE)
- **Fama-MacBeth cross-sectional regressions**: Signal predicts returns after controlling for known factors
- **Event study**: Multi-modal fusion alpha concentrated around information events (earnings, FOMC)
- **Placebo tests**: Shuffled text-price pairs destroy signal → confirms cross-modal learning
- **Out-of-sample & out-of-period**: Train on 2018–2022, test on 2023–2024

## Expected Results (MVP — for simulated data generation)

| Metric | Text-Only | TS-Only | Multi-Modal | Improvement |
|--------|-----------|---------|-------------|-------------|
| Annualized Sharpe | 0.85 | 1.10 | 1.55 | +41% vs best single |
| FF5 Alpha (bps/month) | 35 | 48 | 72 | +50% vs best single |
| Max Drawdown | -18% | -22% | -15% | Better risk control |
| Hit Rate (daily) | 53.2% | 54.8% | 57.1% | +2.3pp |

### Conditional Analysis (Expected)
| Market Regime | Multi-Modal Alpha (bps/month) | Single-Modal Best |
|---------------|-------------------------------|-------------------|
| Earnings window (±5 days) | 120 | 55 |
| High VIX (>25) | 95 | 40 |
| Normal periods | 45 | 38 |
| Low VIX (<15) | 30 | 28 |

*These expected results will guide simulated data generation in Phase 7.*
