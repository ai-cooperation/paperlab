# AI 學術研究全流程工作坊 — 完整課程計畫 v2.1
# AI-Assisted Research Paper Workshop: Complete Course Plan

> 版本：v2.1（增補種子DOI+API驗證、Obsidian、主編分析、IMRaD、YAML、
>       遠端GPU+Colab、TG Bot、Skill自動驗證、轉投策略、SVG、平行審查）
> 對象：研究生、博士生、產學合作研究人員
> 等級：L1D2（初階進階）+ L2D1（中階入門）
> 時長：兩天，每天 8 小時（含休息）
> 簡報頁數：55 頁

---

## 一、課程設計理念

### 核心差異化：「不只教工具，教完整工作流程」

| 一般 AI 課程 | 本工作坊 |
|-------------|---------|
| 教 ChatGPT 怎麼用 | 教從概念到投稿的端到端流程 |
| 工具導向 | 流程導向，工具服務流程 |
| 單點示範 | 系統化自動化（Skills + Agents + Commands） |
| 無品質保證 | 內建多維度審查機制 |
| 無後續追蹤 | 提供完整系統可帶走部署 |

### 學員分級定位

| 等級 | L1D2（Day 1） | L2D1（Day 2） |
|------|--------------|--------------|
| 前提 | 用過 ChatGPT | 完成 Day 1 |
| 重心 | 概念探索 + 文獻研究 | 實驗設計 + 論文撰寫 + 品質保證 |
| 產出 | 研究方向 + 文獻管理系統 | 論文初稿框架 + 品質審查報告 |
| 工具 | Claude Chat + Prompt Engineering | Claude Code + QMD + BibTeX |
| AI 角色 | AI 是「聰明的助教」 | AI 是「研究團隊」（8 個專家 Agent） |

---

## 二、完整工作流程對照表

以下是實際用於 NILM+LLM 論文（投稿 SETA）的完整流程，標記每個步驟在課程中的教學位置：

| Phase | 流程 | Day/Session | 工具/Skill | 教學深度 |
|-------|------|-------------|-----------|---------|
| P1 | 概念探索 | D1/S1 | Claude Chat, Extended Thinking | 完整教學 + 實作 |
| P2 | 文獻調研 | D1/S2 | **CrossRef/Semantic Scholar/OpenAlex API**, Zotero, Obsidian, bib-manager | 完整教學 + 實作 |
| P3 | 研究定位 | D1/S2-S3 | innovation-positioning, journal-fit, **主編分析**, research-contract | 完整教學 + Demo |
| P4 | 論文架構 | D2/S3 | **IMRaD 架構**, MD→QMD, **YAML 檔頭**, academic-writing | 完整教學 + 實作 |
| P5 | 實驗設計 | D2/S3 | experiment-tracker, **IDE+Colab+3090 遠端**, protocol-enforcer | 完整教學 + Demo |
| P6 | 實驗執行 | D2/S3 | gpu-monitor, SSH+nohup, **TG Bot 三層監控** | Demo |
| P7 | 數據分析 | D2/S4 | **Skill 自動驗證流程**, stats-validator, **數據一致性三角檢查** | 完整教學 + Demo |
| P8 | 論文撰寫 | D2/S4 | paper-writer, QMD→TeX, **SVG 向量圖**, **轉投策略+主編匹配** | 完整教學 + 實作 |
| P9 | 品質審查 | D2/S5 | **平行審查 Claude×ChatGPT×Gemini**, P0-P3 分級, mvp-gatekeeper | 完整教學 + 實作 |
| P10 | 投稿準備 | D2/S5 | submission-helper, **10項素材清單**, submission-bundle | 概念 + Demo |
| P11 | 審稿回覆 | D2/S5 | rebuttal-matrix, respond-reviewers | 概念介紹 |

---

## 三、Day 1 詳細課程設計（L1D2 初階進階）

### 主題：AI 研究基礎 — 從概念到文獻

---

### 09:00-09:30 | 開場：AI 正在重塑學術研究（30 min）

**內容**：
- AI 輔助研究的現狀與趨勢
- 完整工作流程總覽（10 個 Phase 概覽）
- 本工作坊的學習目標與成果承諾
- 真實案例：一篇 SETA 論文的 AI 協作歷程

**教學方式**：講述 + 案例展示

---

### 09:30-10:45 | Session 1：AI 概念探索與研究方向確定（75 min）

