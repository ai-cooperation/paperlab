---
title: "為什麼論文寫作一定要學 Markdown？"
description: "Markdown 是 AI 時代論文寫作的基礎語言 — 寫作門檻低、格式一鍵切換、版本控制友好"
date: 2026-03-20
tags: ["工具", "Markdown", "Quarto", "QMD"]
keywords: ["Markdown 論文寫作", "Quarto 學術", "QMD 格式", "Markdown vs Word", "Markdown vs LaTeX"]
summary: "Markdown 是 AI 原生的寫作格式，搭配 Quarto 可以一鍵轉換任何期刊格式。學一次，用一輩子。"
weight: 100
---

## 你現在的問題

你用 Word 寫論文。每次改格式花三小時：調字體、調行距、調標題層級、手動編號圖表。被拒稿改投另一本期刊，格式全部重來。

你把 Word 檔丟給工具處理，格式全跑掉。你想修改論文第三段，工具不知道「第三段」在哪裡。

你跟指導教授用 Word 來回改稿，最後桌面上有 `論文_final.docx`、`論文_final_v2.docx`、`論文_final_v2_老師改.docx`、`論文_真的最終版.docx`。

## 為什麼要學 Markdown？

### 1. 寫作門檻極低

Markdown 的語法 5 分鐘就能學會：

- `# 標題` → 一級標題
- `**粗體**` → **粗體**
- `- 項目` → 項目符號
- `[連結](url)` → 超連結

不需要安裝任何軟體，任何文字編輯器都能寫。

### 2. AI 原生格式

ChatGPT、Claude、Gemini — 所有 AI 的輸入輸出都是 Markdown。用 Markdown 寫論文，AI 可以直接讀懂你的文件結構、精準修改特定段落、不會搞亂格式。

Word 檔案對 AI 來說是一堆 XML，它無法精確操作。

### 3. MD → QMD → 任何期刊格式

Markdown 檔案（`.md`）加上 YAML header 就變成 Quarto 檔案（`.qmd`）。Quarto 可以把同一份文件 render 成：

- IEEE 格式的 PDF
- APA 格式的 PDF
- Elsevier 格式的 PDF
- HTML 網頁
- Word 文件（給不用 Markdown 的合作者）

改投期刊？改一行 YAML，重新 render。

### 4. 版本控制友好

Markdown 是純文字，可以用 Git 追蹤每一次修改：

- 誰改了什麼、什麼時候改的，一目了然
- 可以隨時回到任何歷史版本
- 多人協作不會有檔案衝突

告別 `論文_final_v2_老師改_真的最終版.docx`。

### 5. 跨平台通用

Windows、macOS、Linux 都能用。不會因為換電腦就開不了檔案、格式跑掉。

## 怎麼用？

### Word 工作流 vs Markdown 工作流

| 步驟 | Word 工作流 | Markdown 工作流 |
|------|-----------|----------------|
| 寫作 | Word 手動排版 | Markdown 專注內容 |
| 引用 | Endnote 插件（常當機） | Zotero + BibTeX 自動引用 |
| 改格式 | 手動調 3 小時 | 改 YAML 一行，1 分鐘 |
| AI 協作 | 複製貼上，格式全跑 | AI 直接讀寫，格式不變 |
| 版本管理 | 檔名加 _v2_v3 | Git 自動追蹤 |
| 改投期刊 | 全部重排 | 換 template，重新 render |

### 最小可行工作流

1. 用 VS Code 或 Obsidian 寫 `.md` 檔
2. 加上 YAML header（標題、作者、引用格式）
3. 把 `.md` 改名為 `.qmd`
4. 用 Quarto render 成 PDF 或 Word

## 在 12 Phase 中的角色

- **Phase 1-3（研究發想到文獻調研）**：用 Markdown 寫研究筆記、文獻摘要
- **Phase 4-6（方法論到撰寫）**：用 QMD 寫論文本體，搭配 BibTeX 管理引用
- **Phase 7-9（AI 輔助寫作到品質檢查）**：AI 直接讀寫 Markdown，精準修改
- **Phase 10-11（格式化到投稿）**：Quarto 一鍵切換期刊格式
- **Phase 12（審稿回覆）**：Git diff 清楚顯示每一處修改，方便標示給 reviewer

## 常見問題

**Q：不會程式也能學嗎？**

Markdown 不是程式語言，它只是一種文字標記方式。如果你會用 # 表示標題、用 - 表示列表，你就已經會 Markdown 了。學習曲線比 Word 的進階功能還平緩。

**Q：跟 LaTeX 比哪個好？**

LaTeX 功能更強大，但學習曲線陡峭。Markdown + Quarto 能達到 LaTeX 90% 的效果，學習成本只有 10%。如果你不是數學密集型的領域（大量公式推導），Markdown 完全夠用。需要公式時，Markdown 也支援 LaTeX 數學語法。

**Q：指導教授只用 Word 怎麼辦？**

你用 Markdown 寫，Quarto render 成 Word 給教授改。教授的修改你再合併回 Markdown。這是目前最務實的做法。

---

*這是 Paper Lab 工具指南系列。搭配 [Obsidian](/tools/obsidian/) 和 [Zotero](/tools/zotero/) 一起使用效果更好。*
