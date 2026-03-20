# Introduction

Financial markets are shaped by the continuous flow of information across heterogeneous channels.
At the most fundamental level, two complementary streams govern price discovery: textual
information—encompassing news articles, earnings call transcripts, and regulatory filings—and
quantitative time-series data, including prices, volumes, and technical indicators. The pioneering
work of @Tetlock2007 demonstrated that the pessimism embedded in financial media exerts
measurable downward pressure on equity prices, while @Da2011 showed that investor attention,
proxied by internet search volume, predicts short-horizon return reversals consistent with
sentiment-driven demand. At the same time, the empirical asset pricing literature, exemplified by
@Gu2020, has documented that machine learning methods applied to structured market data yield
economically large risk premia. The recent revolution in large language models (LLMs), surveyed
by @Gentzkow2019 as part of the broader "text as data" paradigm, has further opened the
possibility of processing financial discourse at unprecedented scale and semantic depth. Yet
despite the clear complementarity between these two information channels, the overwhelming
majority of existing models treat them independently—leaving substantial predictive information
and economic insight on the table.

Three fundamental gaps characterize the current state of the literature. First, text-based and
time-series-based approaches have evolved along largely parallel tracks with minimal integration.
On the textual side, @LopezLiraTang2023 and @ChenKellyXiu2023 have demonstrated that LLM-derived
sentiment scores carry substantial cross-sectional predictive power for stock returns; on the
quantitative side, @Nie2023 and @Liu2024 have advanced the architecture of Transformer-based
forecasters for time-series data. However, these two lines of inquiry are conducted in isolation,
and the question of whether text and price signals provide genuinely incremental information—or
merely replicate one another—remains unresolved. Second, the existing LLM finance literature
focuses predominantly on predictive accuracy without grounding findings in economic mechanism.
Studies such as @KirtacGermano2024 and @Guo2024 report impressive return forecasts but offer
little insight into *why* language models capture return variation—whether through fundamental
information, investor attention, or liquidity dynamics. This absence of economic identification
limits the theoretical interpretation and practical credibility of LLM-based trading strategies.
Third, no existing multi-modal framework systematically examines how the joint predictive power
of text and price data varies across market regimes. The work of @Zong2025 and @DeepFusion2024
demonstrates the feasibility of multi-modal fusion for stock prediction but does not condition
on volatility states or macroeconomic cycles, obscuring the circumstances under which each
modality dominates and leaving asset managers without actionable guidance for regime-dependent
allocation.

This paper introduces **FinMM-LLM**, a multi-modal large language model architecture designed
to address all three gaps simultaneously. The contributions of this work are threefold. First, a
novel cross-modal attention architecture is proposed in which a language encoder and a patch-based
time-series encoder are aligned through a shared latent space, with cross-attention heads that
dynamically weight each modality as a function of the input context. This architecture builds on
the general multi-modal learning framework of @Baltrusaitis2019 and extends it to the specific
demands of financial decision intelligence. Second, large-scale empirical evidence is provided
that textual and time-series signals carry *incremental* predictive information: using a
comprehensive sample of S&P 500 constituents over seven years, the multi-modal portfolio
generates a statistically and economically significant alpha against the @Fama2015 five-factor
model, indicating that cross-modal integration is not subsumed by known risk factors. Third, a
cross-modal attention decomposition analysis is performed to interpret the learned representations
through the lens of the information diffusion theory of @HongStein1999, showing that attention
weights assigned to the textual channel spike precisely in the windows surrounding analyst
revisions and earnings announcements—consistent with the mechanism of gradual information
diffusion posited by @GlostenMilgrom1985. Together, these contributions advance both the
engineering frontier of multi-modal AI and the economic understanding of how heterogeneous
information is priced in equity markets.

The remainder of this paper is organized as follows. The following section surveys the related
literature across three strands: financial text mining, machine learning for asset pricing, and
multi-modal learning with time-series Transformers. The model architecture and training procedure
are then described, followed by the data construction and empirical design. Main predictive
performance results are subsequently presented, with portfolio-level and factor-model-based
evaluation. The attention decomposition analysis and regime-conditional tests are reported next.
The final section concludes and identifies directions for future research.
