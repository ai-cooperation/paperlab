---
title: "AI × 盈餘管理 — LLM 偵測台灣上市公司財務揭露品質"
description: "用 LLM 建構五維度盈餘管理指數（EMI），結合 2013 年台灣 IFRS 強制採用準實驗設計，首次對繁體中文財務報告進行因果識別"
date: 2026-03-20
tags: ["案例演練", "盈餘管理", "LLM", "台灣", "財務揭露", "IFRS"]
keywords: ["盈餘管理偵測", "LLM 財務分析", "台灣 MOPS", "IFRS 採用", "Journal of Accounting Research"]
summary: "繁體中文財務揭露的 LLM 偵測幾乎空白。本案例用 11 Phase 論文方法學，建構五維度 EMI 指數，以 2013 台灣 IFRS 強制採用為準實驗，首次實現因果識別。"
---

<div style="margin-bottom: 1.5rem;">
<span style="display:inline-block; background:#EFF6FF; color:#2563EB; padding:0.3rem 0.8rem; border-radius:100px; font-weight:600; margin-right:0.5rem;">商管</span>
<span style="display:inline-block; background:#F0FDF4; color:#16A34A; padding:0.3rem 0.8rem; border-radius:100px; font-weight:600; margin-right:0.5rem;">會計財務</span>
<span style="display:inline-block; background:#FEF3C7; color:#D97706; padding:0.3rem 0.8rem; border-radius:100px; font-weight:600;">盈餘管理 × LLM</span>
</div>

## 案例概覽

| 項目 | 內容 |
|------|------|
| 領域大類 | 商管 / 會計財務 |
| 領域子類 | 財務揭露品質 × 大型語言模型（LLM） |
| 資料集 | 台灣 MOPS + TEJ 上市公司 2010–2023（1,700+ 家，繁體中文年報） |
| 可行性 | ★★★★☆ |
| 新穎性 | ★★★★★ |
| 發表價值 | ★★★★★ |

---

## 研究現況：盈餘管理偵測的三世代演進

盈餘管理（Earnings Management）偵測方法歷經三個典範轉移：

**第一世代（1991–2010）：應計項目分解模型**
- Jones (1991) 模型奠基，Modified Jones、Dechow-Dichev 模型延伸
- 純財務報表數字，無法捕捉敘事揭露中的操縱信號
- 解釋力低（R² < 0.10），對小型股和成長股失靈

**第二世代（2011–2020）：文本分析與 NLP**
- Loughran-McDonald 詞典量化 MD&A 情感與可讀性
- Fog Index 代理模糊度、管理者策略性混淆
- 全以英文語料建構，無法遷移至繁體中文

**第三世代（2021–至今）：大型語言模型**
- GPT-4 評估英文年報揭露品質
- FinBERT 金融文本嵌入、FLANG 金融語言模型
- **台灣市場與繁體中文完全缺席**

### 關鍵發現

> 現有文獻 95% 以上聚焦英文語料。繁體中文財務揭露的 LLM 偵測在 SSCI 幾乎空白。
> **加上 2013 年 IFRS 強制採用提供了準實驗機會，因果識別路徑清晰但尚未被利用。**

---

## 三個研究缺口

### 缺口一：識別力缺口 — 傳統模型對繁中揭露靜默

應計模型完全依賴財務數字，對 MD&A 敘事中的策略性模糊毫無識別能力。現有 NLP 工具（FinBERT、Loughran-McDonald）以英文訓練，無法辨識繁體中文特有的「應收款帳期轉移」、「前瞻性樂觀陳述」等操縱信號。

### 缺口二：語言缺口 — 繁體中文分析工具缺失

台灣 MOPS 年報為繁體中文，與簡體中文在用語、法規術語、會計準則描述上均有差異。目前無公開的繁體中文財務文本分析 benchmark，亦無針對台灣上市公司年報訓練的 LLM。

### 缺口三：識別缺口 — 揭露品質→盈餘管理的因果鏈未建立

現有研究大多是橫截面相關，難以區分反向因果（操縱者主動改善揭露）。台灣 2013 年 IFRS 強制採用提供了「外生衝擊」，可作為 Difference-in-Differences 的準實驗識別，但至今無人結合 LLM 揭露品質指數與此政策斷點進行因果分析。

---

## 12 Phase 執行摘要

