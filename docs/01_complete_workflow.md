# AI-Assisted Research Paper Complete Workflow
# AI 輔助學術論文完整工作流程（v2.0 增補版）

> 從概念發想到期刊投稿的全流程整理
> 基於 NILM+LLM 論文（SETA 投稿）實際經驗
> v2.0: 補充文獻正確性驗證、Obsidian 知識圖譜、主編分析、IMRaD 架構、
>       MD→QMD 轉換、遠端 GPU 訓練、TG Bot 監控、平行審查、SVG 向量圖等

---

## 全流程總覽（11 個階段）

```
Phase 1: 概念探索 ──→ Phase 2: 文獻調研 ──→ Phase 3: 研究定位
    │                     │                     │
    ▼                     ▼                     ▼
  人+AI 對話           種子DOI→API驗證       Research Gap
  方向確認             →Zotero→Obsidian      主編偏好分析
    │                     │                     │
    ▼                     ▼                     ▼
Phase 4: 論文架構 ──→ Phase 5: 實驗設計 ──→ Phase 6: 實驗執行
    │                     │                     │
    ▼                     ▼                     ▼
  IMRaD 設計           數據/腳本設計          3090/Colab 遠端
  MD→QMD→YAML          IDE 工作流             TG Bot 監控
    │                     │                     │
    ▼                     ▼                     ▼
Phase 7: 數據分析 ──→ Phase 8: 論文撰寫 ──→ Phase 9: 品質審查
    │                     │                     │
    ▼                     ▼                     ▼
  Skill自動驗證        轉投策略+主編匹配     平行審查
  數據一致性           QMD→TeX+SVG向量圖     Claude×ChatGPT
    │                                          │
    ▼                                          ▼
Phase 10: 投稿準備 ──→ [投稿] ──→ Phase 11: 審稿回覆
```

---

## Phase 1: 概念探索與方向確認

### 做了什麼
- 與 AI 進行開放式討論，探索研究方向
- 從 NILM（非侵入式負載監測）出發，討論 LLM 在工業能源的應用可能
- 確認 "Training-Free + LLM-guided + Physics-bounded" 三大貢獻點

### 使用的工具
| 工具 | 用途 |
|------|------|
| Claude 對話 | 腦力激盪、方向探索 |
| Extended Thinking | 深度分析可行性（think hard / ultrathink） |
| ChatGPT / Gemini | 多模型交叉驗證方向可行性 |

### 產出
- 研究方向確認
- 初步貢獻點定義
- 可行性評估

---

## Phase 2: 文獻調研與整理（大幅增補）

### 2.1 種子 DOI 生成與 AI 文獻搜尋

**第一步：用 AI 產出種子 DOI 清單**

```
Prompt 範例：
「你是 NILM 領域的資深研究者。請列出 training-free NILM、
LLM for energy、physics-informed load monitoring 三個方向
近 5 年最重要的 20 篇論文，包含 DOI。」
```

- AI 產出的 DOI 清單是「候選清單」，**不能直接信任**
- 必須經過多重 API 驗證才能確認正確性

### 2.2 多重 API 驗證流程（文獻正確性的核心）

```
種子 DOI（AI 產出）
    │
    ▼
┌─────────────────────────────────────────────────┐
│  Step 1: CrossRef API 驗證                        │
│  https://api.crossref.org/works/{DOI}             │
│  → 確認 DOI 存在、取得正式 title/author/year       │
│  → 比對 AI 給的 metadata 是否正確                  │
└───────────────────────┬─────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────┐
│  Step 2: Semantic Scholar API 取 Abstract          │
│  https://api.semanticscholar.org/graph/v1/paper/  │
│  DOI:{doi}?fields=abstract,citationCount,         │
│  referenceCount,fieldsOfStudy                     │
│  → 取得 Abstract 全文                              │
│  → 取得引用數、領域分類                             │
└───────────────────────┬─────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────┐
│  Step 3: OpenAlex API 補充驗證                     │
│  https://api.openalex.org/works/doi:{DOI}         │
│  → 取得 Open Access 狀態                           │
│  → 取得作者機構資訊                                 │
│  → 取得概念標籤（Concepts）                         │
└───────────────────────┬─────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────┐
│  Step 4: Abstract 語義比對                         │
│  用 AI 比對 Abstract 內容與你的研究相關性            │
│  → 1-5 分相關性評分                                │
│  → 標記應引用的章節（Introduction/Related Work/     │
│    Discussion）                                    │
└───────────────────────┬─────────────────────────┘
                        ▼
    確認清單 → 批次匯入 Zotero
```

