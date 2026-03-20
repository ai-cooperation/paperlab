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

現有研究使用不同的前處理流程和資料切分方式。報告準確率 >99% 的研究幾乎全部使用患者內切分，而臨床意義更高的患者間（inter-patient）評估下準確率普遍下滑 5–10%。

### 缺口二：單一資料集驗證 — 跨資料集泛化未知

超過 80% 的研究僅用 MIT-BIH（48 位患者，1980 年代數據）。無研究系統性地在 MIT-BIH、PTB-XL 和 CPSC2018 三個資料集上同時比較 Transformer vs CNN。

### 缺口三：計算效率分析缺失 — 臨床部署決策無依據

架構比較研究普遍略去 FLOPs、推論延遲、記憶體佔用等計算指標——可穿戴設備的部署可行性完全取決於延遲與記憶體，但現有基準無法提供選型依據。

---

## 11 Phase 執行摘要

| Phase | 執行內容 | 狀態 |
|-------|---------|------|
| 1 概念確認 | 確認三假說（H1–H3）、六模型架構、三資料集 | ✅ |
| 2 文獻搜集 | 收集 42 篇候選，CrossRef + S2 三重驗證，39 篇通過（92.9%） | ✅ |
| 3 研究定位 | 確認三缺口，建立差異化陳述 | ✅ |
| 4 論文架構 | IMRaD 骨架，4 圖 + 5 表 = 9 個圖表 | ✅ |
| 5 實驗設計 | MVP 模式跳過 | ⏭ |
| 6 實驗執行 | MVP 模式跳過 | ⏭ |
| 7 結果分析 | 5 張結果表（主表 3-Panel + 消融 + 計算效率），模擬數值 | ✅ |
| 8 論文撰寫 | 全文 7 節完成，39/39 引用鍵嵌入 | ✅ |
| 9 品質審查 | Stage 0 + Stage 1 通過，P0=0 | ✅ |
| 10 投稿準備 | Cover Letter + Submission Checklist | ✅ |
| 11 審稿回覆 | 按需啟動 | ⏳ |

---

<!-- ===== 以下為登入可看的內容 ===== -->

<div id="gated-content" style="display:none;">

## 完整缺口分析

### 缺口一深析：不公平比較的量化影響

**為何理論上重要：** 若基準不一致，任何「Transformer 優於 CNN」或「CNN 更適合邊緣部署」的結論都無法被信賴。錯誤選擇可能導致部署後準確率比預期低 5-10%，在心律不整偵測中意味著漏診風險。

**文獻支撐：**
- Ansari et al. (2023) 系統性回顧指出 ECG 分類研究缺乏統一評估協議
- Islam et al. (2024) CAT-Net 在患者內切分達 99.14%，但患者間切分下未報告
- DeChazal et al. (2004) AAMI 標準明確要求患者間評估，但多數研究忽略

**我們的回應：** 所有 6 個模型使用完全一致的前處理管道（帶通濾波 0.5-45Hz + R-peak 偵測 + Z-score 正規化）、AAMI 標準患者間切分、7 個統一評估指標。

### 缺口二深析：MIT-BIH 偏誤的系統性問題

**為何理論上重要：** MIT-BIH 只有 48 位患者（1980 年代），人口多樣性極低，類別極不平衡（N 類 >90%）。模型在 MIT-BIH 的高性能可能無法泛化到現代臨床場景。

**文獻支撐：**
- Strodthoff et al. (2021) 在 PTB-XL 的系統性基準顯示跨資料集性能差距顯著
- Imtiaz et al. (2024) 展示跨資料庫泛化退化
- Wagner et al. (2020) PTB-XL 包含 18,885 位患者，遠比 MIT-BIH 具代表性

**我們的回應：** 三資料集評估（MIT-BIH + PTB-XL + CPSC2018）覆蓋單導程/12 導程、不同人口組成、不同標注方案。

### 缺口三深析：計算成本分析的臨床必要性

**為何理論上重要：** 心律不整監測需在可穿戴設備（<10ms 延遲、<100MB 記憶體）、床邊監護儀、雲端系統等不同場景部署。

**文獻支撐：**
- Gu et al. (2023) 設計消耗 1.14mW 的硬體 CNN，強調功耗是可穿戴的核心約束
- An et al. (2024) 透過知識蒸餾實現 1242× 模型壓縮
- AnsariSurvey (2025) 識別計算效率分析缺失為現有文獻的最關鍵空白

**我們的回應：** 完整計算分析 + Pareto 效率邊界分析，直接映射到三種部署場景的選型建議。

---

## 可行研究題目

### 題目一（本案例）：系統性基準（可行性最高）

**完整標題：** Transformer, CNN, or Both? A Systematic Benchmark for ECG Arrhythmia Classification Across Architectures, Datasets, and Deployment Constraints

