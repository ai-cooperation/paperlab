---
title: "AI 寫論文會產生假引用：如何辨識與避免"
date: 2026-05-23
draft: false
slug: ai-fake-references
description: "ChatGPT 產生 30-40% 假 DOI，Claude 4.6 的 DOI 品質最好但仍需驗證。先收集真實文獻，再讓 AI 基於已驗證來源生成文字。"
keywords:
  - AI假引用
  - ChatGPT假文獻
  - AI幻覺
  - DOI驗證
  - AI論文引用
tags: ["碩博士論文", "AI假引用", "文獻驗證", "DOI"]
related_phase: /phase/p2-ai-fake-references/
faq:
  - q: "哪個 AI 的引用品質最好？"
    a: "Claude 4.6 的 DOI 產出品質最好，ChatGPT 假 DOI 比例最高（30-40%），Gemini 有搜尋能力但仍需驗證。不管用哪個，驗證步驟都不能省。"
  - q: "DOI 驗證要花很多時間嗎？"
    a: "用批次驗證工具，20 篇文獻 5 分鐘就能跑完。Paper Lab 有開發 citation-check 工具可以批次驗證。"
---

> 「一直查到錯誤的 DOI 或捏造的引用，讓我很絕望。」

先別絕望。ChatGPT 產生的文獻引用中，約 30-40% 的 DOI 是假的。這不是偶爾出錯，是語言模型的本質限制。它生成的是「看起來像真的引用」，不是「真實存在的引用」。

## 各家 AI 的引用品質比較

不同 AI 的表現差很多：

- **Claude 4.6**：DOI 產出品質最好。通常會明確告訴你它無法確認某些引用，比較誠實
- **ChatGPT**：引用格式最漂亮，但假 DOI 比例最高（30-40%），最需要驗證
- **Gemini**：有即時搜尋能力，引用品質居中，但仍然不能盲信

不管用哪個 AI，驗證步驟都不能省。

## 解法方向：順序反過來

大多數人的流程是：請 AI 寫文獻回顧 → 拿到一堆引用 → 驗證 → 發現一半是假的。

正確的流程反過來：

1. **先用學術搜尋引擎收集真實文獻**（Google Scholar、PubMed、Semantic Scholar）
2. **驗證每一個 DOI**：在瀏覽器輸入 `https://doi.org/你的DOI`，確認能跳轉到論文頁面
3. **把已驗證文獻餵給 AI**：「根據以下 10 篇論文，幫我寫一段文獻回顧」
4. AI 只需要組織語言，不需要「創造」引用

這讓 AI 做它擅長的事（組織語言、找論文間的關聯），同時避開它不擅長的事（記住真實的 DOI）。

## 批次驗證工具

手動一個一個查 DOI 太慢。Paper Lab 有開發 [citation-check 工具](/tools/)，可以批次驗證 DOI 真假，20 篇文獻 5 分鐘跑完。你也可以用 CrossRef API 自己寫簡單的驗證腳本，丟進 Google Colab 就能跑。

## FAQ

**Q：哪個 AI 的引用品質最好？**

Claude 4.6 的 DOI 產出品質最好，ChatGPT 假 DOI 比例最高（30-40%），Gemini 有搜尋能力居中。不管用哪個，都要驗證。

**Q：DOI 驗證要花很多時間嗎？**

用批次驗證工具，20 篇文獻 5 分鐘就能跑完。跟你花三天寫完文獻回顧再發現一半是假的相比，這 5 分鐘非常值得。

---

完整的 AI 假引用防護流程，從文獻搜尋到驗證到建庫，完整做法在這裡 → [Phase 2：AI 假引用防護](/phase/p2-ai-fake-references/)
