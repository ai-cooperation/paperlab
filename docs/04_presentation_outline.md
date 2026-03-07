# 簡報升級版 v2.0 — 逐頁大綱（55 頁）
# Presentation Outline v2.0 (55 slides)

> 基於 v1.0（27 頁）全面升級
> v2.0 新增：種子DOI+API驗證、Obsidian知識圖譜、主編分析、IMRaD架構、
>           MD→QMD+YAML、遠端GPU+Colab、TG Bot監控、Skill自動驗證、
>           轉投策略、SVG向量圖、平行審查（Claude×ChatGPT×Gemini）
> 標記：[保留] [更新] [新增]

---

## DAY 1: AI 研究基礎（L1D2 初階進階）

### 開場區（Slides 1-4）

**Slide 1 [更新]** — 封面
- 標題：AI 學術研究全流程工作坊 2026
- 副標題：從概念探索到論文投稿的完整 AI 協作工作流程
- 標籤：L1D2 + L2D1 | 24 Skills | 8 Agents | 5 Commands | 5 APIs
- 底部：Smart Manufacturing Research Application

**Slide 2 [更新]** — 完整 AI 研究工作流程總覽
- 更新為 11 個 Phase（含審稿回覆）
- 每個 Phase 標註核心工具
- 特別標記：種子DOI→API驗證→Zotero→Obsidian 的數據流
- 標記 Day 1 / Day 2 覆蓋範圍
- 底部：AI 參與度 70-75%

**Slide 3 [更新]** — 兩天課程議程規劃
- Day 1 議程（左欄）— 含 API 驗證、Obsidian 實作
- Day 2 議程（右欄）— 含 IMRaD、YAML、平行審查
- 每節標記實作/Demo/講授比例

**Slide 4 [保留]** — Day 1 封面頁

---

### Session 1：概念探索（Slides 5-9）

**Slide 5 [保留]** — 為什麼需要 AI 輔助學術研究？
- 三組痛點 vs AI 解決方案

**Slide 6 [保留]** — Session 1：AI 概念探索
- 四步驟：領域掃描 → 痛點聚焦 → 方向討論 → 方向確定

**Slide 7 [保留]** — 研究 Prompt 工程：CARE 框架
- Context / Action / Role / Example + 範例 Prompt

**Slide 8 [保留]** — 多輪對話策略
- 漸進式縮焦法 + 5 輪對話示範

**Slide 9 [新增]** — 真實案例：NILM+LLM 的概念探索歷程
- 5 輪對話時間線 + 最終三大貢獻點
- Extended Thinking: think / think hard / ultrathink 用法
- 多模型交叉驗證：Claude + ChatGPT + Gemini 同時問

---

### Session 2：文獻調研 — 核心環節（Slides 10-20）

**Slide 10 [保留]** — Session 2：AI 輔助文獻查找策略
- 三層文獻搜索（Scholar → ArXiv/IEEE → Citation Graph）

**Slide 11 [新增]** — 種子 DOI 生成：用 AI 產出候選文獻清單
- 左側：Prompt 範例
  ```
  你是 [領域] 的資深研究者。
  請列出 [主題1]、[主題2]、[主題3] 三個方向
  近 5 年最重要的 20 篇論文，包含 DOI。
  ```
- 右側：AI 產出範例（DOI 清單）
- 底部警告：**AI 產出的 DOI 不能直接信任！** 必須 API 驗證

**Slide 12 [新增]** — 多重 API 驗證流程（文獻正確性的核心）
- 四步驟流程圖（全頁視覺化）：
  ```
  Step 1: CrossRef API → DOI 存在性 + 正式 metadata
  Step 2: Semantic Scholar API → Abstract + 引用數
  Step 3: OpenAlex API → OA 狀態 + 機構 + Concepts
  Step 4: AI Abstract 語義比對 → 相關性 1-5 分
  ```
- 每步驟附 API endpoint URL
- 底部：驗證通過 → 批次匯入 Zotero

**Slide 13 [新增]** — API 實戰示範
- 左欄：CrossRef API 呼叫範例 + 回應 JSON
  ```bash
  curl "https://api.crossref.org/works/10.1016/j.seta.2020.100921"
  ```
- 中欄：Semantic Scholar API 呼叫 + Abstract 擷取
  ```bash
  curl "https://api.semanticscholar.org/graph/v1/paper/
        DOI:10.1016/j.seta.2020.100921
        ?fields=abstract,citationCount"
  ```
