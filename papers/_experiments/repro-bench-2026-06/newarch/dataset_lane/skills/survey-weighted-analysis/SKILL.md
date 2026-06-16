---
name: survey-weighted-analysis
description: 寫 analysis.py 對下載好的真實資料集跑正確的迴歸分析（含複雜抽樣加權 GLM、線性/邏輯迴歸、樣條、次群組、敏感度），並輸出可被機械驗證的 real_results.json。通用於任何資料集，不綁特定變數名。
---

# Survey / Dataset Analysis — 寫一支會被機械驗證的 analysis.py

> 你寫的 `analysis.py` 會被引擎用 `python analysis.py --manifest <> --spec <> --out <>`
> **實際執行**。real_results.json 是「程式跑出來的」，不是你寫的散文。
> 每個你之後在論文要報的數字，都必須由這支程式算出來並放進 `numeric_index`。

## 介面（固定）

```bash
python analysis.py --manifest data/manifest.json \
  --spec real_experiments/analysis_spec.json \
  --out real_experiments/real_results.json
```

## 程式必須做的事

1. **讀真實資料**：依 manifest 的 artifacts 路徑/格式讀檔（pandas：`read_csv` / `read_sas`(xpt) / `read_parquet` / 解壓 zip 等）。把 `manifest_sha256` 原樣複製進 real_results 的 `data_manifest_sha256`（證明你讀了真資料）。
2. **建分析資料集**：依 spec 衍生暴露/結果變數、記錄樣本流（起始 N、排除、最終分析 N）。
3. **跑模型**：依 spec 的 models。**若 spec 宣告了 survey_design，就一定要套用加權**：
   - 複雜抽樣（weight + strata + PSU）→ 用對應方法（Python 可用 `statsmodels` 的 `GLM(..., freq_weights=)`／`var_weights=`，或 `samplics`；最低限度也要套權重並用 Taylor/線性化或自助法估變異）。
   - **不要跑無加權 `logit`/`ols` 然後假裝是加權**——gate 會比對 `n_weighted != n_unweighted`，相同就判定沒套權重。
   - 合併多週期資料時，依該資料集規則調整權重（例如把週期權重除以週期數）。空腹類結果用對應的子樣本權重。
4. **輸出 real_results.json**，欄位固定：

```json
{
  "status": "completed",
  "simulated": false,
  "lane": "dataset_agent_analysis",
  "source": "<dataset name>",
  "data_manifest_sha256": "<copied from manifest>",
  "rows": <analysed rows>,
  "sample_flow": {"identified": N, "excluded_...": N, "analytic": N},
  "survey_design": {"weighted": true, "weight_variable": "<真實欄名>",
                    "strata_variable": "<真實欄名>", "psu_variable": "<真實欄名>",
                    "design_df": <int>, "weight_combination_rule": "<說明>"},
  "variables": {"<col>": {...}, ...},        // 你實際用到的欄
  "models": [
    {"id": "m1", "family": "survey_logistic", "outcome": "<col>", "exposure": "<col>",
     "estimate": <OR/beta>, "ci_low": <>, "ci_high": <>, "p_value": <>,
     "n_unweighted": <int>, "n_weighted": <float>, "covariates": ["<col>", ...]}
  ],
  "spline_results": {...}, "subgroup_results": {...}, "sensitivity_results": {...},
  "numeric_index": [<每一個你報的數字>]
}
```

## 變數名是「這個資料集的真實欄名」，不是寫死

- weight/strata/psu/outcome/exposure 全部填**這個資料集實際的欄名**（你從資料字典/欄位看到的）。
- 不同資料集欄名不同——這支程式對映到 spec 給的真實欄名即可，**不要硬編任何特定資料集的欄名**。

## 研究設計用語要對齊資料能力

- 橫斷面（cross-sectional）資料 → 只能講**關聯/盛行勝算/代謝指標差異**，不能講「預防」「降低發生率」「縱貫因果」。
- spec 怎麼宣告設計，程式與輸出就怎麼描述。

## 會被 gate 擋下（fail closed）

- returncode≠0 / 沒產 real_results / simulated≠false → `DS_EXEC_*`
- 宣告 weighted 但 `n_weighted==n_unweighted`（沒真的套權重）→ `DS_SURVEY_NOT_APPLIED`
- design_df≤0、宣告的權重欄沒被用到 → `DS_SURVEY_*`
- 缺必要欄位 → `DS_SCHEMA_*`

## 鐵則

- **只報你算出來的數字。** 不要硬編、不要寫你沒算的值。每個數字進 `numeric_index`。