**核心問題：** 在嚴格控制的實驗條件下，三類架構在分類性能與計算效率上各有何優勢？

**方法框架：** 統一前處理管道 + 6 架構 + 3 資料集 + 7 指標 + 計算 Pareto 分析

**貢獻點：**
1. 首個嚴格受控的 Transformer vs CNN vs Hybrid ECG 基準框架
2. 三資料集跨域泛化證據
3. 精確性-效率 Pareto 邊界 + 臨床部署場景選型指南

### 題目二：可解釋性（深化延伸）

**完整標題：** Attention Mechanisms in ECG Arrhythmia Classification: What Do Transformers Actually Learn Compared to CNNs?

### 題目三：邊緣部署（應用導向）

**完整標題：** Efficient ECG Arrhythmia Detection for Wearable Devices: Neural Architecture Search Beyond Transformer-CNN Trade-offs

---

## 題目比較矩陣

| 面向 | 題目一（基準） | 題目二（可解釋性） | 題目三（邊緣部署） |
|------|-------------|----------------|----------------|
| 難度 | ★★★☆☆ | ★★★★☆ | ★★★★★ |
| 新穎性 | ★★★★☆ | ★★★★★ | ★★★★☆ |
| 出稿速度 | 快（6 個月） | 中（9 個月） | 慢（12 個月+） |
| MVP 可展示度 | ★★★★★ | ★★★☆☆ | ★★★☆☆ |

---

## 期刊推薦

| 期刊 | IF | 適合題目 | 策略 |
|------|----|---------|------|
| **Expert Systems with Applications** | **8.5** | 題目一 | **首選** — 強調 architecture selection decision support |
| Computers in Biology and Medicine | 6.3 | 題目一、二 | 備選 — scope 完美匹配 |
| IEEE JBHI | 7.7 | 題目一 | 定位為 Strodthoff (2021) 延伸 |
| Biomedical Signal Processing and Control | 5.1 | 題目一、二 | 穩妥選擇 |
| Scientific Reports | 4.6 | 題目一 | 保底 |

### 競爭態勢警示

> **2025 年已有 2 篇類似定位的 arXiv preprint，研究窗口正在縮小。**
> 建議首投 ESWA (IF 8.5)，強調「architecture selection decision support」角度。
> 投稿前必須跑完真實實驗（~2-4 天 GPU time）。**模擬數據無法投稿任何期刊。**

---

## 主要結果預覽（模擬數據）

| 資料集 | 最佳模型 | Macro-F1 | vs 最佳純 CNN | vs 最佳純 Transformer |
|-------|---------|---------|-------------|---------------------|
| MIT-BIH (5-class) | CNN-Transformer | **0.946** | +4.8% | +2.0% |
| PTB-XL (5-superclass) | CNN-Transformer | **0.901** | +5.6% | +2.2% |
| CPSC2018 (9-class) | CNN-Transformer | **0.867** | +5.4% | +1.9% |

計算效率：**ResNet-1D**（1.8ms, 0.52M）最適合邊緣 / **CNN-Transformer**（6.8ms, 4.63M）最佳平衡 / **ECG-Transformer**（14.2ms, 7.81M）僅適合雲端

> *所有數值為模擬數據（^S^），統計自洽但非真實實驗結果。*

---

## 論文初稿預覽

![Experimental Framework](/cases/ecg-transformer/fig1_framework.png)
*統一實驗框架 — 3 個 ECG 資料集 → 統一前處理 → 6 個模型架構 → 多維度評估*

![Pareto Analysis](/cases/ecg-transformer/fig3_pareto.png)
*準確率 vs 計算量 Pareto frontier — CNN（藍）高效、Transformer（橘）高準確、Hybrid（綠）最佳平衡*

![Grad-CAM](/cases/ecg-transformer/fig4_gradcam.png)
*三種架構注意力模式 — CNN 聚焦 QRS 波、Transformer 分散於 P-QRS-T、Hybrid 自適應結合*

---

## DOI 驗證摘要

| 指標 | 數值 |
|------|------|
| 候選文獻 | 42 篇 |
| 最終採用 | 39 篇（92.9%） |
| 雙重驗證通過 | 37/39（94.9%） |
| Abstract 覆蓋率 | 33/39（84.6%） |

---

## 品質評估與改進空間

本初稿為論文方法學的流程展示（showcase）。

- MVP Gate（Stage 1）：✅ 通過，P0 = 0
- Stage 2-3：延後至真實實驗完成後

### 升級到 SCI 等級需要
1. 真實實驗數據替換模擬數值
2. 從實際模型提取 Grad-CAM
3. 通過完整 Phase 9（七維度 + Elite Audit）
4. GitHub repo 開放原始碼

---

## 下載論文初稿 PDF