- 右欄：OpenAlex API + OA 狀態查詢
- 底部：Python 批次腳本概念（for doi in dois: verify(doi)）

**Slide 14 [新增]** — 批次匯入 Zotero：四種方法
- 方式 1：Zotero Magic Wand（貼 DOI 列表）
- 方式 2：Zotero Connector（瀏覽器批次儲存）
- 方式 3：BibTeX 匯入（references.bib → Zotero）
- 方式 4：Zotero API（程式化，pyzotero 範例）
- 附截圖：Zotero 介面 + DOI 匯入操作

**Slide 15 [保留+更新]** — 文獻整理系統：AI 筆記轉換工作流
- 保留 PDF → 結構化摘要 → 筆記標準化 → 知識圖譜
- 更新筆記範本為 Obsidian Markdown 格式（含 YAML frontmatter）

**Slide 16 [新增]** — 文獻筆記卡 + Obsidian 知識圖譜
- 左側：Obsidian 筆記卡範例
  ```markdown
  ---
  tags: [NILM, training-free]
  doi: "10.1016/..."
  year: 2021
  relevance: 4/5
  cite_in: [Introduction, Related Work]
  ---
  # Eskander2021 - Industrial NILM Review
  ## Core Contribution
  → ...
  ## Link to My Research
  → 支撐 C1 → [[Research_Gap_Analysis]]
  ## Related Papers
  → [[Hart1992]] [[Kelly2015]]
  ```
- 右側：Obsidian Graph View 截圖概念圖
  - 節點 = 文獻卡
  - 連線 = `[[雙向連結]]`
  - 聚類 = 研究主題群
  - 孤立節點 = 可能遺漏的文獻
  - 顏色 = tag 分類

**Slide 17 [保留]** — Abstract 捕捉技術
- 5 維度快速評估（相關性/新穎性/影響力/可比較性/引用價值）

**Slide 18 [新增]** — BibTeX 引用管理 + bib-manager Skill
- DOI → BibTeX 自動生成（CrossRef API）
- bib-manager skill 防呆機制：
  - 重複條目偵測
  - 格式一致性檢查
  - 幽靈引用警告
  - CrossRef 交叉驗證
- 黃金規則：**絕不添加 references.bib 中不存在的引用**
- 案例：43 篇引用管理

**Slide 19 [新增]** — Research Gap 識別 + Literature Synthesis
- `literature-synthesis` skill 示範
- 文獻分類矩陣（方法 × 數據集 × 評估指標）
- `/analyze-literature` command Demo
- Gap 識別三層法：現有方法 → 限制 → 機會

**Slide 20 [新增]** — 創新性定位 + 期刊匹配（Phase 3 導入）
- `innovation-positioning` skill 三層框架
- 避免的陷阱："Inspired by...", "We improve..."
- 期刊匹配 6 維度（含主編偏好、近期收錄）
- 案例：10 期刊加權評分 → 選定 SETA

---

### Session 2 延伸 + 自動化入門（Slides 21-23）

**Slide 21 [保留]** — 自動化工具入門：Google Apps Script
- 批次 PDF 分析 / Abstract 爬取 / 引用轉換

**Slide 22 [更新]** — Claude Code 初體驗
- CLAUDE.md = 「AI 的工作手冊」
- Skills / Agents / Commands 架構概覽
- 示範：用 Claude Code 批次驗證 DOI

**Slide 23 [更新]** — Day 1 實作練習 & 回顧
- 實作任務（升級版）：
  1. CARE Prompt × 3 + 多輪對話 × 5 輪
  2. 用 AI 產出 10 個種子 DOI
  3. 用 CrossRef API 驗證 DOI 正確性
  4. 建立 5 篇 Obsidian 文獻筆記卡
  5. 建立 references.bib（至少 5 篇驗證過的引用）
- 核心技能 checklist（10 項）

---

### Day 1 過渡頁（Slide 24）

**Slide 24 [新增]** — AI 工具生態系預覽：Day 2 的武器庫
- 24 Skills 圖標牆（4 類）
- 8 Agents 專家團隊
- 5 Commands + 5 APIs
- 預告：「明天你將擁有一個完整的 AI 研究團隊」

---

## DAY 2: AI 研究進階（L2D1 中階入門）

### 開場區（Slides 25-29）

