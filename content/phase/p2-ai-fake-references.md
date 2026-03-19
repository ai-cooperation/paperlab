---
title: "AI 一直給我假文獻，我快崩潰了"
description: "解決 AI 論文寫作中最大的痛點 — 5 步交叉驗證法，杜絕 ChatGPT 假引用"
date: 2026-03-19
tags: ["Phase 2", "文獻調研", "AI 幻覺", "假文獻", "Zotero"]
keywords: ["AI 假文獻", "ChatGPT 假引用", "AI 幻覺 文獻", "DOI 驗證", "文獻驗證"]
summary: "ChatGPT 生成的引用有 30-40% 的 DOI 是假的。方法學教你用多工具交叉驗證法，5 步杜絕假文獻。"
weight: 2
---

## 你是不是也遇到這個問題？

你用 ChatGPT 生成了一篇漂亮的文獻探討，引用了 20 篇文獻。結果一查，有 8 篇 DOI 是假的，3 篇作者名字不對，2 篇根本不存在。你花了一整天寫的東西，全部要重來。

> 「我發現越核對 GPT 還是常常一直給我錯誤 DOI 或引言不實，它會再上自己編的故事，只要沾上邊。我一直在自我懷疑是不是又要再重寫一份…」
> — 學員反饋

> 「在寫文獻探討時，一直給我不實的文獻來源，讓我很崩潰」
> — 學員反饋

這不是個案。**ChatGPT 生成的學術引用，有 30-40% 的 DOI 是捏造的。** 這是 AI 幻覺（hallucination）在學術寫作中最嚴重的表現。

## 為什麼會這樣？

AI 語言模型的訓練目標是「產生流暢的文字」，不是「產生正確的引用」。

當你要求它引用文獻時，它會：
1. 根據訓練資料中的模式，「編造」一個看起來合理的作者名 + 期刊名 + 年份
2. 生成一個格式正確但不存在的 DOI
3. 把這些組合成看起來完美的引用

問題是：**格式完美 ≠ 內容真實。**

就像不會有會計師只靠一套系統做帳 — 一定要交叉核對。AI 論文寫作也一樣。

## 怎麼解決？5 步交叉驗證法

### 步驟 1：不要只用一個 AI

Gemini Deep Research 的文獻引用品質明顯優於 ChatGPT，因為它會即時搜尋網路。用 Gemini 生成文獻探討的初稿，引用正確率更高。

### 步驟 2：每個引用都要驗 DOI

用 Semantic Scholar 或 CrossRef 驗證每一個 DOI 是否真實存在：
- Semantic Scholar：`api.semanticscholar.org/graph/v1/paper/DOI:{你的DOI}`
- CrossRef：`api.crossref.org/works/{你的DOI}`

如果 API 回傳 404，這個引用就是假的。

### 步驟 3：回到原文比對

把文獻 PDF 上傳到 NotebookLM，逐條核實 AI 引用的內容是否真的出現在原文中。NotebookLM 的 RAG 機制會根據你上傳的文件回答，不會捏造。

### 步驟 4：建立「已驗證文獻庫」

在 Zotero 中標記每篇文獻的驗證狀態：
- ✅ 已驗證（DOI 確認 + 內容比對）
- ⚠️ 待驗證
- ❌ 假文獻（移除）

### 步驟 5：先收集再生成

**不要邊寫邊引用。** 正確的流程是：
1. 先用 Zotero + Research Rabbit 收集真實文獻
2. 把 PDF 餵給 NotebookLM
3. 再根據「你提供的真實文獻」來撰寫文獻探討

這樣 AI 就只能引用你已經驗證過的文獻，不會自己編造。

<div class="tip-box">

**核心原則：** AI 負責寫作，你負責驗證。絕不跳過驗證步驟。

</div>

## 常見問題

**Q：AI 寫論文時文獻引用一直是假的怎麼辦？**

用多工具交叉驗證法：用 Gemini Deep Research 生成（引用品質較好），再用 Semantic Scholar 或 CrossRef API 驗證每個 DOI，最後用 NotebookLM 上傳原文 PDF 逐條比對。

**Q：ChatGPT 假文獻如何驗證？**

最簡單的方式：複製 DOI，到 `doi.org/{DOI}` 看能不能打開。打不開就是假的。進階方式是用 CrossRef API 批次檢查。

**Q：有沒有工具可以自動檢查假引用？**

Zotero 搭配 CrossRef 多重驗證，可以半自動化這個流程。完整的自動化腳本可以付費諮詢。

---

*這是 [論文方法學 12 Phase](/phases/) 的 Phase 2：文獻調研。*
