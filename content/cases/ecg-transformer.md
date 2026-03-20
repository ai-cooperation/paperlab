---
title: "ECG 心律不整分類：Transformer vs CNN 系統性基準評測"
date: 2026-03-20
draft: false
tags: ["ECG", "Transformer", "CNN", "Arrhythmia", "Benchmark", "Medical AI"]
summary: "以 11-Phase 論文方法學，系統性比較 CNN、Transformer、Hybrid 三大架構在心律不整分類的表現。涵蓋 3 資料集、6 模型、統計檢定與計算效率分析。"
cover:
  image: "/cases/ecg-transformer/fig3_pareto.png"
  alt: "Pareto Analysis"
  hidden: false
ShowToc: true
TocOpen: true
---

## 案例概覽

| 維度 | 評估 |
|------|------|
| **領域** | 醫療 AI — 心電圖分析 × 深度學習 |
| **資料集可得性** | ⭐⭐⭐⭐⭐ 三個公開資料集 (MIT-BIH, PTB-XL, CPSC2018) |
| **方法可行性** | ⭐⭐⭐⭐ 標準深度學習框架，需 GPU 訓練 2-4 天 |
| **研究新穎性** | ⭐⭐⭐⭐ 首個控制實驗 CNN vs Transformer vs Hybrid 三方對比 |
| **發表價值** | ⭐⭐⭐⭐ Q1 期刊可行 (IF 5-8 範圍) |
| **目標期刊** | Expert Systems with Applications (IF 8.5) / Computers in Biology and Medicine (IF 6.3) |

---

## 研究現況概述

深度學習在心電圖 (ECG) 心律不整自動分類已發展近十年，經歷了 **CNN 主導期 (2017–2021)** → **Transformer 引入期 (2022–2024)** → **Hybrid 融合期 (2023–2025)** 的演進。

然而，現有研究各自使用不同的前處理管線、資料切分方式和評估指標，導致**跨研究比較不可靠**，臨床部署缺乏架構選擇的實證依據。

---

## 四個研究缺口

| # | 研究缺口 | 說明 |
|---|---------|------|
| **G1** | 不公平的比較協議 | 現有研究使用不同前處理、切分、指標，CNN 報 98% 和 Transformer 報 97.5% 無法比較 |
| **G2** | 單一資料集驗證 | 多數研究僅用 MIT-BIH（1980 年代、48 位病患），未驗證跨資料集泛化能力 |
| **G3** | 缺少計算成本分析 | FLOPs、推論延遲、記憶體佔用等部署關鍵指標幾乎從未報告 |
| **G4** | 時間壓力 | 2025 已有 2 篇類似定位 arXiv preprint，研究窗口正在縮小 |

---

## 11 Phase 執行摘要

| Phase | 任務 | 狀態 | 產出 |
|-------|------|------|------|
| 1 | 概念確認 | ✅ | RQ + 3 貢獻 + 3 Gap + 預期結果 |
| 2 | 文獻搜集 | ✅ | 39 篇 DOI 三重驗證 (通過率 94.9%) |
| 3 | 研究定位 | ✅ | Gap Matrix + Differentiation Statement |
| 4 | 論文結構 | ✅ | 4 圖 5 表 = 9 個圖表元素 |
| 5 | 實驗設計 | ⏭️ | MVP 模式跳過 |
| 6 | 實驗執行 | ⏭️ | MVP 模式跳過 |
| 7 | 結果分析 | ✅ | 模擬數據（統計自洽，^S^ 標注） |
| 8 | 論文撰寫 | ✅ | ~4,300 字，39/39 引用全到位 |
| 9 | 品質審查 | ✅ | Stage 0+1 通過，0 個 P0 問題 |
| 10 | 投稿準備 | ✅ | Cover Letter + 期刊分析 5 間 |

---

## 論文初稿預覽

### 實驗框架

![Experimental Framework](/cases/ecg-transformer/fig1_framework.png)

*Figure 1: 統一實驗框架 — 3 個 ECG 資料集 → 統一前處理 → 6 個模型架構 → 多維度評估*

### 模型架構對比

![Architecture Comparison](/cases/ecg-transformer/fig2_architectures.png)

*Figure 2: 6 個模型架構 (2 CNN + 2 Transformer + 2 Hybrid) 的結構對比*

### Pareto 效率分析

![Pareto Analysis](/cases/ecg-transformer/fig3_pareto.png)

