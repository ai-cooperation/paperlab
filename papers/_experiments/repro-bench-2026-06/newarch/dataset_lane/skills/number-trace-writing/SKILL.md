---
name: number-trace-writing
description: 寫資料集分析論文時，確保每一個出現在稿件裡的數字都來自分析程式產出的 real_results.json（numeric_index），不得有任何幻覺數字。通用於任何資料集分析論文。
---

# Number-Trace Writing — 論文每個數字都要追溯得到

> 引擎會用 `number_trace` gate 掃稿件：**稿件裡每一個數字都必須出現在
> real_results.json 的 `numeric_index`**（或通用統計慣例如 95% CI、p<0.05、年份）。
> 追不到的數字 = 幻覺 → 整篇 fail closed，不得交付。

## 原則

1. **先有 real_results.json，才寫數字。** 寫 Results/Abstract 時，逐一從 real_results 的
   models / sample_flow / survey_design 取值，**原樣**填入；不要重算、不要四捨五入到對不上、不要憑印象。
2. **不要寫你沒算的數字。** 想報的量（某次群組 OR、某交互作用 p、某敏感度結果）若不在
   real_results 裡，就**回去讓分析程式算出來並進 numeric_index**，而不是在稿件裡編一個。
3. **慣例數字不算幻覺**：95（CI 水準）、5/1（顯著水準對應的 %）、0.05/0.01、年份（如 2011–2018）。
   這些 gate 會放行；其餘**實質結果數字**一律要追溯。

## 寫作對照（每句帶數字的話，自問）

- 這個 OR / beta / CI / p / N，是 real_results 哪個 model 的哪個欄？對得上嗎？
- 樣本流的每個 N，是 sample_flow 裡的值嗎？
- 盛行率/百分比是程式算的、在 numeric_index 嗎？

## 研究設計用語（與資料能力一致）

- 橫斷面資料：寫「**與……的關聯**」「盛行勝算」「代謝指標差異」；**禁止**「預防」「降低發生率」「長期/縱貫」「因果」。
- 這條同時被 gate 的橫斷面語言檢查盯著。

## 會被 gate 擋下（fail closed）

- 稿件出現 real_results 沒有的數字 → `DS_NUMBER_UNTRACED`（會列出是哪些數字）
- 橫斷面卻寫預防/發生率/降低風險 → 語言 gate 擋下

## 鐵則

- **稿件是 real_results 的轉述，不是新的計算。** 數字只能搬，不能生。