**Slide 25 [保留]** — Day 2 封面頁

**Slide 26 [新增]** — 從「AI 助教」到「AI 研究團隊」
- Day 1：你 + 1 個 AI 助教
- Day 2：你 + 8 個專家 Agent（角色卡展示）

**Slide 27 [新增]** — 5 Commands：一鍵啟動 AI 工作流
- `/review-paper` → citation → data → reviewer
- `/analyze-literature` → literature-researcher
- `/analyze-experiment` → data → stats
- `/prepare-submission` → reviewer → submission
- `/respond-reviewers` → submission-helper
- 示範：一行指令，三個 Agent 協作

**Slide 28 [新增]** — CLAUDE.md：AI 的工作手冊
- 概念：「SOP 文件，讓 AI 嚴格遵守你的規則」
- 關鍵區塊：引用原則 / 檔案操作 / 驗證原則 / 目錄結構

**Slide 29 [新增]** — 主編分析方法：被忽略的投稿關鍵
- 主編任期 3 年，影響收錄方向
- 分析步驟：
  1. 期刊官網 → Editorial Board
  2. Google Scholar 查主編近 5 年發表
  3. 分析 Editorial / Guest Editorial 內容
  4. 近 2 年收錄文章 topic clustering
- 新主編上任 → 可能更開放新方向
- Special Issue 徵稿 → 主題契合度高
- 底部：`journal-fit` skill 支援此分析

---

### Session 3：論文架構 + 實驗設計（Slides 30-37）

**Slide 30 [更新]** — Session 3：IMRaD 標準論文架構
- 替換原本的五章結構為 IMRaD 詳細展開
  ```
  I  Introduction: 背景→問題→目的→貢獻聲明
  M  Methods: 問題定義→架構→演算法→物理約束
  R  Results: 設置→主結果→Ablation→統計→錯誤分析
  aD Discussion: 分析→邊界→限制→未來
  ```

**Slide 31 [新增]** — 從 Markdown 到 QMD：無痛轉換
- 左側：Markdown 初稿（簡單格式）
- 右側：加上 YAML 檔頭 → 即為 QMD
- 轉換成本：5 分鐘
- 效果差異：MD（純文字）vs QMD（期刊格式 PDF）

**Slide 32 [新增]** — YAML 檔頭詳解：期刊格式的靈魂
- 完整 YAML 範例（SETA/Elsevier 配置）
  ```yaml
  title: "..."
  author:
    - name: ...
      affiliations: ...
  abstract: |
    ...
  bibliography: references.bib
  csl: elsevier-vancouver-author-date.csl
  format:
    elsevier-pdf:
      keep-tex: true
      journal:
        name: SETA
        cite-style: authoryear
      classoption: [authoryear, preprint, review, 12pt]
      geometry: [margin=3cm, a4paper]
  ```
- 不同期刊的 format 對照表（Elsevier / IEEE / Springer / MDPI）
- `quarto render paper.qmd` → PDF + TeX

**Slide 33 [更新]** — AI 輔助實驗設計
- 保留六要素
- 新增：`experiment-tracker` + `protocol-enforcer` + `ablation-min-proof`
- 案例：9 設備 × 3 數據集實驗方案

**Slide 34 [新增]** — IDE 工作流 + 三層執行環境
- VS Code 配置：
  - Python + Jupyter Extension
  - Quarto Extension（即時預覽）
  - Remote-SSH Extension（連遠端 GPU）
  - Claude Code CLI
- 三層環境表格：
  | 環境 | GPU | 用途 | 費用 |
  |------|-----|------|------|
  | 本地 MacBook | 無 | 開發/調試 | 免費 |
  | Google Colab | T4/A100 | 原型驗證 | 免費~$10/月 |
  | 遠端 3090 | RTX 3090 | 完整實驗 | 電費 |

**Slide 35 [新增]** — Colab + 遠端 3090 實戰
- Colab 快速上手：掛載 Drive + pip install + 載入數據
- 遠端 3090 標準流程：
  ```bash
  ssh ac-3090
  source ~/miniconda3/etc/profile.d/conda.sh
  conda activate gpu
  PYTHONUNBUFFERED=1 nohup python -u train.py > exp.log 2>&1 &
  nvidia-smi  # 1 分鐘內檢查 GPU > 60%
  ```