### 2.3 批次匯入 Zotero

- **方式 1**：Zotero Magic Wand — 貼上 DOI 清單自動抓取
- **方式 2**：Zotero Connector — 從瀏覽器批次儲存
- **方式 3**：BibTeX 匯入 — 從 `references.bib` 直接匯入
- **方式 4**：Zotero API — 程式化批次匯入

```python
# Zotero API 批次匯入範例
from pyzotero import zotero
zot = zotero.Zotero(library_id, 'user', api_key)
# 從 DOI 清單批次建立條目
for doi in verified_dois:
    item = zot.item_template('journalArticle')
    item['DOI'] = doi
    zot.create_items([item])
```

### 2.4 文獻筆記卡 → Obsidian 知識圖譜

**筆記卡格式（Obsidian Markdown）**：

```markdown
---
tags: [NILM, training-free, industrial]
doi: "10.1016/j.seta.2020.100921"
year: 2021
cited_by: 45
relevance: 4/5
cite_in: [Introduction, Related Work]
---

# Eskander2021 - Industrial NILM Review

## Core Contribution
→ 首次系統性評估工業場域 NILM 的挑戰

## Method
→ Survey + Taxonomy

## Key Findings
→ 工業負載多樣性遠高於住宅場景

## Limitations
→ 未涵蓋 LLM/AI 輔助方法

## Link to My Research
→ 支撐 C1（Training-free 的必要性）
→ [[Research_Gap_Analysis]]

## Related Papers
→ [[Hart1992]] [[Kelly2015]] [[Tanoni2024]]
```

**Obsidian 連結圖（Graph View）效果**：
- 節點 = 每篇文獻筆記卡
- 連線 = `[[雙向連結]]`
- 聚類 = 自動呈現研究主題群
- 孤立節點 = 可能遺漏的重要文獻
- 顏色 = 依 tag 區分（方法類 / 數據類 / 理論類）

### 使用的工具與 API

| 工具/API | 用途 |
|----------|------|
| Claude / ChatGPT | 產出種子 DOI 清單 |
| **CrossRef API** | DOI 存在性驗證 + metadata 取得 |
| **Semantic Scholar API** | Abstract 取得 + 引用數 + 領域分類 |
| **OpenAlex API** | OA 狀態 + 機構 + Concepts 標籤 |
| **Unpaywall API** | 免費 PDF 連結取得 |
| `literature-researcher` agent | 文獻分析、Gap 識別 |
| `literature-synthesis` skill | 文獻綜述撰寫 |
| `bib-manager` skill | BibTeX 管理與防呆 |
| `download_papers.sh` | 批量下載 PDF（arXiv → Unpaywall → Publisher） |
| `/analyze-literature` command | 一鍵文獻分析 |
| **Zotero + Zotero Connector** | 文獻管理 + PDF 儲存 |
| **Obsidian + Graph View** | 知識圖譜可視化 |

### 產出
- 經 API 多重驗證的文獻清單（排除 AI 幻覺引用）
- `references.bib` — 43 篇完整引用（每篇經 CrossRef 驗證）
- `01_literature/papers/downloaded/` — 13 篇已下載 PDF
- Obsidian 文獻知識圖譜（含連結關係）
- Research Gap 分析報告

---

## Phase 3: 研究定位與創新性論述（增補主編分析）

### 3.1 Research Gap 識別

使用 `innovation-positioning` skill 的三層框架：

```
Layer 1: 問題獨特性 → 為什麼現有方法從根本上無法解決？
Layer 2: 方法論創新 → 你的方法為什麼能解決？
Layer 3: 驗證充分性 → 證明你確實解決了
```

避免的陷阱：
- ❌ "Inspired by..." → 暗示衍生研究
- ❌ "We improve X by..." → 暗示增量工作
- ❌ "Few studies..." → 不構成必要性

### 3.2 期刊匹配度分析（不只看 Scope）

**完整期刊評估框架（6 維度）**：

| 維度 | 權重 | 評估內容 |
|------|------|---------|
| Scope 契合度 | 35% | Aims & Scope 與研究主題的重疊 |
| Impact Factor | 15% | JCR 排名、CiteScore |
| 主編研究偏好 | 20% | **主編的研究領域、發表傾向、近期 Editorial** |
| 近期收錄主題 | 15% | **近 2 年該期刊發表的相關主題分析** |
| 審稿週期 | 10% | First Decision 時間 |
| OA/APC 政策 | 5% | 費用與 OA 選項 |