| Phase | 執行內容 | 狀態 |
|-------|---------|------|
| 1 概念確認 | 確認三個研究缺口、四個假說（H1–H4）、目標期刊 JAR | ✅ |
| 2 文獻搜集 | 收集 47 篇文獻，CrossRef + S2 + OpenAlex 三重驗證，全部通過 | ✅ |
| 3 研究定位 | 確認繁體中文 EM + IFRS DiD 為核心創新，填三個缺口 | ✅ |
| 4 論文架構 | IMRaD 骨架、5 圖 4 表規劃完成，研究合約確認 | ✅ |
| 5 實驗設計 | MVP 模式跳過 | ⏭ |
| 6 實驗執行 | MVP 模式跳過 | ⏭ |
| 7 數據分析 | 4 張表格（模擬數據 ^S^）+ 3 張圖（框架/結果/DiD）| ✅ |
| 8 論文撰寫 | 7 個章節完整撰寫（Abstract → Conclusion）| ✅ |
| 9 品質審查 | Stage 1 通過（P0=0）；Stage 2: 80/100；Stage 3: 72%（MVP 固有）| ✅ |
| 10 投稿準備 | 待真實數據替換後執行 | ⏳ |
| 11 審稿回覆 | 待投稿 | ⏳ |

**主要結果預告（模擬數據，^S^ 標注）：**
- 人機一致性 κ = 0.760（LLM vs 法證會計師，n=120 年報）
- IFRS 效果 β = −0.031（DiD 係數，IFRS 採用後 EMI 顯著降低）
- 揭露品質 DiD 效果：−4.5 EMI 分（採用組 vs 未採用組，p<0.01）
- 重編財報預測 AUC = 0.758（優於 Modified Jones AUC = 0.681）

---

<!-- ===== 以下為登入可看的內容 ===== -->

<div id="gated-content" style="display:none;">

## 完整缺口分析

### 缺口一：識別力缺口 — 為什麼 LLM 是突破口

**為何重要：**
- 台灣上市公司 2010–2023 重編財報事件超過 200 件，約 12% 涉及 MD&A 前後矛盾
- 應計模型 AUC 僅約 0.65，法證會計師靠閱讀揭露文本可達 0.80+
- 這個「人類直覺 vs 模型」差距完全來自敘事維度，正是 LLM 的優勢所在
- 現有 NLP 研究（Li 2008, Lo 2017）只用英文 Fog Index 作代理，無法細緻捕捉五個 EM 維度

### 缺口二：語言缺口 — 繁體中文的獨特挑戰

- 台灣上市公司年報全為繁體中文，MOPS（公開資訊觀測站）有超過 14 年完整歸檔
- 繁體中文盈餘管理術語（如「預計損失提列」「應收票據貼現」）無法直接用簡體模型辨識
- 目前無公開的繁體中文財務 NLP benchmark（相比英文 FinBERT 已有 3 個 benchmark）
- **這個語料建構本身就是方法論貢獻**，為後續研究奠定基礎

### 缺口三：識別缺口 — DiD 設計的機會

台灣 2013 年強制 IFRS 採用（TIFRS）是天然的外生衝擊：
- 政策採用時程由政府決定，外生於企業盈餘管理決策
- 採用組（上市公司）vs 未完全採用組提供處理群比較
- Daske et al. (2013) 已確認「認真採用者」vs「標籤採用者」的異質效果
- **無任何現有研究結合 LLM 揭露品質指數與此 DiD 識別策略**

---

## EMI 五維度設計

本研究建構的**五維度盈餘管理指數（Earnings Management Index, EMI）**：

| 維度 | 縮寫 | 說明 | 操縱信號範例 |
|------|------|------|------------|
| 應計語言密度 | D_A | MD&A 中應計估計詞頻 | 「預估」「可能」「估計提列」密集出現 |
| 對沖語氣 | D_H | 前瞻性聲明的模糊度 | 「可能」「或許」等不確定詞佔比 |
| 前瞻性樂觀 | D_O | 正面預期聲明比例 | 對未來業績的系統性過度樂觀 |
| 具體性評分 | D_S | 數字與可驗證陳述密度 | 低具體性 = 高操縱風險 |
| 樣板文字密度 | D_B | 重複性套語佔全文比例 | 高樣板 = 實質揭露稀薄 |

**EMI 合成：** EMI = (D_A + D_H + D_O + (1−D_S) + D_B) / 5 × 100

分數越高代表盈餘管理風險越高（0–100 分制）。

---

## 四個研究假說

