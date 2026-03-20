---
title: "AI × ECG 心律不整 — Transformer vs CNN 架構系統性比較"
description: "首個控制條件一致的 ECG 心律不整分類架構基準測試：6 種模型（2 CNN + 2 Transformer + 2 Hybrid）跨三資料集比較，含完整計算效率分析"
date: 2026-03-20
tags: ["案例演練", "ECG", "心律不整", "深度學習", "Transformer", "CNN", "生醫工程"]
keywords: ["ECG arrhythmia classification", "Transformer vs CNN benchmark", "深度學習 ECG", "Computers in Biology and Medicine", "心律不整偵測"]
summary: "現有 Transformer vs CNN 比較研究因前處理/切分/指標不一，結果無法互比。本案例用 11 Phase 方法學，建構首個控制條件一致的六架構 ECG 基準，跨 MIT-BIH / PTB-XL / CPSC2018 三資料集，並加入計算效率分析供臨床部署決策。"
---

<div style="margin-bottom: 1.5rem;">
<span style="display:inline-block; background:#F0FDF4; color:#16A34A; padding:0.3rem 0.8rem; border-radius:100px; font-weight:600; margin-right:0.5rem;">工程</span>
<span style="display:inline-block; background:#EFF6FF; color:#2563EB; padding:0.3rem 0.8rem; border-radius:100px; font-weight:600; margin-right:0.5rem;">醫療生技</span>
<span style="display:inline-block; background:#FEF3C7; color:#D97706; padding:0.3rem 0.8rem; border-radius:100px; font-weight:600;">ECG分類 × 深度學習架構比較</span>
</div>

## 案例概覽

| 項目 | 內容 |
|------|------|
| 領域大類 | 工程 / 醫療生技 |
| 領域子類 | 生醫信號處理 × 深度學習架構比較 |
| 資料集 | MIT-BIH (109,446 beats) + PTB-XL (21,837 records) + CPSC2018 (6,877 records) |
| 可行性 | ★★★★★ |
| 新穎性 | ★★★★☆ |
| 發表價值 | ★★★★★ |

---

## 研究現況：ECG 深度學習架構的三世代演進

ECG 心律不整自動分類的深度學習方法歷經三個階段：

**第一世代（2017–2021）：CNN 主導**
- Hannun et al. (2019) 用 34 層 CNN 達到心臟科醫師級準確率（Nature Medicine）
- ResNet-1D、InceptionTime 確立 CNN 基準地位
- 多數研究使用患者內（intra-patient）切分，準確率虛高（>99%）

**第二世代（2022–2023）：Transformer 登場**
- Vision Transformer 移植至 ECG 一維信號
- Meng et al. (2022)、Dong et al. (2023)、Varghese et al. (2023) 等陸續提出 ECG Transformer
- 各自對比自己的基準，無統一實驗條件

**第三世代（2024–至今）：Hybrid 主流 + 邊緣部署**
- CAT-Net、CNN-Transformer 等 Hybrid 架構成為新基準
- 可穿戴設備部署需求興起，但計算效率分析嚴重缺失
- **不同研究間結果無法互比，缺乏公平受控的基準測試**

### 關鍵發現

> 現有文獻報告同一資料集（MIT-BIH）的準確率從 92% 到 99.9% 不等，差異來源是前處理流程與資料切分策略，而非模型本身。
> **公平受控的 Transformer vs CNN vs Hybrid 基準至今不存在。**

---

## 三個研究缺口

### 缺口一：不公平比較協議 — 結果無法互比

現有研究使用不同的前處理流程（濾波器設定、R-peak 分割方式、正規化策略）和資料切分方式（患者內 vs 患者間）。AnsariReview (2023) 指出，報告準確率 >99% 的研究幾乎全部使用患者內切分，而臨床意義更高的患者間（inter-patient）評估下準確率普遍下滑 5–10%。

### 缺口二：單一資料集驗證 — 跨資料集泛化未知