### 3.3 主編分析方法（關鍵新增）

**為什麼主編很重要？**
- 主編任期通常 3 年一屆，影響期刊收錄方向
- 主編的研究背景決定「什麼樣的論文容易過 desk review」
- 新主編上任往往帶來 scope 微調

**主編分析步驟**：

```
Step 1: 找到主編
  → 期刊官網 Editorial Board 頁面
  → 記錄 Editor-in-Chief + Associate Editors

Step 2: 分析主編研究領域
  → Google Scholar 查主編近 5 年發表
  → 看主編的 h-index 和研究關鍵詞
  → 用 AI 分析：「這位主編偏好什麼類型的研究？」

Step 3: 分析近期收錄趨勢
  → 抓取該期刊近 2 年所有文章標題
  → 用 AI 做 topic clustering
  → 識別「熱門主題」和「冷門但在增長的主題」

Step 4: 判斷時機
  → 新主編剛上任 → 可能更開放接受新方向
  → 期刊剛發 Special Issue 徵稿 → 主題契合度高
  → 期刊 IF 剛上升 → 審稿可能更嚴格
```

**案例：SETA 期刊選擇過程**
- 初始候選：10 個期刊加權評分
- Applied Energy (91分) > IEEE TII (89分) > TSG (87分)
- 最終選 SETA：scope 完美契合 + 審稿速度快 + 近期收錄多篇 NILM

### 使用的工具
| 工具/Skill | 用途 |
|------------|------|
| `innovation-positioning` skill | 創新性定位策略 |
| `research-contract` skill | 研究契約與承諾追蹤 |
| `journal-fit` skill | 期刊適配度分析（含 scope 分析） |
| `baseline-min-set` skill | 基線最小集驗證 |
| Google Scholar | 主編研究背景調查 |
| 期刊官網 + AI 分析 | 近期收錄主題趨勢 |

### 產出
- 期刊適配度分析報告（含主編分析）
- 創新性定位文件
- 研究契約定義

---

## Phase 4: 論文架構設計（增補 IMRaD + MD→QMD）

### 4.1 IMRaD 標準架構設計

```
I  — Introduction（引言）
     ├── 研究背景（大 → 小，漏斗式）
     ├── 問題陳述（現有方法的不足）
     ├── 研究目的（你要解決什麼）
     └── 貢獻聲明（3-4 點明確貢獻）

M  — Methods（方法）
     ├── 問題定義（數學/形式化描述）
     ├── 系統架構（框架圖 fig_framework）
     ├── 核心演算法（步驟化描述）
     └── 物理約束設計（銘牌功率上下界）

R  — Results（結果）
     ├── 實驗設置（數據集、參數、環境）
     ├── 主要結果（Performance Table + Figure）
     ├── Ablation Study（組件貢獻驗證）
     ├── 統計驗證（Bootstrap CI、效果量）
     └── 錯誤分析（Error Pattern Heatmap）

aD — and Discussion（討論）
     ├── 結果分析（為什麼有效/失敗）
     ├── 適用性邊界（什麼情況不適用）
     ├── 局限性（誠實承認）
     └── 未來展望
```

### 4.2 從 Markdown 到 QMD 的轉換流程

**為什麼先寫 MD 再轉 QMD？**
- MD 寫作門檻低，適合快速草稿
- QMD 加上 YAML 檔頭就能編譯為期刊格式
- 轉換成本極低，但格式效果差異巨大

**Step 1: 用 Markdown 寫初稿**
```markdown
# Introduction

Non-Intrusive Load Monitoring (NILM) enables...

## Related Work

@hart1992 first proposed...
```

**Step 2: 加上 YAML 檔頭轉為 QMD**

