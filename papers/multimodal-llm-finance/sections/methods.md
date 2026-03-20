## Methodology

### Problem Formulation

A formal prediction task is defined over a universe of stocks indexed by $i$, observed across trading days indexed by $t$. For each stock-day pair $(i, t)$, two input modalities are made available: a text corpus $\mathcal{T}_{i,t}$ comprising financial news articles published within the trading day, and a historical price series $\mathbf{P}_{i,t-L:t} \in \mathbb{R}^{L \times 5}$ representing $L$ consecutive trading days of open, high, low, close, and volume (OHLCV) observations. The objective is to predict the forward return $r_{i,t+h}$ at prediction horizons $h \in \{1, 5, 20\}$ trading days, corresponding respectively to daily, weekly, and monthly investment signals.

The joint investment signal is formulated as

$$s_{i,t} = f\!\left(\mathcal{T}_{i,t},\, \mathbf{P}_{i,t-L:t};\, \theta\right),$$

where $f(\cdot;\theta)$ denotes the proposed FinMM-LLM framework parameterized by $\theta$. Stocks are ranked by $s_{i,t}$ at each rebalancing date, and a long-short decile portfolio is constructed from the top and bottom deciles. This formulation enables systematic comparison across horizons and facilitates factor-adjusted evaluation against standard asset pricing benchmarks.

---

### Text Encoder

Financial news text is encoded using FinBERT [@Yang2020], a domain-adapted variant of BERT [@Devlin2019] pre-trained on a large corpus of financial communication. For each stock-day pair, the title and leading 512 tokens of each retrieved news article are supplied as input, a truncation strategy that preserves the highest-density information while remaining within the model's context window.

Let $N_t$ denote the number of articles associated with stock $i$ on day $t$. The encoder produces a set of article-level embeddings

$$\mathbf{e}^{(k)}_{i,t} \in \mathbb{R}^{d_t}, \quad k = 1, \ldots, N_t,$$

where $d_t = 768$ is the hidden dimension of FinBERT. Because $N_t$ varies across stock-day pairs, a learnable attention pooling mechanism is employed to aggregate the article set into a fixed-size representation. Specifically, scalar attention weights $\alpha^{(k)}$ are computed via a single linear projection followed by a softmax normalization, and the stock-day text representation is obtained as the weighted sum $\mathbf{v}_{i,t} = \sum_{k} \alpha^{(k)} \mathbf{e}^{(k)}_{i,t}$. The resulting matrix $\mathbf{T}_{i,t} \in \mathbb{R}^{N_t \times d_t}$ retains article-level granularity for subsequent cross-modal attention.

Two alternatives are examined in the ablation study: (i) embeddings extracted from a general-purpose GPT encoder, and (ii) document-level sentiment scores derived from the Loughran-McDonald financial lexicon [@LoughranMcDonald2011], which provides a non-parametric baseline. FinBERT is selected as the primary encoder owing to its superior in-domain calibration and its demonstrated advantage in financial sentiment classification tasks.

---

### Time-Series Encoder

Historical price dynamics are encoded using the PatchTST architecture [@Nie2023], a transformer-based time-series model that processes multivariate sequences through non-overlapping temporal patches. The OHLCV price series $\mathbf{P}_{i,t-L:t} \in \mathbb{R}^{L \times 5}$ is constructed with a lookback window of $L = 60$ trading days, approximately three calendar months of observations.

Each variate channel is divided into non-overlapping patches of length $P = 5$ days, yielding $N_s = \lfloor L / P \rfloor = 12$ patch tokens per channel. A channel-independent projection maps each patch to a $d_s = 128$-dimensional embedding, producing a patch token sequence $\mathbf{S}_{i,t} \in \mathbb{R}^{N_s \times d_s}$. Sinusoidal positional encodings are added to $\mathbf{S}_{i,t}$ to preserve temporal ordering across patches, a property that is critical for capturing trend and momentum signals.

The patch-based design was chosen over token-per-timestep alternatives because it reduces sequence length by a factor of $P$, mitigating the quadratic cost of self-attention while capturing local temporal structure within each patch. Two alternatives are included in the ablation: a bidirectional LSTM [@Hochreiter1997] that processes the flattened OHLCV sequence recurrently, and iTransformer [@Liu2024], a recently proposed variant that applies attention across variate dimensions rather than the time dimension. PatchTST is selected as the primary backbone based on preliminary validation performance and its established superiority on multi-step financial forecasting benchmarks.

