<!-- tbl-colwidths: [18, 10, 9, 10, 9, 10, 9] -->

| Variable | 1-Day Coeff | 1-Day *t* | 5-Day Coeff | 5-Day *t* | 20-Day Coeff | 20-Day *t* |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| MM Signal | 0.0148^S^ | 3.42^S^\*\* | 0.0089^S^ | 2.91^S^\*\* | 0.0051^S^ | 2.14^S^\* |
| Text Signal | 0.0032^S^ | 1.18^S^ | 0.0021^S^ | 0.87^S^ | 0.0009^S^ | 0.41^S^ |
| TS Signal | 0.0041^S^ | 1.34^S^ | 0.0027^S^ | 0.98^S^ | 0.0011^S^ | 0.53^S^ |
| Size (log ME) | −0.0073^S^ | −2.81^S^\*\* | −0.0058^S^ | −2.44^S^\* | −0.0041^S^ | −1.92^S^† |
| B/M | 0.0062^S^ | 2.23^S^\* | 0.0048^S^ | 1.98^S^\* | 0.0031^S^ | 1.42^S^ |
| Mom | 0.0054^S^ | 2.07^S^\* | 0.0039^S^ | 1.71^S^† | −0.0021^S^ | −0.89^S^ |
| Intercept | 0.0021^S^ | 1.12^S^ | 0.0018^S^ | 0.98^S^ | 0.0015^S^ | 0.81^S^ |
| | | | | | | |
| Avg. *R*² | 0.032^S^ | | 0.041^S^ | | 0.048^S^ | |
| *N* (avg. stocks) | 490^S^ | | 490^S^ | | 490^S^ | |

: Fama–MacBeth cross-sectional regressions predicting future stock returns. Dependent variable is the cumulative excess return over 1-, 5-, or 20-trading-day horizons. MM Signal, Text Signal, and TS Signal are the standardised ranking signals from the full FinMM-LLM model and its unimodal ablations, respectively. Size = log market equity; B/M = book-to-market ratio; Mom = 12-1 month momentum. All signals and controls are standardised to zero mean, unit standard deviation within each month. {#tbl-famamacbeth}

**Notes.** ^S^ = simulated value for pre-publication demonstration. Coefficients are time-series means of monthly cross-sectional OLS gamma estimates (Fama and MacBeth, 1973); *t*-statistics use Shanken (1992) correction. T = 24 monthly cross-sections; avg. *N* = 490 stocks per month (S&P 500 universe). \*\*significant at 1%; \*significant at 5%; †marginal at 10%. Text Signal and TS Signal lose statistical significance at all horizons when MM Signal is included, consistent with MM Signal subsuming the predictive content of unimodal signals. MM Signal coefficient decays monotonically from 1-day to 20-day horizon, consistent with gradual price discovery.