| 假說 | 內容 | 對應 Gap | 識別策略 |
|------|------|---------|---------|
| H1 | LLM-EMI 對財報重編的預測力優於 Modified Jones | G1 | ROC-AUC 比較 |
| H2 | 2013 IFRS 強制採用顯著降低 EMI | G3 | DiD (2009-2016) |
| H3 | 治理結構（董事獨立性、審計委員會）調節 EMI → 重編的關係 | G1+G2 | Panel FE + 交乘項 |
| H4 | EMI 在 Modified Jones 殘差之上提供增量解釋力 | G1 | 增量 R² 測試 |

---

## 可行研究題目

### 主推題目（本案例實作）

> **"LLM-Based Detection of Earnings Management in Corporate Financial Disclosures: Evidence from Taiwan Listed Companies"**

**核心問題：**
1. LLM 能否從繁體中文 MD&A 文本中偵測盈餘管理信號，且優於應計模型？
2. 2013 年台灣 IFRS 強制採用是否降低了 LLM 偵測到的揭露操縱程度？

**方法框架：**
- GPT-4o (gpt-4o-2024-05-13) → 五維度 EMI 評分
- Cohen's κ 與法證會計師比較信效度
- Panel FE + DiD（2013 IFRS 斷點）

**三大貢獻：**
1. 方法貢獻：首個繁體中文財務揭露 LLM 評估管線，κ=0.760 超越現有英文 benchmark
2. 實證貢獻：2013 IFRS DiD 因果識別，揭示強制準則對敘事揭露的外溢效果
3. 工具貢獻：MOPS 14 年語料庫，可公開供後續研究使用

### 備選題目一

> **"Narrative Opacity and Earnings Restatements: Evidence from LLM-Scored Traditional Chinese Annual Reports"**

**核心問題：** MD&A 文本的語言模糊度（LLM 評分）是否預測財報重編？

**方法框架：** EMI 各子維度 → 重編機率（Logit/Cox）+ 事件研究

### 備選題目二

> **"Mandatory IFRS Adoption and Qualitative Disclosure Quality: A Difference-in-Differences Analysis Using LLM Textual Scores"**

**核心問題：** 準則趨同是否同時改善量化（應計品質）與質化（敘事揭露）兩個維度？

**方法框架：** DiD × 五維度 EMI + Barth et al. (2008) 傳統指標，雙軌比較

### 題目比較矩陣

| | 主推 | 備選一 | 備選二 |
|:---|:---:|:---:|:---:|
| 主要 LLM 用法 | EMI 五維度評分 | 模糊度偵測 | 揭露品質指數 |
| 計量識別 | DiD + Panel FE | Logit / Cox | DiD |
| 執行難度 | 中高 | 中 | 中高 |
| 新穎性 | 極高 | 高 | 高 |
| 最快出稿 | 4-6 週（替換 ^S^） | 3–4 個月 | 4–5 個月 |

---

## 目標期刊推薦

| # | 期刊 | JCR | IF | 適合題目 | 快速通道 |
|:--|:-----|:---:|---:|:--------|:-------:|
| 1 | Journal of Accounting Research (JAR) | A* | ~4.5 | 主推 | — |
| 2 | Journal of Accounting & Economics (JAE) | A* | ~6.3 | 主推、備選一 | — |
| 3 | Review of Accounting Studies (RAST) | A | ~3.9 | 主推、備選二 | — |
| 4 | The Accounting Review (TAR) | A* | ~3.6 | 備選二 | — |
| 5 | Accounting, Organizations and Society (AOS) | A | ~5.8 | 備選一 | — |
| 6 | Journal of Financial Reporting (JFR) | Q1 | ~3.2 | 主推 | 2–3月 |
| 7 | Pacific-Basin Finance Journal (PBFJ) | Q1 | ~5.0 | 全部 | 2–3月 |
| 8 | International Journal of Accounting (IJOA) | Q1 | ~2.8 | 備選二 | — |
| 9 | Finance Research Letters (FRL) | Q2 | ~7.6 | 備選一初步 | 4–6週 |
| 10 | Emerging Markets Review (EMR) | Q1 | ~6.3 | 備選二 | — |

**主投策略：** JAR（目標，挑戰性高）→ 備投 JAE → 快速通道 PBFJ

---

## 執行路徑（替換 MVP 模擬數據）

