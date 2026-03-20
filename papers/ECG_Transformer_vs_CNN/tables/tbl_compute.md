: Computational efficiency comparison across all architectures. Latency measured on NVIDIA RTX 3090 (GPU) and Intel Xeon W-2255 (CPU) with batch size 1. ^S^ denotes simulated data. {#tbl-compute tbl-colwidths="[18,13,13,14,14,14,14]"}

| Model | Params (M)^S^ | FLOPs (M)^S^ | GPU Lat. (ms)^S^ | CPU Lat. (ms)^S^ | Memory (MB)^S^ | Throughput (samples/s)^S^ |
|-------|-------------:|-----------:|----------------:|----------------:|-------------:|------------------------:|
| ResNet-1D | 0.52 | 18.4 | 1.8 ± 0.2 | 4.3 ± 0.5 | 12.6 | 2,841 |
| InceptionTime | 1.87 | 76.3 | 3.2 ± 0.3 | 8.7 ± 0.8 | 28.4 | 1,562 |
| ViT-ECG | 3.42 | 142.5 | 8.5 ± 0.6 | 24.1 ± 1.8 | 52.3 | 587 |
| ECG-Transformer | 7.81 | 298.6 | 14.2 ± 0.9 | 41.7 ± 3.2 | 98.7 | 352 |
| CAT-Net | 2.15 | 87.9 | 5.1 ± 0.4 | 13.4 ± 1.2 | 34.2 | 978 |
| CNN-Transformer | 4.63 | 156.2 | 6.8 ± 0.5 | 17.9 ± 1.5 | 62.8 | 735 |