```yaml
---
title: "Deployable Energy Disaggregation for Sustainable
        Industrial Energy Management"
author:
  - name: Chung-Kuang Chen
    email: alan.chen75@gmail.com
    attributes:
      corresponding: true
    affiliations:
      - id: ntust
        name: National Taiwan University of Science and Technology
        department: Graduate Institute of Intelligent Manufacturing
        city: Taipei City
        country: Taiwan

abstract: |
  Device-level energy visibility is essential for industrial
  measurement and verification (M&V)...

keywords:
  - Energy disaggregation
  - Industrial energy management
  - Training-free deployment

bibliography: references.bib
csl: elsevier-vancouver-author-date.csl
number-sections: true

format:
  elsevier-pdf:
    pdf-engine: pdflatex
    keep-tex: true          # 保留 .tex 方便檢查
    journal:
      name: Sustainable Energy Technologies and Assessments
      formatting: preprint
      cite-style: authoryear
    classoption:
      - authoryear
      - preprint
      - review
      - 12pt
    geometry:
      - margin=3cm
      - a4paper
    fig-dpi: 500

    include-in-header:
      text: |
        \usepackage{lineno}
        \linenumbers              # 行號（review 模式必備）
        \usepackage{setspace}
        \usepackage{amssymb}
---
```

**Step 3: 編譯**
```bash
quarto render paper.qmd              # → PDF
quarto render paper.qmd --to docx    # → Word
quarto render paper.qmd --to html    # → 預覽
```

**常見期刊格式配置對照**：

| 期刊 | format | classoption | csl |
|------|--------|------------|-----|
| Elsevier (SETA) | `elsevier-pdf` | `authoryear, preprint` | `elsevier-vancouver-author-date.csl` |
| IEEE Trans | `ieee-pdf` | `journal` | `ieee.csl` |
| Springer | `springer-pdf` | — | `springer-basic-author-date.csl` |
| MDPI | `mdpi-pdf` | — | `mdpi.csl` |

### 使用的工具
| 工具/Skill | 用途 |
|------------|------|
| `academic-writing` skill | IMRaD 結構規範 |
| `evidence-indexer` skill | 圖表與 claim 追溯 |
| `figure-table-checker` skill | 圖表規劃 |
| Quarto (.qmd) | MD → PDF/DOCX/TeX 轉換 |
| CSL 檔案 | 引用格式樣式 |

### 產出
- `paper_v06_0121.qmd` — 含完整 YAML 配置
- 圖表清單（PAPER_CHANGELOG.md）
- Elsevier/SETA 格式配置

---

## Phase 5: 實驗設計（增補 IDE + 遠端 + Colab）

### 5.1 數據集準備與腳本設計

```
data/
├── IMDELD/
│   ├── _preprocessed/
│   │   ├── aggregate.csv      # 聚合功率
│   │   └── equipment.csv      # 設備標籤
│   └── v4_devices.json        # 設備配置
├── Case1/
│   └── ...
└── WELTRON/
    └── ...
```

**腳本設計原則**：
- 統一 config.py / config.yaml 管理所有參數
- 隨機種子固定：`seed=42`
- 所有路徑用 config 變數，不硬編碼
- 結果輸出為 JSON（可序列化）

### 5.2 IDE 工作流設計

**本地開發（VS Code）**：
```
VS Code
├── Python Extension + Jupyter
├── Quarto Extension（論文預覽）
├── Remote-SSH Extension（連遠端 GPU）
├── GitHub Copilot（程式碼輔助）
└── Claude Code CLI（AI 研究助手）
```

**三層執行環境**：

| 環境 | 用途 | GPU | 費用 |
|------|------|-----|------|
| 本地 MacBook | 開發/調試/小規模測試 | 無 | 免費 |
| Google Colab | 中型實驗/原型驗證 | T4/A100 | 免費-$10/月 |
| 遠端 3090 (ac-3090) | 完整實驗/長時間訓練 | RTX 3090 | 電費 |

**Colab 使用技巧**：
```python
# Colab 掛載 Google Drive（持久化）
from google.colab import drive
drive.mount('/content/drive')

# 安裝依賴
!pip install -q torch torchvision scipy

# 從 Drive 載入數據
import pandas as pd
df = pd.read_csv('/content/drive/MyDrive/data/aggregate.csv')
```

**遠端 3090 標準流程**：
```bash
# 1. SSH 連線 + Conda 環境
ssh ac-3090
source ~/miniconda3/etc/profile.d/conda.sh
conda activate gpu

# 2. 上傳代碼（或 git pull）
cd ~/experiments/nilm-llm
git pull origin main

# 3. 持久化執行
PYTHONUNBUFFERED=1 nohup python -u train.py \
  --config config.yaml \
  --seed 42 \
  > exp_$(date +%Y%m%d_%H%M%S).log 2>&1 &

# 4. 確認 GPU 使用（1 分鐘內必須檢查）
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv
```