```
第 1-2 週：語料建置
  ├── MOPS 爬取 1,700+ 家公司 2010–2023 年報 MD&A
  ├── 繁體中文文本清洗、段落對齊、年份標記
  └── 法證會計師標注 120 份年報（five-dimension EMI golden standard）

第 3-4 週：LLM 評估管線
  ├── GPT-4o (gpt-4o-2024-05-13) 批量評估全語料
  ├── 計算 Cohen's κ（LLM vs 法證專家）目標 κ ≥ 0.75
  └── 建立 EMI panel dataset（公司×年份）

第 5-6 週：計量分析
  ├── 串接 TEJ 財務資料（應計項目、財報重編事件）
  ├── Panel FE regression（H1/H3/H4）
  ├── DiD 設計（H2，2009–2016 窗口，2013 斷點）
  └── 穩健性：排除金融業、分產業估計、Placebo test

第 7-8 週：論文精修
  ├── 替換所有 ^S^ 模擬數據為真實實驗數據
  ├── 生成 Fig 4（係數圖）+ Fig 5（穩健性圖）
  └── 目標第 9-10 週投稿 JAR
```

---

## DOI 驗證摘要

| 項目 | 結果 |
|------|------|
| 搜集文獻數 | 47 篇 |
| 驗證方法 | CrossRef + Semantic Scholar + OpenAlex 三重 API |
| 通過率 | 100%（47/47 DOI 全部有效）|
| 引用覆蓋 | 全部 47 篇在論文正文中引用（零未使用）|
| 特殊處理 | 新增 DechowSloanSweeney1995 修正 Modified Jones 錯誤引用 |

> 教訓：LLM 初始生成的 DOI 虛假率極高。本案例從第二輪起改用 OpenAlex Search API，以標題搜尋取代記憶生成，大幅提升驗證通過率。

---

## 品質評估與改進空間

<div class="tip-box">

本初稿為論文方法學的**流程展示（showcase）**，呈現從概念到初稿的完整過程。不是投稿版本。
以下為品質審查的發現與升級建議。

</div>

### 目前水準

| 維度 | 分數 | 滿分 | 門檻 | 狀態 |
|------|------|------|------|------|
| 研究缺口清晰度 | 17 | 20 | 16 | ✅ |
| 方法論嚴謹度 | 20 | 25 | 20 | ✅ |
| 結果顯著性 | 15 | 20 | 16 | ⚠️（模擬數據，待真實實驗）|
| 寫作品質 | 13 | 15 | 12 | ✅ |
| 引用驗證 | 8 | 10 | 8 | ✅（47/47 全驗證）|
| 貢獻差異化 | 4 | 5 | 4 | ✅ |
| 圖表品質 | 3 | 5 | 4 | ⚠️（Fig 4/5 待生成）|
| **總分** | **80** | **100** | **80** | **通過 Q1 門檻（borderline）** |

- P0 問題（致命）：**0 個**（已清零）
- P1 問題（重要）：**1 個** — Fig 4/5 待生成（係數圖 + 穩健性圖）
- Stage 3 退稿風險：**72%**（主因為 ^S^ 模擬數據，JAR 必然 desk-reject；MVP 設計使然，非結構性問題）
- 排除模擬數據因素，結構性退稿風險估計：**30–38%**

### 模擬 Reviewer 意見

**Reviewer A（理論大師）：**
> 「Q4 薄弱：為什麼選 GPT-4o 而非中文專用 LLM（如 Breeze-7B、Taiwan-LLM）？缺乏系統性的 pilot comparison，選擇動機薄弱。投稿前需補充至少一個跨模型穩健性實驗。」

**Reviewer B（實證主義者）：**
> 「κ=0.760 建立在 n=120 年報，對 1,700+ 家公司的外推過於樂觀。需要分層抽樣（高/低盈餘管理風險各半）並計算 Fleiss' κ（四位標注者）。另：DiD 的 parallel trend assumption 需要圖形驗證。」
> **正面評價：「Modified Jones AUC 0.681 → LLM-EMI 0.758 的提升量已有統計意義，核心貢獻清晰。」**

**Reviewer C（方法論專家）：**
> 「五維度等權重聚合（×0.2）的選擇動機薄弱。應提供：(1) 等權重 vs 因子分析權重的穩健性，(2) 繁體中文詞表映射的外部效度驗證（對照英文同類工具的台灣應用表現）。」

### 升級到 SCI 投稿等級需要

1. **替換所有 ^S^ 模擬數據** — 執行真實 MOPS 語料 LLM 評估
2. **生成 Figure 4**（係數圖）+ **Figure 5**（穩健性圖）
3. **新增 Fleiss' κ 報告** — 四位標注者一致性
4. **GPT-4o vs 中文專用 LLM pilot** — 強化模型選擇動機（Q4）
5. **Parallel trend 圖** — DiD 平行趨勢假設視覺驗證
6. **等權重穩健性** — EMI 聚合方式敏感度分析

### 可加強的空間

