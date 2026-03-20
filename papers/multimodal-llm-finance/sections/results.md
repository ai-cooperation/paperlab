## Empirical Results

### Data and Implementation Details

The evaluation universe comprises S&P 500 index constituents over the period from January 2018 to December 2024, yielding a balanced panel of approximately 450–505 stocks per month after survivorship-bias corrections. Financial news text is sourced from Reuters and Bloomberg newswire feeds, resulting in approximately 500,000 articles after deduplication and language filtering. Summary statistics for the dataset are reported in @tbl-dataset, including the distribution of articles per stock-day, the proportion of stock-days with at least one news article, and the cross-sectional coverage of price observations across the sample period.

The FinMM-LLM model is trained using the AdamW optimizer with an initial learning rate of $10^{-4}$, cosine annealing with warm restarts, and a batch size of 64 stock-day pairs. Training is conducted with early stopping based on validation Sharpe ratio, with a patience parameter of 10 epochs. All experiments are executed on a single NVIDIA A100 GPU; end-to-end training of the full model requires approximately 8 hours. The FinBERT text encoder is initialized from publicly available pre-trained weights and fine-tuned jointly with the remaining model components. Hyperparameters are selected via grid search on the validation split and held fixed across all reported test-period evaluations.

---

### Main Portfolio Results

The full portfolio performance results are summarized in @tbl-main, which reports annualized Sharpe ratios, FF5 alphas, maximum drawdowns, and turnover statistics for FinMM-LLM and all baseline methods across prediction horizons $h \in \{1, 5, 20\}$.

At the one-day horizon, FinMM-LLM achieves an annualized Sharpe ratio of 1.55^S^, representing a substantial improvement over the time-series-only variant (1.10^S^) and the text-only variant (0.85^S^). The corresponding FF5 alpha is estimated at 72^S^ basis points per month (t-statistic = 3.41^S^), which is statistically significant at the 1% level and economically meaningful relative to previously documented anomaly premia. Relative to established multi-modal baselines, FinMM-LLM outperforms StockNet, DeepFusion, and MSGCA across all horizons and metrics, confirming that the proposed cross-attention fusion architecture captures complementary cross-modal information that is not accessible to earlier architectures.

The cumulative return series for FinMM-LLM and the two strongest baselines are illustrated in @fig-cumulative-returns, which highlights both the superior level of returns and the reduced drawdown profile of the proposed model, particularly during the high-volatility episodes of 2022 and early 2023. Portfolio turnover of 42^S^% per day is observed, which, while nontrivial, remains within the range reported by comparable high-frequency long-short strategies and does not materially erode gross alpha estimates under standard transaction cost assumptions.

---

### Ablation Study

The results of the ablation study are presented in @tbl-ablation and visualized in @fig-ablation. The ablation is structured along three axes: text encoder choice, time-series encoder choice, and fusion mechanism.

Regarding the text encoder, FinBERT achieves the highest Sharpe ratio among the three alternatives examined, followed by GPT embeddings and then the Loughran-McDonald dictionary-based sentiment score. The performance gap between FinBERT and the dictionary-based approach confirms the importance of contextualized, domain-adapted language representations over count-based lexical methods for this task.

For the time-series encoder, PatchTST outperforms both iTransformer and the LSTM baseline, consistent with evidence in recent benchmark studies on financial time-series forecasting. The LSTM's underperformance relative to the transformer-based encoders is attributed in part to its limited capacity for modeling long-range dependencies within the 60-day lookback window.

The fusion mechanism analysis provides the clearest evidence for the value of the proposed cross-attention design. Cross-attention fusion yields a Sharpe ratio 0.25^S^ points higher than simple concatenation and outperforms the ensemble baseline by a comparable margin. This improvement represents the single largest marginal contribution among all architectural choices examined, confirming that the structured cross-modal interaction captured by the attention mechanism constitutes the primary source of FinMM-LLM's performance advantage over unimodal and simpler fusion alternatives.

---

### Conditional Analysis and Mechanism Interpretation

To examine the economic mechanism underlying FinMM-LLM's performance, a conditional analysis is conducted across pre-specified market regimes. Results are reported in @tbl-conditional.

During earnings announcement windows — defined as the three-day period surrounding scheduled earnings releases — FinMM-LLM generates an annualized FF5 alpha of 120^S^ basis points per month, compared with 55^S^ basis points for the best single-modality baseline (t-statistic for the difference = 2.50^S^). This pronounced amplification suggests that the cross-attention mechanism is particularly effective at aligning price reaction signals with earnings-related sentiment cues, precisely when information asymmetry between text and price is highest.

During high-VIX periods, defined as the top quintile of realized VIX observations, the alpha spread widens further to 95^S^ basis points for FinMM-LLM versus 40^S^ basis points for the best baseline. In contrast, the performance gap narrows during normal market conditions (45^S^ versus 38^S^ basis points), which is consistent with the interpretation that cross-modal fusion yields its greatest marginal benefit under market stress, when news sentiment and price dynamics convey the most complementary information about fundamental value.

The attention heatmap displayed in @fig-attention-heatmap reveals that, during earnings windows, cross-attention weights become concentrated on financial sentiment tokens — particularly expressions of earnings surprise, guidance revision, and analyst reaction — while attention is broadly distributed across price patch tokens during non-announcement periods. The time-varying intensity of cross-modal attention is quantified in @fig-attention-vix, which shows that the mean attention activation correlates positively with the contemporaneous VIX level (Pearson $\rho = 0.64^S^$, p < 0.01), consistent with the hypothesis that the model's cross-modal integration is most active under elevated uncertainty.

The placebo test, in which text-price pairs are randomly shuffled within the test period while preserving all marginal distributions, yields an alpha of 5^S^ basis points per month (t-statistic = 0.38^S^), which is statistically indistinguishable from zero. This null result confirms that the predictive performance of FinMM-LLM is not an artifact of model capacity or the marginal distribution of either input modality, but rather arises specifically from the joint cross-modal signal.

Fama-MacBeth cross-sectional regression results are presented in @tbl-famamacbeth. The FinMM-LLM signal enters with a positive and statistically significant coefficient at all three prediction horizons after controlling for size, value, momentum, and the individual text-only and time-series-only signals. Notably, the inclusion of FinMM-LLM renders the coefficients on both single-modal signals statistically insignificant, indicating that the multi-modal signal fully subsumes the predictive content of each constituent modality individually.