### 使用的工具
| 工具/Skill | 用途 |
|------------|------|
| `experiment-tracker` skill | 實驗追蹤管理 |
| `experiment-validator` skill | 實驗執行前驗證 |
| `protocol-enforcer` skill | 協議一致性檢查 |
| `ablation-min-proof` skill | Ablation 最小證明設計 |
| `split-leakage-audit` skill | 數據洩漏檢測 |
| `metric-audit` skill | 指標定義審計 |
| VS Code + Remote-SSH | IDE 開發環境 |
| Google Colab | 雲端 GPU 訓練 |
| ac-3090 (RTX 3090) | 遠端 GPU 訓練 |

---

## Phase 6: 實驗執行與監控（增補 TG Bot 細節）

### 6.1 遠端實驗執行

```bash
# 標準遠端執行模板
ssh ac-3090 "source ~/miniconda3/etc/profile.d/conda.sh && \
             conda activate gpu && \
             cd ~/experiments && \
             PYTHONUNBUFFERED=1 nohup python -u experiment.py \
             > exp.log 2>&1 &"
```

### 6.2 Telegram Bot 監控串接

**三層監控系統**：

```
Level 1（即時，前 5 分鐘）：
  ├── 啟動後 1 分鐘：檢查 GPU 使用率 > 60%
  └── 啟動後 5 分鐘：檢查日誌輸出正常

Level 2（定期，每 15 分鐘）：
  ├── 檢查進程存在（ps aux | grep python）
  ├── 檢查 GPU 使用率
  └── 檢查日誌更新時間

Level 3（異常偵測 → TG 通知）：
  ├── 進程消失 → 立即通知
  ├── 日誌 10 分鐘未更新 → 警告
  └── 錯誤訊息出現 → 立即通知
```

**TG Bot 指令**：

| 指令 | 功能 |
|------|------|
| `/check` | GPU 狀態 + 進程狀態 |
| `/all` | 完整效能報告（CPU/RAM/GPU/Disk） |
| `/log` | 顯示最新 10 行日誌 |
| `?` | 幫助列表 |

**自動通知範例**：
```
🔴 實驗異常通知
━━━━━━━━━━━━━━
機器: ac-3090
狀態: Python 進程已消失
最後日誌: epoch 45/100, loss=0.0342
時間: 2026-01-15 03:45:22
━━━━━━━━━━━━━━
建議: 檢查 OOM 或 CUDA error
```

### 使用的工具
| 工具/Skill | 用途 |
|------------|------|
| `gpu-monitor` skill | GPU 環境監控 |
| SSH + nohup / tmux | 遠端持久化執行 |
| Telegram Bot (tg-monitor-bot) | 三層監控 + 異常通知 |
| MCP `check_gpu_status` | GPU 狀態查詢 |
| MCP `send_telegram` | 程式化通知發送 |
| `nvidia-smi` | GPU 即時狀態 |

---

## Phase 7: 數據分析與統計驗證（增補 Skill 自動化）

### 7.1 Skill 驅動的自動化驗證流程

```
/analyze-experiment results.json
    │
    ▼
┌─ data-validator agent ─────────────────┐
│  ✓ JSON 可讀性                          │
│  ✓ 指標範圍合理（無 NaN/inf）            │
│  ✓ 與基線比較（99.72% / 97.55%）        │
│  ✓ 過擬合檢測（train-test gap < 10%）   │
└────────────────────┬───────────────────┘
                     ▼
┌─ stats-validator agent ────────────────┐
│  ✓ Bootstrap CI（n=10,000）             │
│  ✓ Kruskal-Wallis（跨數據集）           │
│  ✓ Mann-Whitney U（VFD vs DOL）        │
│  ✓ Cohen's d 效果量                     │
│  ✓ 功效分析（Power Analysis）           │
│  ✓ 配對 t-test（低解析度 vs 原始）      │
└────────────────────┬───────────────────┘
                     ▼
┌─ statistical-validation skill ─────────┐
│  → 產出 P0-P3 問題分級                   │
│  → 產出可直接引用的論文文本               │
│  → 產出修改檢查清單                      │
└────────────────────────────────────────┘
```

### 7.2 數據一致性檢查

- **Text ↔ Table ↔ Figure 三角驗證**：
  - 論文文字中提到的數字 = 表格中的數字 = 圖表中的數字
  - `figure-table-checker` skill 自動掃描
  - 案例：發現 F1=0.820 vs 0.8488 不一致 → P0 致命問題