超過 80% 的 ECG 分類研究僅使用 MIT-BIH（48 位患者，1980 年代數據）。Strodthoff et al. (2021) 顯示模型在 PTB-XL 上性能顯著下降；Imtiaz et al. (2024) 展示了跨資料庫的嚴重退化現象。無研究系統性地在 MIT-BIH、PTB-XL 和 CPSC2018 三個資料集上同時比較 Transformer vs CNN。

### 缺口三：計算效率分析缺失 — 臨床部署決策無依據

架構比較研究普遍略去 FLOPs、推論延遲、記憶體佔用等計算指標。AnsariSurvey (2025) 將此列為臨床部署的關鍵缺口——可穿戴設備、床邊監護儀的部署可行性完全取決於延遲與記憶體，但現有基準無法提供選型依據。

---

## 12 Phase 執行摘要

| Phase | 執行內容 | 狀態 |
|-------|---------|------|
| 1 概念確認 | 確認三假說（H1–H3）、六模型架構、三資料集、目標期刊 CoBM | ✅ |
| 2 文獻搜集 | 收集 42 篇候選文獻，CrossRef + S2 三重驗證，39 篇通過（92.9%） | ✅ |
| 3 研究定位 | 確認三缺口，建立差異化陳述，Hybrid CNN-Transformer 為核心貢獻 | ✅ |
| 4 論文架構 | IMRaD 骨架，4 圖 + 5 表 = 9 個圖表，研究合約確認 | ✅ |
| 5 實驗設計 | MVP 模式跳過 | ⏭ |
| 6 實驗執行 | MVP 模式跳過 | ⏭ |
| 7 結果分析 | 5 張結果表（主表 3-Panel + 消融 + 計算效率），模擬數值填充 | ✅ |
| 8 論文撰寫 | 全文 7 節完成，39/39 引用鍵嵌入，無孤兒引用 | ✅ |
| 9 品質審查 | Stage 0（文獻驗證）+ Stage 1（MVP Gate）通過，P0=0，Stage 2-3 待後續 | ✅ |
| 10 投稿準備 | Cover Letter + Submission Checklist 完成 | ✅ |
| 11 審稿回覆 | 按需啟動 | ⏳ |

---

## 主要結果預覽（模擬數據）

CNN-Transformer（Hybrid）在三個資料集上均取得最佳表現：

| 資料集 | 最佳模型 | Macro-F1 | vs 最佳純 CNN | vs 最佳純 Transformer |
|-------|---------|---------|-------------|---------------------|
| MIT-BIH (5-class) | CNN-Transformer | **0.946** | +4.8% (InceptionTime 0.903) | +2.0% (ECG-Transformer 0.928) |
| PTB-XL (5-superclass) | CNN-Transformer | **0.901** | +5.6% (InceptionTime 0.853) | +2.2% (ECG-Transformer 0.882) |
| CPSC2018 (9-class) | CNN-Transformer | **0.867** | +5.4% (InceptionTime 0.823) | +1.9% (ECG-Transformer 0.851) |

計算效率對比（延遲 × 準確率 Pareto）：
- **最快**：ResNet-1D（GPU 1.8ms，0.52M params，F1=0.879）← 最適合可穿戴設備
- **最佳**：CNN-Transformer（GPU 6.8ms，4.63M params，F1=0.946）← 雲端/醫院
- **最慢**：ECG-Transformer（GPU 14.2ms，7.81M params，F1=0.928）← 不建議邊緣部署

---

<!-- GATE PROMPT -->
<div id="gate-prompt" style="background:#F8FAFC; border:2px solid #E2E8F0; border-radius:12px; padding:2rem; text-align:center; margin:2rem 0;">
  <p style="font-size:1.1rem; font-weight:600; color:#1E293B; margin-bottom:0.5rem;">🔒 以下內容需要登入查看</p>
  <p style="color:#64748B; margin-bottom:1.5rem;">Google 登入後可查看完整缺口分析、研究題目、期刊推薦，並下載論文初稿 PDF</p>
  <button onclick="paperLabAuth.login()" style="background:#2563EB; color:white; border:none; padding:0.75rem 2rem; border-radius:8px; font-size:1rem; font-weight:600; cursor:pointer;">
    Google 登入 免費查看
  </button>
