# Journal Fit Analysis — ECG Transformer vs CNN Benchmark

**Generated**: 2026-03-20
**Contribution Type**: Benchmark / Comparative Study (非 novel method)
**Academic Level Target**: L2–L3 (Q1–Q2)

---

## 競爭態勢分析（必須正視）

### 已存在的競爭研究

| 論文 | 年份 | 定位 | 與我們的重疊 |
|------|------|------|-------------|
| Strodthoff et al., IEEE JBHI | 2021 | PTB-XL benchmark (CNN only) | 我們多 Transformer + 多資料集 |
| Silva et al., arXiv 2503.07276 | 2025 | Systematic review: fair evaluation + embedded feasibility | 高度重疊 — 他們也強調公平比較 + 部署 |
| arXiv 2507.14206 | 2025 | Comprehensive ECG Time-Series Benchmark (含 classification, detection, forecasting, generation) | 他們範圍更廣，但未聚焦 CNN vs Transformer |
| Ansari et al., AI Review | 2025 | Survey: Transformer + LLM for ECG | Survey 非 benchmark，但覆蓋我們的 Transformer 部分 |

### 我們的差異化優勢
1. **聚焦 CNN vs Transformer vs Hybrid** 三族群對比（別人是 survey 或單族群）
2. **3 資料集 × 6 模型 × 統計檢定** 的控制實驗設計
3. **計算效率 Pareto frontier** — 別人幾乎都沒做
4. **部署場景選擇指南** — 從 benchmark 延伸到 practical recommendation

### 核心風險
- ⚠️ Benchmark paper 沒有 novel method → 頂級期刊 desk-reject 風險高
- ⚠️ 2025 已有 2 篇類似定位的 arXiv preprint → 時間壓力
- ⚠️ 需要真實實驗數據才能投稿（目前 MVP 模擬）

---

## 期刊推薦排名

### 🥇 推薦 1: Expert Systems with Applications

| 指標 | 數值 |
|------|------|
| **IF** | 8.5 (2024) |
| **SJR** | Q1 |
| **Scope Match** | ⭐⭐⭐⭐⭐ (5/5) |
| **接受 benchmark 論文** | ✅ 經常刊登 comparative study |
| **Desk-reject 風險** | 低 — 接受 applied comparison |
| **審稿週期** | 2–4 個月 |
| **APC** | ~$3,390 (OA) / 免費 (hybrid) |

**為何首選：**
- ESWA 明確歡迎 "comparative and benchmark studies"
- 近期刊登過 cross-database ECG classification (Imtiaz 2024, 我們已引用)
- 計算效率分析 + 部署指南符合其 "expert systems" 定位
- IF 8.5 比 CBIOMED 6.3 更高

**投稿角度：** 強調 "architecture selection decision support system for clinical deployment"

**風險：** 需強化 deployment guideline 段落，加入 decision tree 或 flowchart

---

### 🥈 推薦 2: Computers in Biology and Medicine

| 指標 | 數值 |
|------|------|
| **IF** | 6.3 (2024) |
| **SJR** | Q1 |
| **Scope Match** | ⭐⭐⭐⭐⭐ (5/5) |
| **接受 benchmark 論文** | ✅ 近期有 ECG DL benchmark |
| **Desk-reject 風險** | 中 — 需證明超越 Strodthoff2021 |
| **審稿週期** | 2–3 個月 |
| **APC** | ~$3,250 (OA) / 免費 (hybrid) |

**為何推薦：**
- 論文已瞄準此期刊，scope 完美匹配
- 近期大量刊登 ECG + deep learning（我們引用了 4 篇 CBIOMED）
- Oh2018、Gu2023、Li2024 都發在這裡

**投稿角度：** 保持原論文定位 — systematic benchmark + deployment analysis

**風險：** Reviewer 可能質疑 "為何不提 novel method"；需在 Introduction 強調 benchmark 的價值高於又一個新模型

---

### 🥉 推薦 3: Biomedical Signal Processing and Control