- **結果 → 論文的數字流**：
  ```
  results/*.json → EXPERIMENT_RESULTS.md（唯一真相來源）
      → paper.qmd（手動提取，但必須一致）
      → grep '(舊數字)' paper.qmd → 應無結果
  ```

### 使用的工具
| 工具/Skill | 用途 |
|------------|------|
| `stats-validator` agent | 統計檢驗執行 |
| `statistical-validation` skill | 統計方法選擇 + P0-P3 分級 |
| `data-validator` agent | 數據品質 + 過擬合檢測 |
| `metric-audit` skill | 指標定義一致性審計 |
| `figure-table-checker` skill | Text-Table-Figure 三角驗證 |
| `evidence-indexer` skill | Claim → Evidence 追溯鏈 |
| `/analyze-experiment` command | 一鍵實驗分析 |

---

## Phase 8: 論文撰寫（增補轉投策略 + SVG 圖表）

### 8.1 轉投期刊策略：切中熱點與主編偏好

**當需要轉投時的標準流程**：

```
Step 1: 分析目標期刊近 2 年收錄文章
  → 抓取期刊最近 100 篇文章標題
  → 用 AI 做 topic clustering
  → 識別熱門主題、上升主題、冷門主題

Step 2: 分析主編偏好
  → Google Scholar 查主編近期發表
  → 看 Editorial / Guest Editorial 內容
  → 識別主編關注的方向

Step 3: 調整論文定位
  → 修改 Title（關鍵詞對齊期刊熱門主題）
  → 調整 Abstract（強調與期刊 scope 的契合點）
  → 修改 Introduction 第一段（引用該期刊的近期文章）
  → 調整 Discussion（連結到該期刊讀者關心的議題）

Step 4: 格式轉換
  → 修改 YAML 檔頭的 format 區塊
  → 更換 CSL 檔案
  → 調整圖表格式要求
  → 重新 quarto render
```

### 8.2 QMD → TeX 的快速轉換

```bash
# QMD 直接輸出 TeX（保留原始 LaTeX 以便微調）
quarto render paper.qmd --to pdf --keep-tex

# 結果：
# paper.tex    ← 可直接提交到 Overleaf 或期刊系統
# paper.pdf    ← 最終 PDF
```

**YAML 中的關鍵配置**：
```yaml
format:
  elsevier-pdf:
    keep-tex: true           # 保留 .tex 檔案
    pdf-engine: pdflatex     # 或 xelatex（中文支援）
```

### 8.3 SVG 向量圖製作流程

**為什麼用 SVG？**
- 無限放大不失真（期刊要求 300+ DPI）
- 檔案小、可編輯
- 期刊接受 PDF/EPS/SVG 三種向量格式

**Python → SVG 工作流**：

```python
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

fig, ax = plt.subplots(figsize=(8, 5))
# ... 繪圖邏輯 ...

# 輸出多格式
fig.savefig('fig_f1_by_device.svg', format='svg', bbox_inches='tight')
fig.savefig('fig_f1_by_device.pdf', format='pdf', bbox_inches='tight')
fig.savefig('fig_f1_by_device.png', format='png', dpi=500, bbox_inches='tight')
```

**SVG 後處理（可用 Inkscape 微調）**：
```bash
# SVG → PDF（向量）
inkscape fig.svg --export-type=pdf --export-filename=fig.pdf

# SVG → EPS（某些期刊要求）
inkscape fig.svg --export-type=eps --export-filename=fig.eps
```

**QMD 中引用圖片**：
```markdown
![Per-device F1 scores across three datasets.](fig_f1_by_device.pdf){#fig-performance width="100%"}
```

### 使用的工具
| 工具/Skill | 用途 |
|------------|------|
| `paper-writer` agent | 論文撰寫與潤稿 |
| `academic-writing` skill | 學術寫作風格 |
| `bib-manager` skill | 引用管理 |
| `citation-checker` agent | 引用驗證 |
| `journal-fit` skill | 轉投目標分析 |
| Quarto render | QMD → PDF/DOCX/TeX |
| Matplotlib + SVG | 向量圖製作 |
| Inkscape | SVG 後處理與格式轉換 |

### 產出
- `paper_0209_v3.qmd` → `.tex` → `.pdf`
- 5 張向量圖（PDF/SVG 雙格式）
- `Supplementary_Material.qmd`

---

## Phase 9: 多維度品質審查（增補平行審查）

