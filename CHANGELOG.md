# Changelog

## [1.0.0] - 2026-03-07

### Phase 1: 課程規劃（03-06）
- 建立完整工作流程文件 `01_complete_workflow.md`
- 撰寫課程計畫 v2.1 `02_workshop_course_plan.md`（656 行）
  - 兩天課程、5 個 Session、11 個 Phase
  - 學員分級定位（L1D2 + L2D1）
  - 實作練習與評估機制
- 完成教學評估報告 `03_evaluation_report.md`
- 完成簡報大綱 `04_presentation_outline.md`

### Phase 2: 設計系統建立（03-07 上午）
- 配色方案探索：產出 `Color_Scheme_Samples.pptx`（5 套方案）
- 品牌配色確定：Navy/Teal/Gold 三色系統 `Color_Brand_Sample.pptx`
- 品牌設計系統簡報 `gen_brand_system.js`（含字型、陰影、圓角規範）
- 課程介紹簡報 `gen_course_intro.js`（兩天課程架構概覽）

### Phase 3: Day 1 概要版（03-07 中午）
- `gen_day1.js` → `Day1_AI研究基礎.pptx`（概要版）
- `gen_day2.js` → `Day2_AI研究進階.pptx`（概要版）

### Phase 4: 共用元件庫（03-07 下午）
- 建立 `slide_lib.js`（397 行，20+ 可重用函數）
  - coverSlide, sectionDivider, contentSlide
  - conceptSlide, stepSlide, cardsSlide, tableSlide
  - codeBox, infoCard, tipBox, warnBox
  - exerciseSlide, compareSlide, processSteps
  - keyPointsSlide, quoteSlide, closingSlide
- 修復 `tipBox`/`warnBox` 使用 `SHAPES` 常數替代 `pres.shapes.RECTANGLE`

### Phase 5: Day 1 完整版（03-07 下午）
- `gen_day1_full.js` → `Day1_Full_AI研究基礎.pptx`
- 67 頁詳細教學投影片
- 涵蓋：CARE Prompt、Extended Thinking、Zotero/Obsidian、API 驗證三步法、
  Semantic Scholar、Innovation Positioning、Journal Fit

### Phase 6: Day 2 完整版（03-07 晚上）
- `gen_day2_full.js` → `Day2_Full_AI研究進階.pptx`
- 73 頁詳細教學投影片
- 涵蓋：IMRaD、QMD+YAML、GPU 遠端、TG Bot、統計驗證、SVG 圖表、
  BibTeX、Claude Code 24 Skills、七維度審查、平行 AI 審查、投稿策略

### Phase 7: QA 驗證與修復（03-07 晚上）
- PPTX → PDF → JPG 截圖自動化
- 發現 6 處溢出/重疊問題並修復：

| 投影片 | 問題 | 修復 |
|--------|------|------|
| D2 #8 漏斗式 | Layer 4 文字溢出 | 加寬至 4.0"，動態寬度比例 |
| D2 #14 期刊格式 | 程式碼底部裁切 | 壓縮為雙欄排列 |
| D2 #36 Python | 標題/程式碼重疊 | 精簡行數、調整高度 |
| D2 #42 Skills | infoCard 標題重疊 | 精簡文字、調整位置 |
| D1 #32 Semantic Scholar | codeBox 標題重疊 | 精簡 API URL |
| D1 #48 創新性定位 | infoCard 標題重疊 | 精簡內容 |

- `slide_lib.js` 元件修復：
  - `infoCard`: title/body 間距 0.30" → 0.38"，加入 `fit: "shrink"`
  - `codeBox`: title/code 間距 0.28" → 0.34"，加入 `fit: "shrink"`

### Phase 8: 專案獨立化（03-07 晚上）
- 建立 `~/projects/ai-paper-workshop/` 獨立專案
- 目錄結構：src / docs / dist / scripts / qa_screenshots
- 修復輸出路徑（硬編碼 → `path.join(__dirname, "..", "dist")`）
- 建立 npm scripts（build:day1, build:day2, build:all, qa）
- 驗證 `npm run build:all` 可獨立建置