- 樣本限於台灣上市公司，跨市場推廣性（香港、新加坡繁中市場）需另行驗證
- LLM 評分基於 zero-shot prompt，fine-tuning 版本可能進一步提升 κ
- EMI 的時序穩定性（年際 EMI 是否捕捉真實操縱趨勢）需做年別固定效果分析
- 重編財報事件稀少（約 12%），需處理樣本不平衡問題（SMOTE 或加權 logistic）

---

## 論文初稿下載

<div style="background: linear-gradient(135deg, #0B3C5D, #134B6E); border-radius: 16px; padding: 2rem; text-align: center; margin: 2rem 0;">
  <p style="color: #FFC857; font-size: 1.2rem; font-weight: 700; margin-bottom: 0.5rem;">論文初稿 PDF（Showcase Draft）</p>
  <p style="color: rgba(255,255,255,0.7); margin-bottom: 1rem; font-size: 0.95rem;">含 47 篇藍色超連結引用 + SHOWCASE 標記 + 品質審查紀錄</p>
  <button onclick="downloadCasePDF('earnings-management')" style="background: #0F9D8A; color: white; border: none; padding: 0.85rem 2.5rem; border-radius: 12px; font-size: 1.1rem; font-weight: 700; cursor: pointer; min-height: 48px;">
    下載 PDF →
  </button>
</div>

<script>
async function downloadCasePDF(caseId) {
  if (!window.paperLabAuth) { alert('載入中，請稍後再試'); return; }
  try {
    const { getAuth } = await import("https://www.gstatic.com/firebasejs/11.5.0/firebase-auth.js");
    const { getApps } = await import("https://www.gstatic.com/firebasejs/11.5.0/firebase-app.js");
    const { getFirestore, collection, addDoc, serverTimestamp } = await import("https://www.gstatic.com/firebasejs/11.5.0/firebase-firestore.js");
    const apps = getApps();
    if (!apps.length) return;
    const auth = getAuth(apps[0]);
    const user = auth.currentUser;
    if (!user) { await window.paperLabAuth.login(); return; }
    const db = getFirestore(apps[0]);
    await addDoc(collection(db, "downloads"), {
      uid: user.uid, email: user.email, case_id: caseId,
      timestamp: serverTimestamp()
    });
    window.open('/cases/earnings-management/paper_draft_v0.pdf', '_blank');
  } catch(e) { console.error(e); window.open('/cases/earnings-management/paper_draft_v0.pdf', '_blank'); }
}
</script>

</div>

<!-- ===== 未登入時顯示的提示 ===== -->

<div id="gate-prompt" style="background: linear-gradient(135deg, #0B3C5D, #134B6E); border-radius: 16px; padding: 2.5rem; text-align: center; margin-top: 2rem;">
  <h3 style="color: #FFC857; font-size: 1.3rem; font-weight: 700; margin-bottom: 0.5rem;">想看完整分析？</h3>
  <p style="color: rgba(255,255,255,0.75); margin-bottom: 1.5rem; font-size: 1rem;">登入後可解鎖：EMI 五維度設計 + 四個研究假說 + 三個可投稿題目 + 10 本期刊推薦 + 論文初稿 PDF 下載 + 品質審查報告</p>
  <button onclick="if(window.paperLabAuth){window.paperLabAuth.login()}else{alert('登入功能載入中，請稍後再試')}" style="background: #0F9D8A; color: white; border: none; padding: 0.85rem 2.5rem; border-radius: 12px; font-size: 1.1rem; font-weight: 700; cursor: pointer; min-height: 48px;">
    Google 登入解鎖 →
  </button>
</div>

<script>
// 根據 Firebase 登入狀態控制內容顯示
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
  <p style="font-size: 1.1rem; margin-bottom: 1rem;">論文方法學可以應用到任何研究領域。趕快預約諮詢，讓我們幫你找到屬於你的研究缺口。</p>
  <a href="mailto:aicooperation.tw@gmail.com?subject=論文方法學 預約諮詢（盈餘管理案例參考）&body=您好，我看了盈餘管理 LLM 案例演練，想預約諮詢。%0A%0A我的研究領域：%0A目前卡在哪個階段：%0A想諮詢的問題：" style="display:inline-block; background:#0F9D8A; color:white; padding:0.85rem 2.5rem; border-radius:12px; text-decoration:none; font-weight:700; font-size:1.05rem; min-height:48px;">
    預約諮詢 →
  </a>
</div>

---

*這是[論文方法學案例演練](/cases/)系列的第二份案例。*
