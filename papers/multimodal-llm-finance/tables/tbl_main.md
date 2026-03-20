<!-- tbl-colwidths: [22, 10, 16, 12, 11, 12, 10] -->

| Model | Sharpe | Ann. Alpha (bps) | Alpha *t*-stat | MDD (%) | Hit Rate (%) | Turnover |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| L-M Dictionary | 0.51^S^ | 18^S^ | 1.48^S^ | −28.4^S^ | 50.1^S^ | 0.082^S^ |
| FinBERT (text-only) | 0.85^S^ | 35^S^ | 2.12^S^ | −18.3^S^ | 53.2^S^ | 0.094^S^ |
| PatchTST (TS-only) | 1.10^S^ | 48^S^ | 2.50^S^ | −22.1^S^ | 54.8^S^ | 0.087^S^ |
| StockNet | 0.97^S^ | 41^S^ | 2.30^S^ | −20.8^S^ | 53.9^S^ | 0.091^S^ |
| DeepFusion | 1.18^S^ | 54^S^ | 2.69^S^ | −19.2^S^ | 55.3^S^ | 0.096^S^ |
| MSGCA | 1.31^S^ | 61^S^ | 2.80^S^ | −17.1^S^ | 56.0^S^ | 0.098^S^ |
| **FinMM-LLM (Ours)** | **1.55^S^** | **72^S^** | **3.41^S^** | **−15.0^S^** | **57.1^S^** | **0.103^S^** |

: Main results — portfolio performance on the 2023–2024 test set. Alpha is the annualised Fama–French five-factor alpha expressed in basis points (bps). MDD = maximum drawdown. Hit rate = fraction of monthly long positions with positive excess return. Turnover = average monthly one-way portfolio turnover. {#tbl-main}

**Notes.** ^S^ = simulated value for pre-publication demonstration. All portfolios are long-only, value-weighted, rebalanced monthly. Alpha *t*-statistics are computed using Newey–West standard errors with 3 lags (SE range: 12.2–21.8 bps); *t* = alpha / SE. L-M Dictionary alpha is not statistically significant (*t* < 2.0). Bold entries indicate the best value in each column.