**Phase 1 對應**

**1.1 研究 Prompt 工程（25 min）**
- CARE 框架：Context / Action / Role / Example
- 研究專用 Prompt 模板 5 套：
  1. 領域掃描 Prompt
  2. Research Gap 識別 Prompt
  3. 可行性分析 Prompt
  4. 創新性定位 Prompt
  5. 研究問題精煉 Prompt

**1.2 多輪對話策略（20 min）**
- 漸進式縮焦法（寬 → 窄）
- Extended Thinking 使用時機
- 「think hard」「ultrathink」指令介紹
- 示範：從「智慧製造」到「Training-Free NILM」的 5 輪對話

**1.3 方向確認方法論（15 min）**
- 三角驗證：AI 建議 × 文獻證據 × 導師意見
- 研究問題的 SMART 化
- 示範工具：`innovation-positioning` skill

**1.4 即時練習（15 min）**
- 學員選定自己的研究主題
- 用 CARE 框架寫出第一個 Prompt
- 與 AI 進行 3 輪對話

---

### 10:45-11:00 | 休息

---

### 11:00-12:00 | Session 2 前半：文獻查找 + API 驗證 + Obsidian（60 min）

**Phase 2 對應 — 文獻正確性是本課程的核心環節**

**2.1 種子 DOI 生成 + 多層次搜索（15 min）**
- 用 AI 產出種子 DOI 清單（Prompt 範例）
- **關鍵警告**：AI 產出的 DOI 不能直接信任！必須 API 驗證
- 三層搜索：Scholar → ArXiv/IEEE → Citation Graph

**2.2 多重 API 驗證流程（文獻正確性的核心）（20 min）**
- **Step 1: CrossRef API** — DOI 存在性 + 正式 metadata
  - `https://api.crossref.org/works/{DOI}`
  - 比對 AI 給的 title/author/year 是否正確
- **Step 2: Semantic Scholar API** — Abstract + 引用數 + 領域
  - `https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=abstract,citationCount`
- **Step 3: OpenAlex API** — OA 狀態 + 機構 + Concepts
  - `https://api.openalex.org/works/doi:{DOI}`
- **Step 4: AI Abstract 語義比對** — 相關性 1-5 分
- 現場 Demo：用 curl 呼叫 CrossRef API 驗證一個 DOI
- 案例：43 篇引用全部經 CrossRef 驗證

**2.3 批次匯入 Zotero + Obsidian 知識圖譜（15 min）**
- Zotero 四種匯入方式：Magic Wand / Connector / BibTeX / API
- 文獻筆記卡格式（Obsidian Markdown + YAML frontmatter）
  ```markdown
  ---
  tags: [NILM, training-free]
  doi: "10.1016/..."
  relevance: 4/5
  cite_in: [Introduction, Related Work]
  ---
  # Author2021 - Paper Title
  ## Core Contribution → ...
  ## Related Papers → [[Hart1992]] [[Kelly2015]]
  ```
- **Obsidian Graph View**：節點=文獻、連線=雙向連結、聚類=主題群
- 孤立節點 = 可能遺漏的重要文獻

**2.4 Abstract 快速評估 + AI 筆記（10 min）**
- 5 維度評估（相關性/新穎性/影響力/可比較性/引用價值）
- Claude 閱讀 PDF → 結構化摘要
- 示範：用 AI 在 30 秒評估一篇論文

---

### 12:00-13:00 | 午休

---

### 13:00-14:30 | Session 2 後半 + Session 3 前導：文獻系統化與 Research Gap（90 min）

**2.4 BibTeX 引用管理入門（30 min）**
- `references.bib` 結構解析
- DOI → BibTeX 自動生成
- 引用防呆機制：`bib-manager` skill 如何運作
- 常見錯誤：重複條目、格式不一致、幽靈引用

**2.5 Literature Review 撰寫策略（30 min）**
- 文獻分類矩陣建立
- Research Gap 識別方法
- `literature-synthesis` skill 示範
- 從文獻到 Related Work 的轉換流程
- `/analyze-literature` command Demo

**2.6 研究定位 + 期刊匹配 + 主編分析（Phase 3 導入）（30 min）**
- 創新性論述策略（避免被定位為「應用研究」）
  - `innovation-positioning` skill 三層框架
  - 避免陷阱："Inspired by..." / "We improve..." / "Few studies..."