</div>

<!-- GATED CONTENT -->
<div id="gated-content" style="display:none;">

---

## 完整缺口分析

### 缺口一深析：不公平比較的量化影響

**為何理論上重要：** 若基準不一致，任何「Transformer 優於 CNN」或「CNN 更適合邊緣部署」的結論都無法被信賴。這直接影響臨床系統的架構選型決策——錯誤選擇可能導致部署後準確率比預期低 5-10%，在心律不整偵測中意味著漏診風險。

**文獻支撐：**
- Ansari et al. (2023) 系統性回顧指出 ECG 分類研究缺乏統一評估協議
- Islam et al. (2024) CAT-Net 在患者內切分達 99.14%，但患者間切分下未報告
- DeChazal et al. (2004) AAMI 標準明確要求患者間評估，但多數研究忽略

**我們的回應：** 所有 6 個模型使用完全一致的前處理管道（帶通濾波 0.5-40Hz + R-peak 偵測 + Z-score 正規化）、AAMI 標準患者間切分、7 個統一評估指標。

### 缺口二深析：MIT-BIH 偏誤的系統性問題

**為何理論上重要：** MIT-BIH 只有 48 位患者（1980 年代），人口多樣性極低，類別極不平衡（N 類 >90%）。模型在 MIT-BIH 的高性能可能無法泛化到現代臨床場景，Strodthoff et al. 已驗證此點。

**文獻支撐：**
- Strodthoff et al. (2021) 在 PTB-XL 的系統性基準顯示跨資料集性能差距顯著
- Imtiaz et al. (2024) 展示跨資料庫泛化退化，提出 domain adaptation 方案
- Wagner et al. (2020) PTB-XL 包含 18,885 位患者，遠比 MIT-BIH 具代表性

**我們的回應：** 三資料集評估（MIT-BIH + PTB-XL + CPSC2018）覆蓋單導程/12 導程、不同人口組成、不同標注方案，量化跨資料集泛化差距。

### 缺口三深析：計算成本分析的臨床必要性

**為何理論上重要：** 心律不整監測需要在可穿戴設備（<10ms 延遲、<100MB 記憶體）、床邊監護儀（即時處理）、雲端系統（批次分析）等不同場景部署。沒有計算效率數據，架構選型無從依據。

**文獻支撐：**
- Gu et al. (2023) 設計消耗 1.14mW 的硬體 CNN，強調功耗是可穿戴的核心約束
- An et al. (2024) 透過知識蒸餾實現 1242× 模型壓縮，但未與 Transformer 系統比較
- AnsariSurvey (2025) 識別計算效率分析缺失為現有文獻的最關鍵空白

**我們的回應：** 完整計算分析（參數量、FLOPs、GPU/CPU 延遲、記憶體佔用、吞吐量），並提供 Pareto 效率邊界分析，直接映射到三種部署場景的選型建議。

---

## 可行研究題目

### 題目一（本案例）：系統性基準（可行性最高）

**完整標題：** Benchmarking CNN, Transformer, and Hybrid Architectures for ECG Arrhythmia Classification: A Controlled Multi-Dataset Study with Computational Profiling

**核心問題：** 在嚴格控制的實驗條件下，三類架構在分類性能與計算效率上各有何優勢？什麼部署情境下哪種架構最優？

**方法框架：** 統一前處理管道 + 6 架構 + 3 資料集 + 7 指標 + 計算 Pareto 分析

**貢獻點：**
1. 首個嚴格受控的 Transformer vs CNN vs Hybrid ECG 基準框架
2. 三資料集跨域泛化證據（MIT-BIH + PTB-XL + CPSC2018）
3. 精確性-效率 Pareto 邊界 + 臨床部署場景選型指南