<div style="background:#EFF6FF; border:1px solid #BFDBFE; border-radius:8px; padding:1.5rem; margin:1.5rem 0;">
  <p style="font-weight:700; color:#1E40AF; margin-bottom:0.5rem;">📄 論文初稿 PDF（含方法學展示標記）</p>
  <p style="color:#3B82F6; font-size:0.9rem; margin-bottom:1rem;">SHOWCASE DRAFT — 非投稿版本 | 15 頁 | 39 篇引用 | 4 圖 5 表</p>
  <button onclick="downloadCasePDF('ecg-transformer')" style="background:#2563EB; color:white; border:none; padding:0.6rem 1.5rem; border-radius:6px; font-weight:600; cursor:pointer;">
    下載 PDF
  </button>
</div>

<script>
async function downloadCasePDF(caseId) {
  if (!window.paperLabAuth) { alert('載入中，請稍後再試'); return; }
  const { getAuth } = await import("https://www.gstatic.com/firebasejs/11.5.0/firebase-auth.js");
  const { getApps } = await import("https://www.gstatic.com/firebasejs/11.5.0/firebase-app.js");
  const apps = getApps();
  if (apps.length === 0) return;
  const user = getAuth(apps[0]).currentUser;
  if (!user) { await window.paperLabAuth.login(); return; }
  try {
    const { getFirestore, collection, addDoc, serverTimestamp } = await import("https://www.gstatic.com/firebasejs/11.5.0/firebase-firestore.js");
    const db = getFirestore(apps[0]);
    await addDoc(collection(db, 'downloads'), {
      uid: user.uid, email: user.email, case_id: caseId,
      timestamp: serverTimestamp()
    });
    window.open('/cases/ecg-transformer/paper_draft_v0_showcase.pdf', '_blank');
  } catch(e) { console.error(e); window.open('/cases/ecg-transformer/paper_draft_v0_showcase.pdf', '_blank'); }
}
</script>

</div>

<!-- ===== 未登入時顯示的提示 ===== -->

<div id="gate-prompt" style="background: linear-gradient(135deg, #0B3C5D, #134B6E); border-radius: 16px; padding: 2.5rem; text-align: center; margin-top: 2rem;">
  <h3 style="color: #FFC857; font-size: 1.3rem; font-weight: 700; margin-bottom: 0.5rem;">想看完整分析？</h3>
  <p style="color: rgba(255,255,255,0.75); margin-bottom: 1.5rem; font-size: 1rem;">登入後可解鎖：完整缺口分析 + 三個可投稿題目 + 期刊推薦（含競爭態勢警示）+ 論文初稿 PDF 下載 + 品質審查報告</p>
  <button onclick="if(window.paperLabAuth){window.paperLabAuth.login()}else{alert('登入功能載入中，請稍後再試')}" style="background: #0F9D8A; color: white; border: none; padding: 0.85rem 2.5rem; border-radius: 12px; font-size: 1.1rem; font-weight: 700; cursor: pointer; min-height: 48px;">
    Google 登入解鎖 →
  </button>
</div>

<script>
document.addEventListener('DOMContentLoaded', function() {
  function checkAuth() {
    if (typeof firebase === 'undefined' && !window.paperLabAuth) {
      setTimeout(checkAuth, 500);
      return;
    }
    import("https://www.gstatic.com/firebasejs/11.5.0/firebase-auth.js").then(({ getAuth, onAuthStateChanged }) => {
      import("https://www.gstatic.com/firebasejs/11.5.0/firebase-app.js").then(({ getApps }) => {
        const apps = getApps();
        if (apps.length > 0) {
          const auth = getAuth(apps[0]);
          onAuthStateChanged(auth, function(user) {
            if (user) {
              document.getElementById('gated-content').style.display = 'block';
              document.getElementById('gate-prompt').style.display = 'none';
            } else {
              document.getElementById('gated-content').style.display = 'none';
              document.getElementById('gate-prompt').style.display = 'block';
            }
          });
        }
      });
    });
  }
  checkAuth();
});
</script>

---

## 想把這套方法應用到你的領域？

<div style="background: #F5F7FA; border-radius: 12px; padding: 1.5rem; text-align: center;">
  <p style="font-size: 1.1rem; margin-bottom: 1rem;">論文方法學可以應用到任何研究領域。預約諮詢，讓我們幫你找到你的研究缺口。</p>
  <a href="mailto:aicooperation.tw@gmail.com?subject=論文方法學 預約諮詢（ECG 案例參考）&body=您好，我看了 ECG 心律不整案例演練，想預約諮詢。%0A%0A我的研究領域：%0A目前卡在哪個階段：%0A想諮詢的問題：" style="display:inline-block; background:#0F9D8A; color:white; padding:0.85rem 2.5rem; border-radius:12px; text-decoration:none; font-weight:700; font-size:1.05rem; min-height:48px;">
    預約諮詢 →
  </a>
</div>

---