### 9.1 七維度評分框架

| 維度 | 權重 | 評估內容 |
|------|------|---------|
| 創新性 | 25% | 方法創新，非簡單應用 |
| 方法論嚴謹性 | 20% | 實驗設計、統計驗證 |
| 結果呈現 | 15% | 數據一致性、圖表品質 |
| 寫作品質 | 15% | 學術語言、邏輯清晰 |
| 文獻回顧 | 10% | 全面性、批判性分析 |
| 期刊契合度 | 10% | 與目標期刊 scope 匹配 |
| 格式規範 | 5% | 投稿要求符合度 |

### 9.2 平行審查策略（Claude × ChatGPT × Gemini）

**為什麼要平行審查？**
- 不同 AI 模型有不同的「審稿偏好」
- Claude 偏重邏輯嚴謹性和統計
- ChatGPT 偏重寫作流暢度和結構
- Gemini 偏重事實準確性和引用
- 三者交叉 = 最全面的預審

**平行審查工作流**：

```
                  論文 paper.qmd
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
   ┌──────────┐  ┌──────────┐  ┌──────────┐
   │  Claude  │  │ ChatGPT  │  │  Gemini  │
   │ Code     │  │ 4o       │  │ 2.5 Pro  │
   │          │  │          │  │          │
   │ 七維度   │  │ 結構     │  │ 事實     │
   │ 評分     │  │ 寫作     │  │ 引用     │
   │ P0-P3    │  │ 流暢度   │  │ 準確性   │
   │ 統計     │  │ 邏輯     │  │ 新穎性   │
   └────┬─────┘  └────┬─────┘  └────┬─────┘
        │             │             │
        └─────────────┼─────────────┘
                      ▼
              ┌───────────────┐
              │  彙整報告      │
              │  • 三者共識    │
              │  = 高信度問題   │
              │  • 單一指出    │
              │  = 需人工判斷   │
              └───────────────┘
```

**Claude 的獨特優勢**：
- 有 Skills 系統，可啟動 `paper-review-skill` 做結構化評分
- 有 `citation-checker` agent 做引用驗證
- 有 `mvp-gatekeeper` 做投稿門檻檢查
- 可透過 `/review-paper` command 一鍵啟動完整審查流程

### 使用的工具
| 工具/Skill | 用途 |
|------------|------|
| `paper-reviewer` agent | 七維度評分 |
| `paper-review-skill` skill | 審查框架 |
| `citation-checker` agent | 引用驗證 |
| `figure-table-checker` skill | 圖表一致性 |
| `mvp-gatekeeper` skill | MVP 門檻檢查 |
| `evidence-indexer` skill | 證據追溯 |
| `/review-paper` command | Claude 一鍵審查 |
| ChatGPT 4o | 平行審查（寫作+結構） |
| Gemini 2.5 Pro | 平行審查（事實+引用） |

---

## Phase 10: 投稿準備（增補素材優化）

### 10.1 投稿素材清單

| 素材 | 工具 | 說明 |
|------|------|------|
| 論文 PDF | Quarto render | 最終格式 |
| 論文 TeX | Quarto --keep-tex | 某些期刊要求 |
| 論文 DOCX | Quarto --to docx | 某些期刊要求 |
| Cover Letter | `submission-helper` agent | 5 段式結構 |
| Highlights | AI 輔助 | 3-5 點核心發現 |
| Graphical Abstract | Inkscape / AI | 視覺化摘要 |
| Supplementary Material | QMD 編譯 | 補充表格/圖表 |
| Author Checklist | 期刊官網 | 逐項確認 |
| Declaration | 模板 | 利益衝突聲明 |
| Suggested Reviewers | AI + 文獻分析 | 3-5 位推薦審稿人 |

### 10.2 素材優化

- Cover Letter 中引用目標期刊近期文章（表示你了解期刊方向）
- Highlights 用數字說話（F1=0.820、成本 < $0.03）
- Suggested Reviewers 從 references.bib 中選活躍研究者

### 使用的工具
| 工具/Skill | 用途 |
|------------|------|
| `submission-helper` agent | Cover Letter + Highlights |
| `journal-submission` skill | 投稿流程規範 |
| `submission-bundle` skill | 打包完整性檢查 |
| `/prepare-submission` command | 一鍵投稿準備 |

---

## Phase 11: 審稿回覆

（內容同前，略）

---

## 完整工具清單彙總

### Skills（24 個）