### 題目二：可解釋性（深化延伸）

**完整標題：** Attention Mechanisms in ECG Arrhythmia Classification: What Do Transformers Actually Learn Compared to CNNs?

**核心問題：** Transformer 的注意力機制是否真的在捕捉心電生理學上有意義的時序模式？

**方法框架：** Grad-CAM（CNN）+ Attention Rollout（Transformer）+ 心臟科醫師驗證

### 題目三：邊緣部署（應用導向）

**完整標題：** Efficient ECG Arrhythmia Detection for Wearable Devices: Neural Architecture Search Beyond Transformer-CNN Trade-offs

**核心問題：** 在 <1M 參數、<5ms 延遲的硬約束下，NAS 能找到超越手工設計 Hybrid 的架構嗎？

**方法框架：** Neural Architecture Search + 知識蒸餾 + Raspberry Pi 實地驗證

---

## 題目比較矩陣

| 面向 | 題目一（基準） | 題目二（可解釋性） | 題目三（邊緣部署） |
|------|-------------|----------------|----------------|
| 難度 | ★★★☆☆ | ★★★★☆ | ★★★★★ |
| 新穎性 | ★★★★☆ | ★★★★★ | ★★★★☆ |
| 出稿速度 | 快（6 個月） | 中（9 個月） | 慢（12 個月+） |
| 需要真實實驗 | ✅（必須） | ✅（必須） | ✅（必須） |
| MVP 可展示度 | ★★★★★ | ★★★☆☆ | ★★★☆☆ |

---

## 期刊推薦

| 期刊 | IF | SJR | 適合題目 | 備注 |
|------|----|-----|---------|------|
| Computers in Biology and Medicine | 6.3 | Q1 | 題目一 | 目標期刊，ECG 論文活躍 |
| Biomedical Signal Processing and Control | 5.1 | Q1 | 題目一、二 | BSPC，高 ECG 論文接受率 |
| IEEE Journal of Biomedical and Health Informatics | 7.7 | Q1 | 題目一 | 計算效率分析契合度高 |
| Artificial Intelligence in Medicine | 7.0 | Q1 | 題目二 | 可解釋 AI 方向首選 |
| Expert Systems with Applications | 7.5 | Q1 | 題目三 | NAS + 應用部署 |
| Sensors (MDPI) | 3.9 | Q2 | 題目三 | 邊緣部署，開放取用 |
| IEEE Transactions on Biomedical Engineering | 4.6 | Q1 | 題目一、二 | 硬核方法論，審查嚴格 |
| PLOS ONE | 3.7 | Q1 | 題目一 | 重現性導向，快速通道 |

---

## 執行路徑時間表

| 月份 | 里程碑 |
|------|-------|
| 第 1 個月 | 環境建置：PhysioNet 資料集下載 + 前處理管道實作 |
| 第 2–3 個月 | 6 個模型訓練（ResNet-1D / InceptionTime / ViT-ECG / ECG-Transformer / CAT-Net / CNN-Transformer） |
| 第 4 個月 | 三資料集評估 + 統計顯著性檢定（McNemar + DeLong） |
| 第 4.5 個月 | 計算效率測量（FLOPs / 延遲 / 記憶體）+ Pareto 分析 |
| 第 5 個月 | 論文修訂（將模擬數據替換為真實實驗數據） |
| 第 6 個月 | 投稿 Computers in Biology and Medicine |

---

## DOI 驗證摘要

| 指標 | 數值 |
|------|------|
| 候選文獻總數 | 42 篇 |
| CrossRef 驗證通過 | 40/42（95.2%） |
| Semantic Scholar 驗證通過 | 37/42（88.1%） |
| 雙重驗證通過 | 37/39（94.9%） |
| 最終採用文獻 | 39 篇（排除 3 篇主題不符） |
| Abstract 覆蓋率 | 33/39（84.6%） |
| 近 5 年文獻佔比 | 31/39（79.5%） |

---

## 品質評估與改進空間

