# AI Paper Workshop 2026

AI 輔助學術研究全流程工作坊 — 從概念到投稿的完整 PPTX 課程簡報生成系統。

## 課程概覽

| 項目 | 內容 |
|------|------|
| 課程名稱 | AI-Assisted Research Paper Workshop |
| 對象 | 研究生、博士生、產學合作研究人員 |
| 時長 | 兩天，每天 8 小時（含休息） |
| 等級 | Day 1: L1D2（初階進階）/ Day 2: L2D1（中階入門） |
| 總投影片數 | 140 頁（Day 1: 67 + Day 2: 73） |

### Day 1 — AI 研究基礎：從概念到文獻（67 slides）

| Session | 時間 | 主題 | 內容 |
|---------|------|------|------|
| 開場 | 09:00-09:30 | AI 正在重塑學術研究 | 真實案例：NILM+LLM 論文的 AI 協作歷程 |
| S1 | 09:30-10:45 | 概念探索與研究方向 | CARE Prompt 框架、Extended Thinking、多輪對話策略 |
| S2 | 11:00-12:00 | AI 輔助文獻研究 | Zotero/Obsidian 整合、DOI 種子驗證三步法 |
| S2+ | 13:00-14:30 | 文獻進階 | CrossRef/Semantic Scholar/OpenAlex API、Graph View |
| S3 | 14:45-16:00 | 研究定位與創新性 | Innovation Positioning、Journal Fit、三層創新框架 |
| 結尾 | 16:00-17:00 | Day 1 實作 + 總結 | 完成文獻管理系統、Day 2 預習 |

### Day 2 — AI 研究進階：從架構到投稿（73 slides）

| Session | 時間 | 主題 | 內容 |
|---------|------|------|------|
| 開場 | 09:00-09:20 | Day 2 總覽 | Phase 4-11 工作流程 |
| S3 | 09:20-12:00 | 論文架構與實驗規劃 | IMRaD、QMD+YAML、GPU 遠端執行、TG Bot 監控、統計驗證 |
| S4 | 13:00-14:45 | 論文撰寫系統 | 各章寫作策略、SVG 向量圖、BibTeX、Claude Code + 24 Skills |
| S5 | 15:00-16:30 | 品質審查與投稿 | 七維度評分、平行 AI 審查、引用驗證、投稿策略 |
| 結尾 | 16:30-17:00 | 課程總結 | 帶走 research-workspace.zip 完整系統 |

## 目錄結構

```
ai-paper-workshop/
├── README.md              # 本文件
├── CHANGELOG.md           # 開發歷史
├── package.json           # Node.js 專案設定
├── .gitignore
│
├── src/                   # PPTX 生成原始碼
│   ├── slide_lib.js       # 共用元件庫（20+ 可重用函數）
│   ├── gen_day1_full.js   # Day 1 完整課程簡報（67 slides）
│   ├── gen_day2_full.js   # Day 2 完整課程簡報（73 slides）
│   ├── gen_course_intro.js # 課程介紹簡報
│   ├── gen_brand_system.js # 品牌設計系統簡報
│   ├── gen_day1.js        # Day 1 概要版（早期版本）
│   ├── gen_day2.js        # Day 2 概要版（早期版本）
│   ├── gen_color_samples.js # 配色方案樣本
│   └── gen_color_brand.js  # 品牌配色樣本
│
├── docs/                  # 課程規劃文件
│   ├── 01_complete_workflow.md    # 完整工作流程說明
│   ├── 02_workshop_course_plan.md # 課程計畫 v2.1（656 行）
│   ├── 03_evaluation_report.md    # 教學評估報告
│   └── 04_presentation_outline.md # 簡報大綱
│
├── dist/                  # 產出的 PPTX 檔案
│   ├── Day1_Full_AI研究基礎.pptx  # Day 1 完整版（67 slides, 1.2MB）
│   ├── Day2_Full_AI研究進階.pptx  # Day 2 完整版（73 slides, 1.3MB）
│   ├── AI_Research_Workshop_Course_Intro.pptx  # 課程介紹
│   ├── Day1_AI研究基礎.pptx      # Day 1 概要版
│   ├── Day2_AI研究進階.pptx      # Day 2 概要版
│   ├── Color_Brand_Sample.pptx    # 品牌配色
│   └── Color_Scheme_Samples.pptx  # 配色方案
│
├── scripts/               # 自動化腳本
│   └── qa-screenshots.sh  # QA 截圖生成腳本
│
└── qa_screenshots/        # QA 驗證截圖（不入 git）
    ├── day1/              # 67 張 JPG
    └── day2/              # 73 張 JPG
```

## 技術架構

### 設計系統

| 項目 | 規格 |
|------|------|
| 畫布 | 10" x 5.625"（16:9） |
| 主色 | Navy `#0B3C5D` / Teal `#0F9D8A` / Gold `#FFC857` |
| 字型 | 標題 20-24pt / 內文 10.5-13pt |
| Header bar | y: 0, h: 0.72" |
| 內容區域 | y: 0.82" ~ 5.35" |
| 底部導覽 | y: 5.4", h: 0.225" |

### slide_lib.js 共用元件（20+ 函數）

| 元件 | 用途 |
|------|------|
| `coverSlide` | 封面頁（帶裝飾圓形） |
| `sectionDivider` | 章節分隔頁（深色背景） |
| `contentSlide` | 標準內容頁（含 header + nav） |
| `conceptSlide` | 概念解說頁（標題 + 副標 + 要點） |
| `stepSlide` | 步驟教學頁（編號 + 標題 + 清單） |
| `cardsSlide` | 2~3 欄卡片頁 |
| `tableSlide` | 表格頁 |
| `codeBox` | 程式碼區塊（深色底 + 語法高亮色） |
| `infoCard` | 資訊卡片（左側色條 + 標題 + 內文） |
| `tipBox` | 提示框（淺藍底） |
| `warnBox` | 警告框（紅色底） |
| `exerciseSlide` | 實作練習頁 |
| `compareSlide` | Before/After 比較頁 |
| `processSteps` | 水平流程步驟 |
| `keyPointsSlide` | 重點清單頁 |
| `quoteSlide` | 引言頁 |
| `closingSlide` | 結尾頁 |

### QA 驗證流程

```
npm run build:all → soffice --convert-to pdf → pdftoppm -jpeg → 逐頁視覺檢查
```

檢查項目：
- 文字溢出：所有文字不超出元素邊界
- 元素重疊：標題與內文不重疊（title/body gap >= 0.08"）
- 邊距一致：內容在 x: 0.25"~9.75" 範圍內
- 底部安全：所有內容在 y < 5.35" 以上
- 中文字型：CJK 字元正確渲染

## 使用方式

### 安裝

```bash
cd ~/projects/ai-paper-workshop
npm install
```

### 建置所有簡報

```bash
npm run build:all
```

### 建置單天簡報

```bash
npm run build:day1   # → dist/Day1_Full_AI研究基礎.pptx
npm run build:day2   # → dist/Day2_Full_AI研究進階.pptx
```

### QA 驗證

```bash
npm run qa           # 需要 LibreOffice + poppler-utils
```

## 相依

- **Runtime**: Node.js >= 18
- **npm**: pptxgenjs ^3.12.0
- **QA tools**: LibreOffice (soffice), poppler-utils (pdftoppm)

## 來源專案

此課程內容從 [NILM_LLM_SETA](https://github.com/AlanChen75/NILM_LLM_SETA) 研究專案的教學需求衍生。
課程以該專案的 SETA 論文投稿經驗為真實案例貫穿兩天教學。
