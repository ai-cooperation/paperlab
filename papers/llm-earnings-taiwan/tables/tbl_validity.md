<!-- tbl-colwidths: [30, 15, 18, 12, 18] -->

**Table 2** | Inter-rater reliability and baseline comparison across earnings management detection methods. Expert annotation sample: *n* = 120 firm-years, stratified by industry × EM quintile. Cohen's κ and Pearson *r* computed against forensic accountant expert panel scores. Two-tailed *t*-tests; significance stars: \*\*\* *p* < 0.001, \*\* *p* < 0.01, \* *p* < 0.05.

| Method | Cohen's κ | Pearson *r* (vs. Expert) | RMSE | AUC (Restatement) |
|---|---|---|---|---|
| **Proposed LLM Pipeline (EMI)** | **0.760^S^**\*\*\* | **0.681^S^**\*\*\* | **4.21^S^** | **0.758^S^** |
| Modified Jones Accruals | 0.412^S^\*\* | 0.381^S^\*\* | 9.73^S^ | 0.621^S^ |
| Loughran–McDonald Tone | 0.481^S^\*\* | 0.442^S^\*\* | 8.14^S^ | 0.653^S^ |
| TF-IDF Boilerplate Score | 0.388^S^\* | 0.351^S^\*\* | 10.28^S^ | 0.598^S^ |

*Notes:* Cohen's κ measures agreement between each method's EM classification and expert forensic accountant labels (5-point ordinal scale collapsed to 3-category: low / medium / high EM). Pearson *r* is the correlation between continuous EMI scores and expert ratings. RMSE is the root mean squared error on the 0–100 EMI scale relative to expert scores (lower = better). AUC is the area under the ROC curve from a logistic regression predicting financial restatement within three years, using each method's score as the sole predictor (*n* = 2,856^S^ firm-years). The proposed LLM pipeline significantly outperforms all three baselines on all four metrics. Baseline methods are operationalised as follows: Modified Jones Accruals (Dechow et al., 1995) scaled by lagged total assets; Loughran–McDonald Tone = (positive − negative word count) / total words using the 2018 master dictionary; TF-IDF Boilerplate Score = mean cosine similarity to industry-year template constructed from bottom-quartile EMI reports.

*^S^ Values marked [S] are simulated based on expected results confirmed by authors prior to data collection; they will be replaced with experimental results.*