- **期刊匹配 6 維度評估（不只看 Scope！）**：
  | 維度 | 權重 | 內容 |
  |------|------|------|
  | Scope 契合度 | 35% | Aims & Scope 重疊 |
  | Impact Factor | 15% | JCR + CiteScore |
  | **主編研究偏好** | **20%** | **主編領域、發表傾向、近期 Editorial** |
  | **近期收錄主題** | **15%** | **近 2 年收錄文章 topic clustering** |
  | 審稿週期 | 10% | First Decision 時間 |
  | OA/APC | 5% | 費用與 OA 選項 |
- **主編分析方法（關鍵新增）**：
  1. 期刊官網 → Editorial Board → 記錄 EIC + AE
  2. Google Scholar 查主編近 5 年發表 → h-index + 研究關鍵詞
  3. 分析 Editorial / Guest Editorial → 偏好方向
  4. 近 2 年收錄文章標題 → AI topic clustering → 熱門/上升主題
  5. 時機判斷：新主編上任=更開放 / Special Issue=契合度高
- 案例：10 期刊加權評分 → Applied Energy (91) > IEEE TII (89) → 最終 SETA

---

### 14:30-14:45 | 休息

---

### 14:45-16:00 | 自動化工具入門 + 實作時間（75 min）

**2.7 Google Apps Script 自動化概念（20 min）**
- 批次 PDF 分析流程
- Claude API 整合概念
- 文獻追蹤通知設定

**2.8 Claude Code 初體驗（25 min）**
- Claude Code CLI 安裝與基本操作
- CLAUDE.md 的概念與作用（「AI 的工作手冊」）
- Skills / Agents / Commands 架構概覽
- 示範：用 Claude Code 批次處理文獻

**實作練習 1（30 min）**
- [ ] 選定研究主題，用 CARE 寫 3 個 Prompt
- [ ] 用 AI 對話 5 輪確定研究方向
- [ ] 用 AI 產出 10 個種子 DOI
- [ ] **用 CrossRef API 驗證至少 3 個 DOI 正確性**
- [ ] 建立 3 篇 **Obsidian 文獻筆記卡**（含雙向連結）
- [ ] 建立自己的 references.bib（至少 5 篇驗證過的引用）
- [ ] （進階）用 Semantic Scholar API 取 Abstract 做相關性評分

---

### 16:00-17:00 | Day 1 回顧與明日預告（60 min）

**回顧**：
- 核心技能 checklist（6 項）
- 學員產出檢查
- Q&A

**作業（可選）**：
- 擴充文獻到 20 篇
- 完成 Research Gap 分析初稿
- 寫一份 1 頁研究方向說明

---

## 四、Day 2 詳細課程設計（L2D1 中階入門）

### 主題：AI 研究進階 — 從架構到投稿

---

### 09:00-09:20 | Day 1 回顧 + 中階概念導入（20 min）

**內容**：
- Day 1 成果回顧
- 從「AI 助教」升級到「AI 研究團隊」的概念轉變
- 8 個專家 Agent 介紹：各司其職的 AI 團隊
- 今日目標：走完論文架構 → 撰寫 → 品質保證 → 投稿策略

---

### 09:20-10:45 | Session 3：論文架構設計與實驗規劃（85 min）

**Phase 4 + Phase 5 對應**

**3.1 IMRaD 標準論文架構設計（25 min）**
- **IMRaD 架構詳解**：
  - I (Introduction)：背景→問題→目的→貢獻聲明（漏斗式）
  - M (Methods)：問題定義→系統架構→演算法→物理約束
  - R (Results)：設置→主結果→Ablation→統計→錯誤分析
  - aD (Discussion)：分析→邊界→限制→未來
- 圖表清單規劃（`evidence-indexer` 追溯 claim→evidence）
- 案例：NILM 論文 5 圖 11 表的配置策略

**3.2 MD → QMD 轉換 + YAML 檔頭詳解（30 min）**
- **為什麼先 MD 再 QMD**：MD 寫作門檻低 → 加 YAML 檔頭即為 QMD
- **YAML 檔頭完整範例**（SETA/Elsevier 配置）：
  ```yaml
  title: "..."
  author:
    - name: Chung-Kuang Chen
      affiliations: [{name: NTUST, department: GIMT}]
  abstract: |
    ...
  bibliography: references.bib
  csl: elsevier-vancouver-author-date.csl
  format:
    elsevier-pdf:
      keep-tex: true
      journal: {name: SETA, cite-style: authoryear}
      classoption: [authoryear, preprint, review, 12pt]
      geometry: [margin=3cm, a4paper]
  ```
