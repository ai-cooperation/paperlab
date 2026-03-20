<!-- tbl-colwidths: [24, 24, 12, 14, 12] -->

**Panel (a): Text Encoder Ablation** *(TS encoder fixed to PatchTST)*

| Component | Variant | Sharpe | Alpha (bps) | *t*-stat |
|:---|:---|:---:|:---:|:---:|
| Text Encoder | L-M Dictionary | 1.15^S^ | 52^S^ | 2.53^S^ |
| Text Encoder | GPT-Embedding | 1.42^S^ | 65^S^ | 3.10^S^ |
| Text Encoder | **FinBERT** ✓ | **1.55^S^** | **72^S^** | **3.41^S^** |

**Panel (b): TS Encoder Ablation** *(text encoder fixed to FinBERT)*

| Component | Variant | Sharpe | Alpha (bps) | *t*-stat |
|:---|:---|:---:|:---:|:---:|
| TS Encoder | LSTM | 1.28^S^ | 56^S^ | 2.76^S^ |
| TS Encoder | iTransformer | 1.46^S^ | 68^S^ | 3.24^S^ |
| TS Encoder | **PatchTST** ✓ | **1.55^S^** | **72^S^** | **3.41^S^** |

**Panel (c): Fusion Method Ablation** *(both encoders fixed)*

| Component | Variant | Sharpe | Alpha (bps) | *t*-stat |
|:---|:---|:---:|:---:|:---:|
| Fusion | Simple Ensemble | 1.33^S^ | 60^S^ | 2.93^S^ |
| Fusion | Concatenation | 1.44^S^ | 67^S^ | 3.21^S^ |
| Fusion | **Cross-Attention** ✓ | **1.55^S^** | **72^S^** | **3.41^S^** |

: Component ablation analysis. Each panel varies one design axis while holding all others at the chosen configuration (✓). Alpha is the annualised FF5 alpha in basis points; *t*-statistics use Newey–West (3 lags) standard errors. {#tbl-ablation}

**Notes.** ^S^ = simulated value for pre-publication demonstration. Ablation experiments use identical training/testing splits and hyperparameters as the main experiment; only the component architecture is swapped. SE values range 20.3–21.1 bps across all variants.