**Slide 36 [新增]** — Telegram Bot 實驗監控
- 三層監控系統圖
  - Level 1（即時）：1 分鐘 GPU、5 分鐘日誌
  - Level 2（定期）：每 15 分鐘進程+GPU
  - Level 3（異常）：進程消失/日誌停更/錯誤
- TG 通知範例截圖（實驗異常 → 手機收到通知）
- 指令列表：`/check` `/all` `/log`

**Slide 37 [保留+更新]** — 數據彙整策略
- 保留可重現性設計
- 新增：seed=42 規範、JSON 可序列化、metric-audit

---

### Session 4：QMD + BibTeX 撰寫（Slides 38-44）

**Slide 38 [保留]** — Session 4：QMD + BibTeX 論文寫作系統

**Slide 39 [保留]** — BibTeX 引用管理
- DOI → BibTeX → 驗證 → 重複偵測

**Slide 40 [保留]** — AI 輔助學術寫作
- Introduction / Related Work / Methodology / Experiments 策略

**Slide 41 [新增]** — 轉投策略：切中熱點與主編偏好
- Step 1: 抓取目標期刊近 100 篇標題 → AI topic clustering
- Step 2: 分析主編研究偏好（Google Scholar + Editorial）
- Step 3: 調整 Title / Abstract / Introduction 第一段 / Discussion
- Step 4: 格式轉換（改 YAML format + CSL）→ 重新 render
- 案例：Energy & Buildings → SETA 的調整策略

**Slide 42 [新增]** — SVG 向量圖製作 + QMD→TeX 快速轉換
- 為什麼用 SVG？（無限放大、可編輯、期刊接受）
- Python → SVG/PDF/PNG 三格式輸出程式碼
- Inkscape 後處理（SVG → PDF/EPS）
- QMD 引用：`![caption](fig.pdf){#fig-label width="100%"}`
- `quarto render --keep-tex` → 直接得到 .tex 提交 Overleaf

**Slide 43 [新增]** — Skill 驅動的自動化統計驗證
- 流程圖：
  ```
  /analyze-experiment results.json
  → data-validator (品質) → stats-validator (統計)
  → statistical-validation skill (P0-P3 分級)
  → 論文用文本輸出
  ```
- 數據一致性三角驗證：Text ↔ Table ↔ Figure
- 案例：發現 F1=0.820 vs 0.8488 不一致

**Slide 44 [新增]** — Claude Code 深度體驗
- Skills 觸發機制：說「統計」→ 啟動 statistical-validation
- Agents 分工：獨立 context + 工具權限隔離
- 示範 3 個 Command：
  1. `/review-paper paper.qmd "SETA"` → 七維度報告
  2. `/analyze-experiment results.csv` → 統計分析
  3. `/prepare-submission "SETA"` → Cover Letter

---

### Session 5：品質保證 + 投稿（Slides 45-54）

**Slide 45 [新增]** — 七維度論文分析框架
- 7 維度各一圖標 + 權重 + 評分
- paper-review-skill 完整示範

**Slide 46 [新增]** — P0-P3 品質管控系統
- 四級問題分類（顏色標記 + 案例）
- mvp-gatekeeper skill：「能不能投稿？」
- 案例：2 P0 + 3 P1 + 3 P2 → 修復後可投

**Slide 47 [新增]** — 平行審查：Claude × ChatGPT × Gemini
- 流程圖：
  ```
  論文 → Claude（七維度+統計）
       → ChatGPT（結構+寫作）
       → Gemini（事實+引用）
       → 彙整（三者共識=高信度問題）
  ```
- 各模型審稿偏好對比表
- Claude 獨特優勢：Skills 系統 + `/review-paper`

**Slide 48 [保留+更新]** — 多維度論文分析（更新為七維度）

**Slide 49 [保留+更新]** — 文獻確認與比對
- 三層引用驗證 + citation-checker agent
- 新增：figure-table-checker + evidence-indexer

**Slide 50 [新增]** — Reviewer 預測與應對策略
- AI 模擬 4 個常見問題 + 回答模板
- rebuttal-matrix skill 追蹤

**Slide 51 [新增]** — 投稿全流程：Cover Letter → Rebuttal
- submission-helper agent
- Cover Letter 5 段式（引用目標期刊近期文章）
- submission-bundle 打包清單
- Suggested Reviewers 從 references.bib 選