- **期刊格式對照表**：
  | 期刊 | format | classoption | csl |
  |------|--------|------------|-----|
  | Elsevier | `elsevier-pdf` | authoryear, preprint | elsevier-vancouver |
  | IEEE | `ieee-pdf` | journal | ieee.csl |
  | Springer | `springer-pdf` | — | springer-basic |
  | MDPI | `mdpi-pdf` | — | mdpi.csl |
- 示範：`quarto render paper.qmd` → PDF + TeX

**3.3 實驗設計 + IDE 工作流 + 遠端 GPU（30 min）**
- 實驗設計六要素 + Skill 支援
- **IDE 工作流（VS Code）**：
  - Python + Jupyter Extension
  - Quarto Extension（即時預覽論文）
  - Remote-SSH Extension（連遠端 GPU）
  - Claude Code CLI（AI 研究助手）
- **三層執行環境**：
  | 環境 | GPU | 用途 | 費用 |
  |------|-----|------|------|
  | 本地 MacBook | 無 | 開發/調試 | 免費 |
  | Google Colab | T4/A100 | 原型驗證 | 免費~$10/月 |
  | 遠端 3090 | RTX 3090 | 完整實驗 | 電費 |
- **Colab 實戰**：Drive 掛載 + pip install + 數據載入
- **遠端 3090 標準流程**：
  ```bash
  ssh ac-3090
  conda activate gpu
  PYTHONUNBUFFERED=1 nohup python -u train.py > exp.log 2>&1 &
  nvidia-smi  # 1 分鐘內檢查 GPU > 60%
  ```

---

### 10:45-11:00 | 休息

---

### 11:00-12:00 | 數據彙整策略 & 可重現性設計（60 min）

**Phase 6 + Phase 7 對應**

**3.4 TG Bot 實驗監控（20 min）**
- **三層監控系統**：
  - Level 1（即時）：1 分鐘 GPU 使用率、5 分鐘日誌輸出
  - Level 2（定期）：每 15 分鐘進程存在 + GPU + 日誌更新
  - Level 3（異常 → TG 即時通知）：進程消失/日誌停更/錯誤
- TG Bot 指令：`/check`（GPU）、`/all`（完整報告）、`/log`（日誌）
- 自動通知範例：實驗 OOM → 手機收到通知 + 建議
- Demo：展示真實 TG 通知截圖

**3.5 Skill 驅動的自動化統計驗證（25 min）**
- **自動化流程**：
  ```
  /analyze-experiment results.json
  → data-validator（品質+過擬合）
  → stats-validator（Bootstrap+效果量+功效）
  → statistical-validation skill（P0-P3 分級）
  → 論文用文本輸出
  ```
- **數據一致性三角驗證**：Text ↔ Table ↔ Figure
  - `figure-table-checker` skill 自動掃描
  - `evidence-indexer` skill：Claim → Evidence 追溯鏈
  - 案例：F1=0.820 vs 0.8488 不一致 → P0 問題
- 統計方法選擇：t-test / Mann-Whitney / Bootstrap / Cohen's d
- 常見統計陷阱與 P0-P2 分級

