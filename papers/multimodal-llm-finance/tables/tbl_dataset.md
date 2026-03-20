<!-- tbl-colwidths: [38, 31, 31] -->

| Statistic | Training (2018–2022) | Testing (2023–2024) |
|:---|---:|---:|
| # Stocks (S&P 500 constituents) | 478^S^ | 493^S^ |
| # Stock-days | 599,412^S^ | 247,486^S^ |
| # News articles (total) | 387,520^S^ | 162,480^S^ |
| Avg. articles per stock-day | 2.42^S^ | 2.51^S^ |
| Vocabulary size (BPE tokens) | 64,312^S^ | — |
| Avg. article length (tokens) | 186.4^S^ | 191.7^S^ |
| Trading days | 1,254^S^ | 502^S^ |
| Date range | 2018-01-02 – 2022-12-30^S^ | 2023-01-03 – 2024-12-31^S^ |

: Dataset statistics for the FinMM-LLM study. News articles sourced from Reuters and Bloomberg financial wire services. Vocabulary built on training corpus only; BPE tokeniser applied to both splits. {#tbl-dataset}

**Notes.** ^S^ = simulated value for pre-publication demonstration. Stock universe based on S&P 500 index membership with survivorship-bias correction; firms with ≥ 250 trading days per year and non-zero news coverage retained.
