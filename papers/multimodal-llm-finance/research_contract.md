# Research Contract — FinMM-LLM

## Core Claim
Multi-modal LLM fusion of financial news text and stock price time-series generates incremental information content beyond single-modal approaches, with the value concentrated in high-information-asymmetry periods.

## Binding Commitments

| # | Commitment | Verification Method |
|---|-----------|-------------------|
| 1 | Multi-modal Sharpe > max(Text-only Sharpe, TS-only Sharpe) | Table 2: Main results |
| 2 | FF5 alpha statistically significant (t > 2.0) | Table 5: Fama-MacBeth |
| 3 | Conditional alpha higher in earnings/high-VIX periods | Table 4: Conditional analysis |
| 4 | Placebo test destroys signal (shuffled pairs → insignificant alpha) | Section 4.4 placebo results |
| 5 | Cross-attention weights correlate with information events | Figure 4-5: Attention analysis |

## Scope Boundaries
- **In scope**: S&P 500, 2018-2024, English news, daily granularity
- **Out of scope**: Non-US markets, intraday, small-caps, non-English text

## MVP Status
- Mode: MVP (simulated data, marked with ^S^)
- All numerical results are statistically self-consistent simulations
- Real data required before journal submission