**3.6 可重現性設計（15 min）**
- 隨機種子固定（seed=42）
- 參數配置文件化（YAML/JSON）
- 結果 JSON 可序列化（NumpyEncoder）
- `metric-audit` skill：指標定義一致性
- 結果 → 論文的數字流：results/*.json → EXPERIMENT_RESULTS.md → paper.qmd

---

### 12:00-13:00 | 午休

---

### 13:00-14:15 | Session 4：QMD + BibTeX 論文撰寫系統（75 min）

**Phase 8 對應**

**4.1 論文撰寫 + 轉投策略（30 min）**
- 各章節撰寫策略（IMRaD 對應）：
  - Introduction：倒金字塔 + 貢獻聲明
  - Related Work：從 Obsidian 文獻矩陣到段落
  - Methodology：圖表先行、AI 生文字
  - Results：數據表 → AI 統計分析 → 討論
  - Discussion：限制性坦承 + 未來展望
- **轉投期刊策略（關鍵新增）**：
  1. 抓取目標期刊近 100 篇標題 → AI topic clustering → 識別熱點
  2. 分析主編偏好（Google Scholar + Editorial 內容）
  3. 調整 Title（對齊期刊熱門關鍵詞）
  4. 調整 Abstract + Introduction 第一段（引用該期刊近期文章）
  5. 修改 YAML format + CSL → `quarto render` → 新格式
- `paper-writer` agent + `academic-writing` skill

**4.2 SVG 向量圖 + QMD→TeX 快速轉換（20 min）**
- **SVG 向量圖製作**：
  - 為什麼 SVG？（無限放大、可編輯、期刊要求 300+ DPI）
  - Python → SVG/PDF/PNG 三格式輸出
    ```python
    fig.savefig('fig.svg', format='svg', bbox_inches='tight')
    fig.savefig('fig.pdf', format='pdf', bbox_inches='tight')
    ```
  - Inkscape 後處理：SVG → PDF/EPS（某些期刊要求）
  - QMD 引用：`![caption](fig.pdf){#fig-label width="100%"}`
- **QMD → TeX 快速轉換**：
  - `quarto render paper.qmd --keep-tex` → 同時得 .pdf + .tex
  - .tex 可直接提交 Overleaf 或期刊系統
  - 展示效果：5 秒內從 QMD 得到期刊格式 PDF

**4.3 BibTeX 進階管理（10 min）**
- 引用格式：`@citekey` 與 `[@a; @b]`
- CSL 樣式切換（APA, IEEE, Elsevier）
- `bib-manager` + `citation-checker` 雙重防呆
- 黃金規則：**絕不添加 references.bib 中不存在的引用**

**實作練習 2（15 min）**
- [ ] 建立 QMD 論文骨架（含完整 YAML 檔頭）
- [ ] 設定 bibliography + csl
- [ ] 寫出 Abstract 初稿（200 字）
- [ ] 加入 3 個引用，`quarto render` 驗證格式
- [ ] （進階）產出一張 SVG 圖並嵌入 QMD

---

### 14:15-14:45 | Claude Code 自動化工作流（30 min）

**核心教學**

**4.4 Claude Code 深度體驗 + Skill 自動化 Demo**
- **CLAUDE.md 詳解**：如何寫「AI 的工作手冊」
  - 引用處理原則（最高優先級）
  - 檔案操作原則 + 驗證原則
  - 專案目錄結構定義
  - 實驗執行規範
- **Skills 系統架構**：24 個專業知識庫
  - 基礎 Skills（14 個）：paper-review, bib-manager, literature-synthesis...
  - 進階 Research Agent Skills（10 個）：mvp-gatekeeper, journal-fit, evidence-indexer...
  - Skill 觸發機制：用戶輸入 → 語義匹配 → 自動載入
- **Agents 系統**：8 個 AI 專家團隊
  - 唯讀 Agent（citation-checker, paper-reviewer）：安全不改檔
  - 讀寫 Agent（paper-writer, submission-helper）：可編輯論文
  - 執行 Agent（data-validator, stats-validator）：可跑腳本
- **Commands 系統**：5 個一鍵工作流
- **現場 Demo（3 個完整流程）**：
  ```
  Demo 1: /review-paper paper.qmd "SETA"
  → citation-checker → data-validator → paper-reviewer
  → 輸出七維度評分 + P0-P3 問題清單

  Demo 2: /analyze-experiment results.json
  → data-validator → stats-validator
  → 輸出統計分析報告

  Demo 3: /prepare-submission "SETA"
  → paper-reviewer → submission-helper
  → 輸出 Cover Letter 草稿 + 檢查清單
  ```

---

### 14:45-15:00 | 休息

---

### 15:00-16:30 | Session 5：多維度分析 & 品質保證（90 min）

**Phase 9 + Phase 10 對應**

**5.1 多維度論文分析系統（20 min）**
- 七維度評分框架：
  1. 結構完整性
  2. 方法論嚴謹性
  3. 實驗設計
  4. 數據可信度
  5. 寫作清晰度
  6. 引用完整性
  7. 創新貢獻
- P0-P3 問題分級系統（致命/嚴重/重要/次要）
- `paper-review-skill` 完整示範
- `mvp-gatekeeper` skill：MVP 門檻檢查

**5.2 平行審查：Claude x ChatGPT x Gemini（25 min）**
- **為什麼需要多 AI 平行審查？**
  - 單一 AI 有盲點 → 多 AI 交叉檢查提高覆蓋率
  - 不同模型擅長不同面向 → 互補而非替代
- **三 AI 分工策略**：
  | AI 工具 | 強項 | 審查重點 | 工具/Skill |
  |---------|------|---------|-----------|
  | **Claude Code** | 系統化、Skill 生態系 | 七維度評分 + P0-P3 分級 + 引用驗證 + 數據一致性 | paper-review-skill, citation-checker, figure-table-checker |
  | **ChatGPT (GPT-4o)** | 結構/寫作流暢度 | 段落邏輯、語法、可讀性、論述連貫性 | Custom GPT / Prompt |
  | **Gemini (2.5 Pro)** | 事實查核/長文檢索 | 引用事實核對、數據聲明驗證、最新文獻覆蓋 | NotebookLM / Deep Research |
- **平行審查操作流程**：
  ```
  Step 1: Claude Code（自動化）
    /review-paper paper.qmd "SETA"
    → citation-checker → data-validator → paper-reviewer
    → 輸出：七維度評分 + P0-P3 問題清單

  Step 2: ChatGPT（手動 Prompt）
    Prompt: "Review this paper as a senior reviewer for [journal].
             Focus on: structure, argumentation flow, writing clarity,
             and paragraph-level logic. List issues by severity."
    → 輸出：寫作/邏輯問題清單

  Step 3: Gemini Deep Research（手動）
    Prompt: "Fact-check all claims and citations in this paper.
             Verify: (1) cited papers exist, (2) claims match source,
             (3) any missing recent key references (2023-2026)."
    → 輸出：事實核查 + 遺漏文獻清單

  Step 4: 整合（人工）
    三份報告合併 → 去重 → 按 P0-P3 排序 → 修改優先級
  ```
- **案例**：SETA 論文平行審查發現
  - Claude：F1 數據不一致（P0）、引用格式問題（P1）
  - ChatGPT：Discussion 段落邏輯跳躍（P1）、passive voice 過多（P2）
  - Gemini：2 篇引用年份錯誤（P1）、缺少 2025 關鍵綜述（P2）

**5.3 引用驗證與比對（15 min）**
- 三層引用驗證：
  - Layer 1: 存在性（DOI 有效、作者正確）
  - Layer 2: 準確性（引用主張 vs 原文）
  - Layer 3: 完整性（所有 .bib 條目都有被引用）
- `citation-checker` agent 實際運作
- `figure-table-checker` skill：圖表交叉引用

**5.4 Reviewer 預測與應對（15 min）**
- AI 模擬審稿人提問
- 常見 Reviewer 問題模板
- 案例：4 個預測問題與回答模板
- `rebuttal-matrix` skill 追蹤審稿回覆

**5.5 投稿策略與流程（15 min）**
- 期刊選擇方法論（加權評分表）
- Cover Letter 撰寫（`submission-helper` agent）
- 投稿前最終檢查清單（`submission-bundle` skill）
- `/prepare-submission` command Demo
- **投稿素材 10 項清單**：
  1. 論文 PDF（期刊格式）
  2. 論文 .tex 源碼（如需）
  3. Cover Letter
  4. 圖表高解析度檔案（SVG/PDF/TIFF, 300+ DPI）
  5. Supplementary Material
  6. Author Statement / CRediT
  7. Highlights（3-5 bullet points）
  8. Graphical Abstract（800x400px）
  9. Suggested Reviewers（3-5 人 + 理由）
  10. Data Availability Statement

---

### 16:30-17:30 | 總結與下一步（60 min）

**5.6 完整工作流回顧（15 min）**
- 10 個 Phase 完整走過
- 24 Skills + 8 Agents + 5 Commands 的系統全貌
- AI 參與度：65-70%

**5.7 如何部署這套系統到自己的研究（15 min）**
- `research-workspace.zip` 安裝指南
- CLAUDE.md 客製化方法
- Skills 新增與修改
- Telegram Bot 遠端設定

**5.8 學習路徑規劃（10 min）**
- 即刻行動（本週）
- 短期目標（1 個月）
- 中期目標（3 個月）

**Q&A + 課程評估（20 min）**

---

## 五、教學素材清單

### 必備素材

| # | 素材 | 類型 | 用於 |
|---|------|------|------|
| 1 | CARE 框架 Prompt 模板（5 套） | PDF/Handout | D1/S1 |
| 2 | 標準化文獻筆記模板（Obsidian 格式） | Markdown | D1/S2 |
| 3 | references.bib 範例檔 | BibTeX | D1/S2, D2/S4 |
| 4 | download_papers.sh | Shell Script | D1/S2 |
| 5 | API 驗證腳本（CrossRef/Semantic Scholar/OpenAlex） | Python/Shell | D1/S2 |
| 6 | Obsidian Vault 範例（含 10 篇文獻筆記卡 + Graph View） | Obsidian | D1/S2 |
| 7 | QMD 論文骨架模板（含 4 種期刊 YAML 配置） | Quarto | D2/S3-S4 |
| 8 | research-workspace.zip（24 Skills + 8 Agents + 5 Commands） | 完整系統 | D2 部署 |
| 9 | NILM+LLM 論文完整案例 | QMD + PDF | 全程案例 |
| 10 | 統計分析評估報告 | Markdown | D2/S4 |
| 11 | 七維度審查報告範例 | Markdown | D2/S5 |
| 12 | 平行審查整合模板（Claude×ChatGPT×Gemini） | Markdown | D2/S5 |
| 13 | Reviewer 預測問答模板 | Markdown | D2/S5 |
| 14 | 投稿素材 10 項檢查清單 | PDF/Handout | D2/S5 |

### Demo 環境

| # | 環境 | 用途 |
|---|------|------|
| 1 | Claude（Web/API） | D1 全程 |
| 2 | ChatGPT (GPT-4o) | D2/S5 平行審查 |
| 3 | Gemini (2.5 Pro / NotebookLM) | D2/S5 平行審查 |
| 4 | Claude Code CLI | D1/S2 後段, D2 全程 |
| 5 | VS Code + Quarto + Remote-SSH | D2 |
| 6 | Zotero（桌面版 + Connector） | D1/S2 |
| 7 | Obsidian（含 Graph View） | D1/S2 |
| 8 | Inkscape（SVG 後處理） | D2/S4 |
| 9 | Terminal（SSH + curl API） | D1/S2, D2/S3 |
| 10 | Telegram Bot | D2/S3 Demo |

---

## 六、學員前置準備

### Day 1 前
- [ ] 註冊 Claude 帳號（free 或 pro）
- [ ] 準備一個感興趣的研究主題
- [ ] 安裝 VS Code（可選）

### Day 2 前（Day 1 結束佈達）
- [ ] 安裝 Claude Code CLI（`npm install -g @anthropic-ai/claude-code`）
- [ ] 安裝 Quarto（`brew install quarto`）
- [ ] 準備至少 5 篇 PDF 文獻
- [ ] 完成 Day 1 的文獻整理作業

---

## 七、評估方式

### 過程評估（60%）

| 項目 | 佔比 | 評估標準 |
|------|------|---------|
| D1 實作練習 | 20% | CARE Prompt + **API 驗證 3 個 DOI** + **3 篇 Obsidian 筆記卡**（含雙向連結） + 5 篇 BibTeX 引用 |
| D2 實作練習 | 20% | QMD 骨架（含 YAML 檔頭）+ Abstract + 3 引用 + SVG 圖（進階） |
| 課堂參與 | 20% | 提問、討論、分享 |

### 成果評估（40%）

| 項目 | 佔比 | 評估標準 |
|------|------|---------|
| 研究方向報告 | 15% | 明確的研究問題 + Gap 分析 + **期刊匹配初評** |
| 論文框架 | 15% | 完整 QMD 骨架 + BibTeX + **所有引用經 API 驗證** |
| 系統部署 | 10% | 成功安裝 research-workspace + **Obsidian Vault 建立** |

---

## 八、課程時數分配統計

### Day 1（8 小時）
| 類型 | 時數 | 佔比 |
|------|------|------|
| 講述 | 3.0h | 37.5% |
| Demo | 1.5h | 18.8% |
| 實作 | 2.0h | 25.0% |
| 休息/Q&A | 1.5h | 18.8% |

### Day 2（8.5 小時）
| 類型 | 時數 | 佔比 |
|------|------|------|
| 講述 | 3.0h | 35.3% |
| Demo | 2.0h | 23.5% |
| 實作 | 1.5h | 17.6% |
| 休息/Q&A | 2.0h | 23.5% |

### 講述:Demo:實作 = 6:3.5:3.5 ≈ 46%:27%:27%