*Figure 3: 準確率 vs 計算量 Pareto frontier — CNN（藍）高效、Transformer（橘）高準確、Hybrid（綠）最佳平衡*

### Grad-CAM 注意力視覺化

![Grad-CAM](/cases/ecg-transformer/fig4_gradcam.png)

*Figure 4: 三種架構的注意力模式差異 — CNN 聚焦 QRS 波、Transformer 分散於 P-QRS-T、Hybrid 自適應結合*

---

## 模擬結果摘要

### 主要分類結果 (MIT-BIH, 5-class, inter-patient)

| Model | Accuracy | Macro-F1 | GPU Latency | Params |
|-------|:--------:|:--------:|:-----------:|:------:|
| ResNet-1D | 95.83% | 0.879 | 1.8 ms | 0.52M |
| InceptionTime | 96.47% | 0.903 | 3.2 ms | 1.87M |
| ViT-ECG | 96.91% | 0.912 | 8.5 ms | 3.42M |
| ECG-Transformer | 97.32% | 0.928 | 14.2 ms | 7.81M |
| CAT-Net | 97.18% | 0.921 | 5.1 ms | 2.15M |
| **CNN-Transformer** | **98.05%** | **0.946** | **6.8 ms** | **4.63M** |

> *所有數值為模擬數據（^S^），基於文獻預期範圍生成，統計自洽但非真實實驗結果。*

### 核心發現

- **Hybrid > Transformer > CNN** — 在準確率上一致成立
- **CNN > Hybrid > Transformer** — 在計算效率上 CNN 有 3-5× 優勢
- **CNN-Transformer 是 Pareto 最優** — 在準確率與效率的平衡上最佳
- **統計顯著** — CNN-Transformer 顯著優於所有其他模型 (McNemar's test, p < 0.05)

---

## 期刊推薦與競爭態勢

| 期刊 | IF | 策略 |
|------|-----|------|
| **Expert Systems with Applications** | **8.5** | **首選** — 強調 architecture selection decision support |
| Computers in Biology and Medicine | 6.3 | 備選 — scope 完美匹配 |
| IEEE JBHI | 7.7 | 定位為 Strodthoff (2021) 延伸 |
| Biomedical Signal Processing and Control | 5.1 | 穩妥選擇 |
| Scientific Reports | 4.6 | 保底 |

### ⚠️ 競爭態勢警示

> **2025 年已有 2 篇類似定位的 arXiv preprint：**
> - *A Comprehensive Benchmark for ECG Time-Series* (July 2025)
> - *A Systematic Review of ECG Arrhythmia Classification* (March 2025)
>
> **建議：** 首投 ESWA (IF 8.5)，強調「architecture selection decision support」角度。投稿前必須跑完真實實驗（~2-4 天 GPU time）。模擬數據無法投稿任何期刊。

---

## 品質評估與改進空間

本初稿為論文方法學的**流程展示（showcase）**，呈現從概念到初稿的完整過程。

### 目前水準

| 審查階段 | 結果 |
|---------|------|
| Stage 0: 文獻複驗 | ✅ 通過 — 39/39 DOI 有效 |
| Stage 1: MVP Gate | ✅ 通過 — P0: 0 個 |
| Stage 2: Paper Review | ⏳ 待執行（MVP 模式延後） |
| Stage 3: Elite Audit | ⏳ 待執行（MVP 模式延後） |

### 升級到 SCI 等級需要

1. **跑真實實驗** — 所有 ^S^ 模擬數據必須替換為實際訓練結果（~2-4 天 GPU）
2. **生成真實 Grad-CAM** — 從實際模型提取注意力圖
3. **通過完整 Phase 9** — 七維度評分 + Elite Reviewer Audit
4. **開放原始碼** — GitHub repo 支持可重複性

### Reviewer 可能質疑的方向

- 「這是 benchmark paper，沒有 novel method」— 需強化 deployment guideline 貢獻
- 模擬數據需替換為真實結果
- 可加入 cross-dataset transfer learning 實驗
- 2025 已有 2 篇類似 preprint，建議 3 個月內投稿

---

## 論文初稿下載

📄 **[下載 Showcase PDF（15 頁，含浮水印）](/cases/ecg-transformer/paper_draft_v0_showcase.pdf)**

包含：Abstract、Introduction、Related Work、Methodology、Results、Discussion、Conclusion、39 篇參考文獻。

---

> 📧 **想要將此方法學應用到您的研究領域？**
>
> 預約一對一諮詢：**aicooperation.tw@gmail.com**
