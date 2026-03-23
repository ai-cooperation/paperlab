---
title: "論文圖表怎麼做：用 AI 生成學術級向量圖"
date: 2026-05-30
draft: false
slug: paper-figures-guide
description: "Excel 截圖是論文圖表的第一大地雷。用 AI 生成 Python 程式碼，在 Google Colab 跑出向量圖，不需要會寫程式。"
keywords:
  - 論文圖表
  - 學術圖表
  - Python論文圖
  - matplotlib學術圖
  - 論文圖表格式
tags: ["碩博士論文", "論文圖表", "Python", "數據視覺化"]
related_phase: /phase/p9-figures-tables/
faq:
  - q: "完全不會寫程式怎麼辦？"
    a: "不需要會。告訴 AI 你要什麼圖，複製程式碼到 Google Colab，點 Run，下載圖片。報錯就把錯誤訊息貼給 AI。"
  - q: "已經做好 Excel 圖了，不想重做？"
    a: "把 Excel 圖截圖給 AI，請它根據截圖重新生成符合學術規範的 Python 程式碼。只需要校對數字是否正確。"
---

> 「reviewer 說我的圖表解析度不足，要求重做所有圖。」

Excel 截圖是論文圖表的第一大地雷。截圖是點陣圖（72-96 DPI），期刊要求 300 DPI 以上，放大就糊，reviewer 一看就知道不專業。

解法：用 AI 生成 Python 程式碼，在 Google Colab 跑出向量圖。不需要安裝軟體，不需要會寫程式，不需要花錢買繪圖工具。

## 流程很簡單

告訴 AI 你要什麼圖（類型、數據、軸標籤、分組），它生成 Python matplotlib 程式碼。複製到 Google Colab，點 Run，下載 SVG 向量圖。如果程式碼報錯，把錯誤訊息貼回給 AI，它會修好。通常一兩輪就能跑出正確的圖。

不滿意的地方直接告訴 AI：「把字體放大」、「圖例移到右上角」、「換成色盲友善色板」。它修改程式碼，你再跑一次。

## 最容易被忽略的事：色彩語義一致性

整篇論文中，同一個變數或組別必須使用同一個顏色。如果圖 1 中「實驗組」是藍色，圖 3 中「實驗組」不能變成紅色。

在程式碼中定義一個全域色板，每張圖都引用它：

```python
COLORS = {
    'experimental': '#2171B5',  # 藍
    'control': '#CB181D',       # 紅
    'baseline': '#6A6A6A',      # 灰
}
```

這件事很小，但 reviewer 會注意到。色彩不一致會讓讀者困惑，也顯得不專業。

## FAQ

**Q：完全不會寫程式怎麼辦？**

不需要會。告訴 AI 你要什麼圖，複製程式碼到 Google Colab，點 Run，下載圖片。你不需要理解程式碼的每一行。

**Q：已經做好 Excel 圖了，不想重做？**

把 Excel 圖截圖給 AI，請它重新生成符合學術規範的 Python 程式碼。只需要校對數字是否正確。

---

<p style="text-align: center; font-size: 1.1em; margin-top: 2rem;">
<a href="/phase/p9-figures-tables/"><strong>完整做法在這裡 → Phase 9：圖表與視覺化</strong></a>
</p>
