<!-- tbl-colwidths: [28, 9, 18, 18, 13, 10] -->

| Regime | *N* (days) | MM Alpha (bps) | Best Single (bps) | Difference | *t*-stat |
|:---|:---:|:---:|:---:|:---:|:---:|
| Earnings Window (±5d) | 80^S^ | 118^S^ | 72^S^ | +46^S^ | 2.50^S^\* |
| FOMC Window (±2d) | 80^S^ | 95^S^ | 61^S^ | +34^S^ | 1.98^S^† |
| High VIX (>25) | 75^S^ | 83^S^ | 58^S^ | +25^S^ | 1.49^S^ |
| Normal Periods | 167^S^ | 68^S^ | 46^S^ | +22^S^ | 1.37^S^ |
| Low VIX (<15) | 100^S^ | 42^S^ | 34^S^ | +8^S^ | 0.52^S^ |

: Conditional portfolio performance by market regime. MM Alpha = annualised FF5 alpha of FinMM-LLM. Best Single = the higher of FinBERT (text-only) or PatchTST (TS-only) alpha in each regime. Difference = MM Alpha − Best Single; *t*-statistic tests whether this difference exceeds zero (Newey–West SE, 3 lags). {#tbl-conditional}

**Notes.** ^S^ = simulated value for pre-publication demonstration. \*significant at 5%; †marginal at 10%. Regimes defined on NYSE trading calendar over the 2023–2024 test period (502 total trading days); High VIX and Low VIX defined on the CBOE Volatility Index (VIX). Earnings Window covers the five trading days before and after each company's quarterly earnings announcement date. SE values range 15.4–18.4 bps across regimes, reflecting shorter subsample periods at extreme regimes.
