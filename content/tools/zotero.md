---
title: "為什麼論文寫作一定要學 Zotero？"
description: "免費開源的文獻管理工具，一鍵從瀏覽器存文獻、自動抓 metadata、輸出 BibTeX 搭配 Quarto 使用"
date: 2026-03-19
tags: ["工具", "Zotero", "引用管理", "BibTeX"]
keywords: ["Zotero 教學", "引用管理工具", "BibTeX 匯出", "Zotero vs Endnote", "文獻管理"]
summary: "Zotero 是免費開源的文獻管理工具，一鍵從瀏覽器存文獻、自動抓 metadata、輸出 BibTeX 搭配 Quarto 使用。"
weight: 102
---

## 你現在的問題

你的文獻散落在各處：桌面有 30 個 PDF、下載資料夾有 50 個、Google Drive 有 20 個。檔名是 `paper1.pdf`、`(2).pdf`、`Final version - Copy.pdf`。你找不到上週讀的那篇，也記不得哪篇的 DOI 是什麼。

寫論文要引用的時候，你手動複製 APA 格式的引用，改完發現 A 期刊要 IEEE 格式，全部又要重改。

更危險的是：你用工具自動生成引用，結果有 30% 是假的，但你沒有一個可靠的文獻庫可以核對。

## 為什麼要學 Zotero？

### 1. 一鍵存文獻

安裝 Zotero Connector 瀏覽器擴充功能後，在任何學術網站（Google Scholar、PubMed、arXiv、期刊網站）只要點一下按鈕，文獻就自動存進 Zotero，連 PDF 都幫你下載。

### 2. 自動抓 metadata

存進 Zotero 的文獻會自動擷取：作者、標題、期刊、年份、DOI、摘要。你不需要手動輸入任何一項。如果 metadata 不完整，Zotero 可以透過 DOI 從 CrossRef 自動補齊。

### 3. BibTeX 輸出

Zotero 可以輸出 `.bib` 檔案，搭配 Markdown + Quarto 使用，引用只需要寫 `[@chen2024]`，render 時自動生成完整的引用格式。換期刊？換 CSL 樣式檔就好，不需要手動改任何引用。

### 4. 四種匯入方式

| 方式 | 場景 |
|------|------|
| 瀏覽器 Connector | 在學術網站一鍵存入 |
| DOI / ISBN 輸入 | 知道 DOI 就能存，自動抓所有資訊 |
| PDF 匯入 | 把 PDF 拖進 Zotero，自動辨識 metadata |
| BibTeX 匯入 | 從其他工具或 AI 生成的 .bib 檔匯入 |

### 5. 搭配 CrossRef API 驗證

Zotero 中的文獻都有 DOI，你可以用 CrossRef API 批次驗證所有 DOI 是否真實存在。這是杜絕 AI 假文獻的最後防線。

## 怎麼用？

### 基本工作流

1. **安裝 Zotero 7** — 免費下載，支援 Windows/macOS/Linux
2. **安裝瀏覽器 Connector** — Chrome/Firefox/Safari 都有
3. **建立分類資料夾** — 按研究主題或論文章節分類
4. **日常使用** — 讀到好文獻，點一下 Connector 按鈕存入
5. **寫論文時** — 匯出 BibTeX，在 Quarto 中引用

### 黃金規則

> **絕不添加 `references.bib` 中不存在的引用。**

這條規則的意思是：你的論文中的每一條引用，都必須來自你的 Zotero 文獻庫匯出的 `.bib` 檔案。AI 生成的引用如果在你的 Zotero 中找不到，就不能用。

這是防止假文獻混入論文的最簡單方法。

### 進階：三重驗證流程

1. **Zotero 有這篇嗎？** — 如果沒有，這個引用不可信
2. **DOI 在 CrossRef 查得到嗎？** — `api.crossref.org/works/{DOI}`
3. **引用內容跟原文一致嗎？** — 用 NotebookLM 上傳 PDF 比對

## 在 12 Phase 中的角色

Zotero 貫穿整個研究流程：

| Phase | Zotero 的角色 |
|-------|--------------|
| **Phase 2 — 文獻調研** | 存入所有找到的文獻，建立文獻庫 |
| **Phase 3 — 確認 Research Gap** | 標記核心文獻（星號標記），分類整理 |
| **Phase 6-9 — 撰寫** | 匯出 BibTeX，在論文中引用 |
| **Phase 10 — 品質審查** | CrossRef API 驗證所有 DOI，確保無假文獻 |
| **Phase 11 — 投稿準備** | 切換 CSL 樣式，一鍵轉換引用格式（APA → IEEE → Vancouver） |

## 常見問題

**Q：已經在用 Endnote 需要換嗎？**

看情況。Endnote 是付費軟體（通常學校買授權），畢業後可能就不能用了。Zotero 永久免費、開源、跨平台。如果你還在學，可以兩個並行，慢慢轉移。如果你要用 Markdown + Quarto 工作流，Zotero 的 BibTeX 匯出比 Endnote 順暢很多。

**Q：Zotero 免費嗎？**

軟體完全免費。雲端同步空間免費 300MB（夠存幾千篇文獻的 metadata），如果要同步 PDF 需要付費擴充空間（或用 WebDAV 自架）。大部分人 300MB 免費空間就夠用。

**Q：AI 生成的引用可以直接匯入 Zotero 嗎？**

可以，但強烈建議先驗證。把 AI 生成的 BibTeX 匯入 Zotero 後，用 DOI 查詢功能逐一驗證。查不到的就是假文獻，立刻刪除。

**Q：Zotero 可以跟 Obsidian 搭配嗎？**

可以。用 Zotero 的 Better BibTeX 插件，每次在 Zotero 新增文獻，自動更新 `.bib` 檔案。在 Obsidian 中用 Citations 插件，可以直接從 Zotero 文獻庫建立文獻筆記。兩者搭配是學術寫作的最強組合。

---

*這是 論文方法學工具指南系列。搭配 [Markdown](/tools/markdown/) 和 [Obsidian](/tools/obsidian/) 一起使用效果更好。*
