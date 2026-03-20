: Ablation study on CNN-Transformer (proposed hybrid) using MIT-BIH dataset. ^S^ denotes simulated data. {#tbl-ablation tbl-colwidths="[30,14,14,14,14,14]"}

| Configuration | Accuracy (%)^S^ | Macro-F1^S^ | Params (M)^S^ | FLOPs (M)^S^ | Δ F1^S^ |
|---------------|----------------:|------------:|--------------:|------------:|--------:|
| **Full model (CNN-Transformer)** | **98.05** | **0.946** | **4.63** | **156.2** | — |
| − Transformer encoder (CNN only) | 96.12 | 0.886 | 1.24 | 42.8 | −0.060 |
| − CNN backbone (Transformer only) | 96.78 | 0.908 | 3.89 | 138.4 | −0.038 |
| − Multi-head attention (single head) | 97.41 | 0.928 | 4.01 | 132.6 | −0.018 |
| − Positional encoding | 97.23 | 0.921 | 4.58 | 154.8 | −0.025 |
| − Data augmentation | 97.14 | 0.918 | 4.63 | 156.2 | −0.028 |
| − SMOTE balancing | 96.89 | 0.905 | 4.63 | 156.2 | −0.041 |
| Patch size 50 → 25 | 97.92 | 0.941 | 5.12 | 178.4 | −0.005 |
| Patch size 50 → 100 | 97.68 | 0.934 | 3.98 | 128.6 | −0.012 |
| Transformer layers 4 → 2 | 97.56 | 0.931 | 2.87 | 98.4 | −0.015 |
| Transformer layers 4 → 8 | 98.11 | 0.947 | 8.24 | 286.8 | +0.001 |
