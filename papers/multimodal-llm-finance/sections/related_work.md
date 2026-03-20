# Related Work

## Financial Text Mining: From Dictionaries to Large Language Models

The systematic extraction of information from financial text has a long history in the empirical
finance and NLP literatures. Early dictionary-based approaches operationalized sentiment by
counting words drawn from curated lexicons. @Tetlock2007 provided seminal evidence that
the fraction of pessimistic language in financial news columns predicts market returns and
trading volume. @Tetlock2008 extended this framework to firm-level news and showed that the
share of negative words from general-purpose dictionaries forecasts accounting earnings and
stock returns, though their predictive power decays rapidly. A critical methodological advance
came from @LoughranMcDonald2011, who demonstrated that Harvard's General Inquirer lexicon
systematically misclassifies financial terminology—labeling "liability" and "tax" as negative
despite their neutral connotations in financial discourse—and proposed a finance-specific word
list that substantially improves return predictability in 10-K filings. The arrival of deep
learning prompted a fundamental rethinking of textual representation. @Ding2015 proposed
extracting structured events from news and encoding them via a neural tensor network, demonstrating
that event-driven features carry incremental predictive content beyond dictionary sentiment scores.
Domain-adapted language models then emerged as the dominant paradigm: @Araci2019 fine-tuned
BERT on a financial communication corpus to produce FinBERT, and @Yang2020 scaled this approach
to 4.9 billion tokens spanning corporate reports, earnings calls, and analyst reports. The most
recent wave has harnessed general-purpose LLMs: @Wu2023 trained BloombergGPT on a proprietary
363-billion-token financial archive, while @Yang2023 introduced the open-source FinGPT framework
with reinforcement learning from human feedback. In the cross-sectional return prediction domain,
@LopezLiraTang2023 documented that ChatGPT sentiment scores derived from news headlines
significantly predict next-day abnormal returns, and @ChenKellyXiu2023 showed that LLM-based
signals generate Sharpe-ratio improvements that are incremental to both price-based and
characteristic-based strategies. @Guo2024 further investigated fine-tuning strategies for
return prediction from newsflow, comparing encoder-only and decoder-only architectures.
Despite this remarkable progress, a common limitation of all text-based approaches is that
textual signals are processed in isolation, without joint modeling alongside the quantitative
price dynamics that evolve contemporaneously with news flow.

## Machine Learning for Asset Pricing

The application of machine learning methods to the canonical asset pricing problem—measuring
and forecasting risk premia—was systematically benchmarked by @Gu2020, who documented that
neural networks and gradient-boosted trees applied to a large panel of firm characteristics
nearly double the out-of-sample Sharpe ratio relative to leading regression-based approaches.
The dimensionality reduction perspective was formalized by @Kelly2019, who showed that when
factor loadings are modeled as functions of observable characteristics, a unified framework
nests both factor models and characteristic-based pricing models. The interface between textual
information and cross-sectional returns was examined by @KeKellyXiu2019, who introduced a
supervised text-mining method yielding sentiment scores that predict individual stock returns
and earnings surprises, outperforming commercial sentiment vendors. @Gentzkow2019 provided
the methodological foundation for treating text as structured economic data, surveying a broad
class of approaches including bag-of-words, topic models, and word embeddings. A distinct and
visually oriented branch of the literature was advanced by @Jiang2023, who applied convolutional
neural networks to images of stock price charts and demonstrated that chart-based signals
generate significant out-of-sample return predictability with gradient-based economic
interpretation. Despite these advances, the prevailing approach in the machine learning asset
pricing literature remains anchored to a single modality—either quantitative characteristics,
text, or visual price representations—or, when multiple signals are combined, relies on simple
feature concatenation rather than principled cross-modal alignment. This limitation restricts
the capacity of existing models to exploit the information complementarity that economic theory
predicts should exist between fundamental news and price dynamics.

## Multi-Modal Learning and Time-Series Transformers

The theoretical foundation for integrating heterogeneous information streams is provided by the
multi-modal machine learning framework of @Baltrusaitis2019, who identified five core challenges
in multi-modal systems—representation, translation, alignment, fusion, and co-learning—and argued
that joint modeling consistently outperforms late fusion of unimodal systems. The Transformer
architecture introduced by @Vaswani2017 has become the backbone of both modalities considered
in this paper: large language models derive their text comprehension capabilities from
scaled self-attention, and the time-series domain has been reshaped by a succession of
Transformer variants. @Zhou2021 proposed Informer with ProbSparse self-attention for
long-horizon forecasting; @Wu2021 introduced Autoformer with decomposition-based
auto-correlation; @Lim2021 developed the Temporal Fusion Transformer for interpretable
multi-horizon forecasting with explicit variable selection; and patch-based representations
were advanced by @Nie2023, who showed that a time series is worth 64 words—treating
subseries as tokens dramatically improves long-range forecasting. @Liu2024 further refined
the Transformer's role in time-series modeling through inverted attention across variate
dimensions. The vision-language alignment paradigm demonstrated by @Radford2021 in CLIP
established a blueprint for grounding representations across fundamentally different signal
types via contrastive pre-training. The multi-modal financial prediction literature has grown
rapidly in response: @Xu2018 proposed StockNet, a generative model that jointly processes
tweets and historical price movements; @DeepFusion2024 combined a fine-tuned BERT branch
with an LSTM-based price branch for stock prediction; @Ye2024 fused historical prices with
news embeddings through an information-theoretic fusion objective; and @Zong2025 introduced
a gated cross-attention mechanism that fuses indicator sequences, textual news, and relational
graphs, reporting 8–32% improvements over unimodal baselines. Despite this growing body of
work, existing multi-modal finance models share two critical limitations: they provide no
economic identification mechanism that would allow the learned representations to be
interpreted within established theories of information diffusion or adverse selection, and
they do not conduct regime-conditional analysis that would reveal when and why each modality
contributes to return predictability. The present paper occupies the upper-right quadrant of
a two-dimensional space defined by (i) multi-modal integration versus single-modality and
(ii) economic interpretability versus black-box prediction—a position currently unoccupied
by any existing work—and thus addresses both limitations simultaneously through cross-modal
attention decomposition and regime-stratified evaluation.