| 指標 | 數值 |
|------|------|
| **IF** | 5.1 (2024) |
| **SJR** | Q1 |
| **Scope Match** | ⭐⭐⭐⭐ (4/5) |
| **接受 benchmark 論文** | ✅ ECG 是核心主題 |
| **Desk-reject 風險** | 低 |
| **審稿週期** | 3–5 個月 |
| **APC** | ~$2,990 (OA) |

**為何推薦：**
- CAT-Net (Islam2024)、Xia2023、Alamatsaz2024 都發在 BSPC
- 對 ECG 方法論文非常友好
- 接受率相對較高

**投稿角度：** 強調 signal processing 層面（preprocessing pipeline, Stockwell transform 對比）

**風險：** IF 較低 (5.1)，如果目標是高影響力可考慮其他

---

### 備選 4: IEEE Journal of Biomedical and Health Informatics (IEEE JBHI)

| 指標 | 數值 |
|------|------|
| **IF** | 7.7 (2024) |
| **SJR** | Q1 |
| **Scope Match** | ⭐⭐⭐⭐ (4/5) |
| **接受 benchmark** | ✅ Strodthoff2021 就在這裡 |
| **Desk-reject 風險** | 中高 — 需明確超越 Strodthoff |
| **審稿週期** | 4–8 個月（IEEE 較慢） |

**為何考慮：** Strodthoff 的 PTB-XL benchmark 就在 JBHI，我們可以定位為其「擴展版」
**風險：** IEEE 審稿慢、格式嚴格、需 IEEE 會員

---

### 備選 5: Scientific Reports

| 指標 | 數值 |
|------|------|
| **IF** | 4.6 (2024) |
| **SJR** | Q1 |
| **Scope Match** | ⭐⭐⭐ (3/5) |
| **接受 benchmark** | ✅ 幾乎不拒 benchmark |
| **Desk-reject 風險** | 極低 |
| **審稿週期** | 1–3 個月 |

**為何考慮：** Kim2025、Alghieth2025 都發在 Scientific Reports，benchmark 容易過
**風險：** IF 4.6 較低，聲望不如 Q1 專業期刊

---

## 選擇決策矩陣

| 因素 | 權重 | ESWA | CBIOMED | BSPC | IEEE JBHI | Sci Rep |
|------|------|------|---------|------|-----------|---------|
| Scope 匹配 | 30% | 5 | 5 | 4 | 4 | 3 |
| 接受 benchmark 意願 | 25% | 5 | 4 | 4 | 3 | 5 |
| IF / 聲望 | 20% | 5 | 4 | 3 | 5 | 2 |
| 審稿速度 | 15% | 4 | 4 | 3 | 2 | 5 |
| Desk-reject 風險(反向) | 10% | 5 | 3 | 4 | 2 | 5 |
| **加權總分** | **100%** | **4.85** | **4.20** | **3.65** | **3.35** | **3.75** |

---

## 最終建議

### 策略 A：衝高 IF（推薦）
**首投 → Expert Systems with Applications (IF 8.5)**
被拒 → 轉投 Computers in Biology and Medicine (IF 6.3)
再被拒 → Biomedical Signal Processing and Control (IF 5.1)

### 策略 B：穩妥快速
**首投 → Computers in Biology and Medicine (IF 6.3)**
被拒 → 轉投 Scientific Reports (IF 4.6)

### 策略 C：最大聲望
**首投 → IEEE JBHI (IF 7.7)**
定位為 Strodthoff2021 的 Transformer-era 延伸
風險高但成功聲望最大

---

## 投稿前必須完成的事項

1. **跑真實實驗** — 模擬數據無法投稿任何期刊
2. **生成 4 張圖** — 框架圖、架構圖、Pareto 圖、Grad-CAM 圖
3. **加強 deployment guideline** — 加入 decision flowchart（特別是投 ESWA）
4. **跑 Phase 9 Stage 2+3** — Paper Review + Elite Audit
5. **加入 code availability** — GitHub repo link
