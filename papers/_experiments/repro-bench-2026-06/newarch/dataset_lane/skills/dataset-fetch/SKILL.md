---
name: dataset-fetch
description: 把一個公開資料集來源（URL）解析成「真實可下載的檔案清單」。當研究的 data_source.type=dataset 時，由 agent 讀來源網頁/資料字典，產出 download_plan.json 交給引擎下載。通用於任何公開資料集，不綁特定資料集。
---

# Dataset Fetch — 解析公開資料集成可下載檔案清單

> 你（agent）的工作是「找出真實的檔案 URL」，**不是自己下載、更不是捏造資料**。
> 引擎的決定性 Python 會親自下載你列出的 URL、算 sha256、寫 manifest。
> 你列假 URL → 下載失敗或拿到真實內容，騙不過 gate。

## 產出（只寫這一個檔）

`data/download_plan.json` = 一個 JSON 陣列：

```json
[
  {"url": "<直接指向資料檔的 URL>", "filename": "<存檔名>"},
  ...
]
```

## 怎麼解析（通用流程）

1. 讀 `data_source.url`。它常是**落地頁（landing page）**，不是檔案本身。
2. 在落地頁/資料字典找出**實際資料檔**的直接連結。常見格式：`.csv .tsv .xpt .sas7bdat .parquet .feather .dta .sav .zip .gz`。
   - 用 terminal 工具 `curl -sL <url>` 抓頁面，grep 出檔案連結；或讀資料字典頁。
   - 大型調查資料集常**分檔/分週期**（多個 component 檔）——把研究需要的檔都列進來。
3. 只列**真實存在、來源站台提供**的 URL。不要列 example.com、不要自己編、不要產生本地 CSV。
4. 需要的檔才下載（控制體積）；每個檔給清楚 filename。

## 範例（示意，非限定）

- 一個分週期、分 component 的健康調查 → 列出各週期的 demographics / examination / questionnaire 檔的真實 URL。
- 一個世界銀行指標 → 列出指標 CSV 的下載 URL。
- 一個 Kaggle 公開 CSV → 列出檔案的直接下載 URL。

## 會被 gate 擋下的情形（fail closed）

- 只抓到 HTML 落地頁、沒有真資料檔 → `DS_FETCH_NO_DATA`
- 檔名含 synthetic/fake/example/dummy → `DS_FETCH_SYNTHETIC`
- 空檔、無法解析的檔 → `DS_FETCH_NO_DATA`

## 鐵則

- **你只給 URL；下載與存證是 Python 的事。** 不要在 download_plan 之外寫任何資料檔。
- 找不到真實檔案連結時，回報「來源只有落地頁、需要更精確的資料檔 URL」，不要硬湊。