本初稿為論文方法學的流程展示（showcase），呈現從概念到初稿的完整 11 Phase 過程。

### 目前水準
- MVP Gate 審查（Stage 1）：✅ 通過，P0 = 0 個，P2 = 1 個（命名一致性，已修正）
- Stage 2（Paper Review）：延後至真實實驗完成後執行
- Stage 3（Elite Reviewer Audit）：延後至真實實驗完成後執行

### 升級到 SCI 等級需要

1. **真實實驗數據**：目前所有結果表格均為模擬數值（標示 ^S^）。投稿前必須在 MIT-BIH、PTB-XL、CPSC2018 上實際訓練並評估 6 個模型。
2. **圖形生成**：框架圖、訓練曲線、Pareto 圖、混淆矩陣目前為規格說明，需生成實際 PNG/SVG。
3. **統計顯著性驗證**：McNemar 檢定和 DeLong AUC 比較需要真實模型輸出，模擬數據無法通過 Stage 2 統計嚴謹性審查。

### 可加強的空間

- **Reviewer 可能質疑**：6 個模型的超參數是否對齊（都有做超參數調優還是用預設值）？
- **Reviewer 可能質疑**：MIT-BIH 類別極不平衡（N 類 >90%），Macro-F1 是否受影響？需要報告各類 F1（per-class F1）。
- **可深化的方向**：跨院系統（不同廠商心電圖機器的域移問題）、對罕見心律不整的分析（Macro-F1 可能被常見類拉高）
- **計算效率**：延遲測量應包含不同 batch size，並報告在 ARM Cortex-M 或 Raspberry Pi 上的實際測量（而非外推）

---

## 下載論文初稿 PDF

<div style="background:#EFF6FF; border:1px solid #BFDBFE; border-radius:8px; padding:1.5rem; margin:1.5rem 0;">
  <p style="font-weight:700; color:#1E40AF; margin-bottom:0.5rem;">📄 論文初稿 PDF（含方法學展示標記）</p>
  <p style="color:#3B82F6; font-size:0.9rem; margin-bottom:1rem;">SHOWCASE DRAFT — 非投稿版本 | 模擬數據標示 ^S^ | 框架完整，實驗數據待補</p>
  <button onclick="downloadCasePDF('ecg-transformer')" style="background:#2563EB; color:white; border:none; padding:0.6rem 1.5rem; border-radius:6px; font-weight:600; cursor:pointer;">
    下載 PDF
  </button>
</div>

</div>
<!-- END GATED CONTENT -->

---

## 想將這套方法用在你的領域？

<div style="background:#F0FDF4; border:1px solid #BBF7D0; border-radius:8px; padding:1.5rem; margin:1.5rem 0;">
  <p style="font-weight:700; color:#15803D; margin-bottom:0.5rem;">🎯 客製化諮詢</p>
  <ul style="color:#166534; margin-bottom:1rem;">
    <li>心電圖 / 醫療影像 / 生醫信號 × 深度學習架構選型</li>
    <li>論文方法學一對一指導（從 Research Gap 到 PDF）</li>
    <li>11 Phase 系統套用到你的研究主題</li>
  </ul>
  <a href="mailto:aicooperation.tw@gmail.com" style="background:#16A34A; color:white; padding:0.6rem 1.5rem; border-radius:6px; font-weight:600; text-decoration:none;">
    預約諮詢
  </a>
</div>

<script>
async function downloadCasePDF(caseId) {
  const auth = window.paperLabAuth;
  if (!auth) return;
  const user = firebase.auth().currentUser;
  if (!user) {
    await auth.login();
    return;
  }
  try {
    await firebase.firestore().collection('downloads').add({
      uid: user.uid,
      email: user.email,
      case_id: caseId,
      timestamp: firebase.firestore.FieldValue.serverTimestamp(),
    });
  } catch (e) { console.warn('download log failed', e); }
  window.open('/cases/' + caseId + '/paper_draft_v0.pdf', '_blank');
}
</script>