**Slide 52 [保留+更新]** — 期刊選擇與投稿策略
- 加入 6 維度評估（含主編+近期收錄）
- 加入 journal-fit skill

**Slide 53 [新增]** — 系統部署：帶走你的 AI 研究團隊
- research-workspace.zip 安裝（3 步）
- CLAUDE.md 客製化
- Skills / Agents 新增
- TG Bot 遠端設定（可選）
- QR Code 下載

---

### 收尾區（Slides 54-55）

**Slide 54 [更新]** — 完整 AI 論文研究工作流程
- 11 Phase + 工具標記 + API 標記
- AI 參與度 70-75%
- 下一步學習路徑

**Slide 55 [保留]** — 謝謝大家
- 核心理念 + QR Code

---

## 簡報頁數統計

| 區段 | 頁數 | 保留 | 更新 | 新增 |
|------|------|------|------|------|
| 開場 (1-4) | 4 | 1 | 2 | 1 |
| S1 概念探索 (5-9) | 5 | 4 | 0 | 1 |
| S2 文獻調研 (10-20) | 11 | 2 | 1 | 8 |
| 自動化+回顧 (21-23) | 3 | 1 | 2 | 0 |
| Day 1→2 過渡 (24) | 1 | 0 | 0 | 1 |
| Day 2 開場 (25-29) | 5 | 1 | 0 | 4 |
| S3 架構+實驗 (30-37) | 8 | 0 | 2 | 6 |
| S4 QMD+撰寫 (38-44) | 7 | 3 | 0 | 4 |
| S5 品質+投稿 (45-53) | 9 | 0 | 2 | 7 |
| 收尾 (54-55) | 2 | 1 | 1 | 0 |
| **合計** | **55** | **13** | **10** | **32** |

---

## 各 Session 核心教學重點對照

| Session | 核心重點 | 實戰亮點 | 實作 |
|---------|---------|---------|------|
| S1 概念探索 | CARE 框架、多輪對話 | NILM+LLM 案例 | Prompt 撰寫 |
| S2 文獻調研 | **種子DOI→API驗證→Zotero→Obsidian** | 4 個 API 實戰 | DOI 驗證 + 筆記卡 |
| S3 架構+實驗 | **IMRaD + YAML + IDE + GPU** | QMD 轉換 + 遠端 3090 | QMD 骨架建立 |
| S4 撰寫+分析 | **轉投策略 + SVG + Skill 驗證** | 平行統計 + 圖表產出 | QMD 撰寫 |
| S5 品質+投稿 | **平行審查 + P0-P3 + 主編分析** | Claude×ChatGPT×Gemini | 審查報告 |

---

## 新增內容 vs 原始簡報差異總結

| 主題 | 原始版本 | v2.0 升級 |
|------|---------|----------|
| 文獻驗證 | 「用 AI 搜尋文獻」 | **種子DOI → CrossRef/Semantic Scholar/OpenAlex API 多重驗證** |
| 文獻整理 | 標準化筆記模板 | **Obsidian 筆記卡 + Graph View 知識圖譜** |
| 文獻匯入 | 手動管理 | **Zotero 批次匯入（4 種方式）** |
| 期刊選擇 | Scope + IF | **主編分析 + 近 2 年收錄趨勢 + 任期判斷** |
| 論文架構 | 五章結構 | **IMRaD 標準 + MD→QMD 轉換流程** |
| 格式配置 | QMD 概念 | **YAML 檔頭完整範例 + 4 種期刊對照** |
| 實驗執行 | 概念提及 | **VS Code IDE + Colab + 遠端 3090 完整流程** |
| 實驗監控 | 無 | **TG Bot 三層監控 + 異常通知** |
| 統計驗證 | 提到但不深入 | **Skill 自動化驗證 + P0-P3 分級 + 數據一致性檢查** |
| 論文轉投 | 無 | **主編偏好分析 + 近期熱點 + Title/Abstract 調整策略** |
| 圖表製作 | 概念提及 | **SVG 向量圖 + Inkscape + 多格式輸出** |
| QMD→TeX | 無 | **keep-tex 配置 + Overleaf 提交** |
| 品質審查 | 6 維度 | **7 維度 + P0-P3 + 平行審查（Claude×ChatGPT×Gemini）** |
| 投稿材料 | Cover Letter 概念 | **10 項素材清單 + 引用目標期刊文章策略** |
| 系統部署 | 無 | **research-workspace.zip 帶走** |