| # | Skill | 對應 Phase | 功能 |
|---|-------|-----------|------|
| 1 | `literature-synthesis` | P2 | 文獻綜述撰寫 |
| 2 | `bib-manager` | P2, P8 | BibTeX 管理 |
| 3 | `innovation-positioning` | P3 | 創新性定位 |
| 4 | `research-contract` | P3 | 研究契約追蹤 |
| 5 | `journal-fit` | P3, P8 | 期刊適配度 + 主編分析 |
| 6 | `baseline-min-set` | P3, P5 | 基線最小集 |
| 7 | `academic-writing` | P4, P8 | 學術寫作 + IMRaD |
| 8 | `evidence-indexer` | P4, P7, P9 | 證據索引 + 數據一致性 |
| 9 | `figure-table-checker` | P4, P7, P9 | 圖表檢查 + 三角驗證 |
| 10 | `experiment-tracker` | P5, P6 | 實驗追蹤 |
| 11 | `experiment-validator` | P5 | 實驗驗證 |
| 12 | `protocol-enforcer` | P5 | 協議一致性 |
| 13 | `ablation-min-proof` | P5 | Ablation 設計 |
| 14 | `split-leakage-audit` | P5 | 數據洩漏檢測 |
| 15 | `metric-audit` | P5, P7 | 指標審計 |
| 16 | `data-preprocessing` | P5 | 數據預處理 |
| 17 | `gpu-monitor` | P6 | GPU 監控 |
| 18 | `statistical-validation` | P7 | 統計驗證 + P0-P3 |
| 19 | `paper-review-skill` | P9 | 七維度審查 |
| 20 | `mvp-gatekeeper` | P9 | MVP 門檻 |
| 21 | `research-verification` | P9 | 研究驗證 |
| 22 | `journal-submission` | P10 | 投稿流程 |
| 23 | `submission-bundle` | P10 | 投稿打包 |
| 24 | `rebuttal-matrix` | P11 | 審稿回覆 |

### 外部 API

| API | Phase | 用途 |
|-----|-------|------|
| CrossRef API | P2 | DOI 驗證 + metadata |
| Semantic Scholar API | P2 | Abstract + 引用數 + 領域 |
| OpenAlex API | P2 | OA 狀態 + 機構 + Concepts |
| Unpaywall API | P2 | 免費 PDF 連結 |
| Zotero API | P2 | 程式化文獻匯入 |

### 外部工具

| 工具 | Phase | 用途 |
|------|-------|------|
| Quarto (.qmd) | P4, P8 | MD → PDF/TeX/DOCX |
| Zotero | P2 | 文獻管理 |
| Obsidian | P2 | 知識圖譜 |
| VS Code + Remote-SSH | P5, P6 | IDE + 遠端開發 |
| Google Colab | P5 | 雲端 GPU |
| ac-3090 (RTX 3090) | P6 | 遠端 GPU |
| Telegram Bot | P6 | 實驗監控 |
| Matplotlib + SVG | P8 | 向量圖製作 |
| Inkscape | P8 | SVG/PDF/EPS 轉換 |
| Claude + ChatGPT + Gemini | P9 | 平行審查 |

---

## 流程自動化程度評估

| Phase | 人工 | AI 輔助 | 全自動 | 說明 |
|-------|------|---------|--------|------|
| P1 概念探索 | 70% | 30% | - | 人主導方向，AI 提供建議 |
| P2 文獻調研 | 15% | 45% | 40% | API 自動驗證 + Zotero 批量 |
| P3 研究定位 | 35% | 65% | - | AI 分析主編+期刊，人決策 |
| P4 論文架構 | 25% | 75% | - | AI 建議 IMRaD 結構，人確認 |
| P5 實驗設計 | 40% | 60% | - | AI 設計方案，人審核 |
| P6 實驗執行 | 5% | 15% | 80% | 遠端自動執行 + TG 通知 |
| P7 數據分析 | 5% | 25% | 70% | Skill 自動驗證 + 報告 |
| P8 論文撰寫 | 25% | 75% | - | AI 初稿 + SVG 圖，人修訂 |
| P9 品質審查 | 10% | 10% | 80% | 平行審查 + 自動報告 |
| P10 投稿準備 | 15% | 55% | 30% | AI 準備材料，人確認 |
| P11 審稿回覆 | 35% | 65% | - | AI 草擬，人定稿 |

**整體 AI 參與度：約 70-75%**