---

### Cross-Modal Attention Fusion

The cross-modal fusion module constitutes the central methodological contribution of FinMM-LLM. Rather than combining text and price representations through simple concatenation or element-wise operations, a bidirectional cross-attention mechanism is introduced to enable each modality to selectively query information from the other. This design is motivated by the observation that the informativeness of price movements is often contingent on the sentiment context provided by contemporaneous news, and vice versa.

Formally, let $\mathbf{T} \in \mathbb{R}^{N_t \times d_t}$ and $\mathbf{S} \in \mathbb{R}^{N_s \times d_s}$ denote the text and price token sequences, respectively, projected to a common dimension $d_k$ via learned linear maps $W_Q, W_K, W_V$. The text-to-price cross-attention is defined as

$$\mathrm{CrossAttn}(\mathbf{T}, \mathbf{S}) = \mathrm{softmax}\!\left(\frac{\mathbf{T} W_Q \left(\mathbf{S} W_K\right)^\top}{\sqrt{d_k}}\right) \mathbf{S} W_V,$$

where $\mathbf{T}$ serves as the query source and $\mathbf{S}$ provides keys and values. An analogous price-to-text operation is computed symmetrically, with roles reversed. The resulting cross-attended representations from both directions are concatenated and passed through a layer normalization.

A gated fusion layer then combines the cross-modal output $\mathbf{C}$ with the original price representation via a data-dependent gate:

$$\mathbf{F} = \sigma(W_g \mathbf{C}) \odot \mathbf{C} + \left(1 - \sigma(W_g \mathbf{C})\right) \odot \mathbf{S},$$

where $\sigma(\cdot)$ is the sigmoid function and $\odot$ denotes element-wise multiplication. This formulation allows the model to adaptively suppress the cross-modal component when text signals are uninformative, reverting to a near-unimodal price representation.

The architecture draws conceptual inspiration from CLIP-style contrastive alignment [@Radford2021] but is substantially adapted for sequential, heterogeneous financial data in which the two modalities differ in sequence length, token semantics, and temporal granularity. Connections to the broader multi-modal learning literature are discussed in @Baltrusaitis2019, while the foundational self-attention mechanism follows @Vaswani2017. An important interpretability benefit of the cross-attention design is that the attention weight matrix $\boldsymbol{\alpha} \in \mathbb{R}^{N_t \times N_s}$ can be inspected post-hoc to identify which text tokens most strongly activate which price patches, providing a granular view of cross-modal interaction that is exploited in the conditional analysis of Section 4.4 [@Zong2025].

---

### Evaluation Framework

A long-short decile portfolio strategy is employed as the primary evaluation vehicle. At each rebalancing date, stocks are sorted by the predicted signal $s_{i,t}$ and assigned to ten equal-weight deciles; the portfolio goes long on the top decile and short on the bottom decile, with daily rebalancing. Performance is summarized through four metrics: annualized Sharpe ratio, annualized factor-adjusted alpha, maximum drawdown (MDD), and portfolio turnover.

Factor adjustment follows the Fama-French five-factor model (FF5; @Fama2015), in which portfolio excess returns are regressed on the market, size, value, profitability, and investment factors. Fama-MacBeth cross-sectional regressions [@Fama1993] are further employed to assess whether the FinMM-LLM signal retains predictive power for individual stock returns after controlling for standard risk factors and previously documented anomalies.

An ablation study is conducted across three dimensions. First, the modality contribution is isolated by evaluating text-only, time-series-only, and full multi-modal variants. Second, the text encoder is varied among FinBERT, GPT embeddings, and the Loughran-McDonald dictionary. Third, the fusion mechanism is compared against concatenation and simple ensemble baselines. Conditional analyses are performed across three market regimes: earnings announcement windows (three days surrounding scheduled releases), high-VIX periods (top quintile of realized VIX), and FOMC meeting weeks. A placebo test is included in which text-price pairings are randomly shuffled within the test period, thereby destroying any true cross-modal signal while preserving marginal distributions.

The dataset is split temporally: the model is trained on 2018–2022, validated on 2022–2023, and evaluated out-of-sample on 2023–2024. This strict temporal separation prevents look-ahead bias and ensures that reported results reflect genuine out-of-sample generalization.
