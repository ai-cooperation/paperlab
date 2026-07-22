# ADR-002: Figure Lanes — 依論文類別的圖表模板註冊表（v2，經五面向對抗審查修訂）

Status: DRAFT v2（v1 經 5-adversary panel：14 blocker + 19 major 全數採納或裁決；待用戶拍板）
Date: 2026-07-21
Origin: v3_9bb7921f4f2f（NILM VIP）交付後用戶目視抓到圖表品質崩壞——floor 82 但四張圖三張是
pipeline 自畫像。審查七維度無圖表維度，Gate C 只驗配對編號。

## 1. 問題（三個結構性缺陷）

- **D1 模板硬編**：`DATA_OUTPUTS` 硬編四個 meta 形狀檔名，`_ensure_required_minimal_figures`
  對每種論文都補這四張——meta 圖形語言套在 evidence-map 論文上只能拿稽核計數充數。
- **D2 無資訊性偵測**：稽核率充數圖（全 1.00 bar）、無溯源 whisker、同值漏斗全可過閘。
- **D3 審查無圖表層**。

## 2. 設計原則

1. 確定性生成、evidence 錨定（反捏造不變量：模型不畫數字）。
2. 類別偵測吃 evidence 形狀；**absence 斷言要有 probe log**（搜過才准說沒有）。
3. fail-closed 且**每閘的判準是「溯源」不是「數值形狀」**——值全等/零攔損若各有獨立真溯源
   就是合法事實，症狀 regex 會製造不可修 finding（審查裁決：v1 的 zi1/zi2 判準推翻重寫）。
4. 迴圈不是補丁：registry entry = 資料；**類別豁免/門檻全部住在 template metadata**，
   gate 與偵測器 source 零類別分支（v1 的「k=1 豁免」「k≥10 funnel」都移進 entry 欄位）。
5. **見證鏈不自我見證**：閘獨立回 evidence 檔驗數值，不信 manifest 自述。

## 3. 類別註冊表

### 3.1 Registry entry 形狀（資料，非程式）

```python
{
  "category_id": "C1_meta",
  "priority": 10,
  "detect": {...宣告式 schema predicate（鍵路徑+形狀條件）...},
  "templates": [
    {"stem": "fig_forest", "generator": "forest_v2", "comparative": True,
     "sufficiency": {...資料充足性 predicate...},        # 不足→該圖不畫，不硬畫
     "uniform_ok_when": {...},                            # 承載 k=1 類豁免
     "thresholds": {...},                                 # 承載 k≥10 funnel 類條件
     "conditional": False},
    ...
  ],
}
```

- 偵測＝按 priority 迭代 entries 執行 predicate。litmus：新類別＝加 entry，
  **驗收 grep：registry 資料檔之外 source 零類別名/stem/evidence 鍵路徑字面量**
  （含測試檔——域中立測試的 allowlist 改從 registry 載入）。

### 3.2 類別與圖組

| 類別 | 偵測訊號 | 必備 | 選配（各自 sufficiency predicate） |
|---|---|---|---|
| C1 meta | meta.effects k≥1 含 CI | forest、method_overview | PRISMA（有真檢索紀錄才畫；無階段級資料→單框 identification 圖+正文誠實聲明）、funnel（k≥10） |
| C4 benchmark | method×metric 矩陣 ≥2 方法 | benchmark 比較圖、pipeline 圖 | — |
| C3 empirical | primary_outcomes 點估計+不確定度 | 效應圖（真 CI）、pipeline 圖 | 分組比較、時序（依 outcome 形狀） |
| C2 evidence-map | 以上皆無**且 probe log 完整** | 框架圖（minimal 可通過態） | 地景圖（分類覆蓋率≥80% 才畫）、覆蓋矩陣（須有非滿格維度，全滿改正文一句話不出圖）、決策樹（→S3，見 §8） |
| C0 fallback | bib metadata 亦不足 | method_overview | — |

- **多命中**：偵測器記錄全部命中類別入 manifest；必備集=首中類別，**允許集=全部命中類別的
  聯集**；宣告 paper_type 與 evidence 形狀衝突＝顯性事件停泊（比照 V3.2 降級=顯性事件）。
- **框架圖只准 paper-domain 欄位**（research question/constructs/假設關係），明文禁止
  engine-ops 欄位（gate/phase/retry）；每個節點 label 須 grounded 於正文（機械字串比對）。
- lane_downgrade → 強制 C2（帶事件紀錄）。

### 3.3 figure_manifest.json（單一真相源）

- 欄位：`schema_version`、`category`（權威）、`categories_detected`（全部命中）、
  `probe_log`（C2 的 absence 查證）、`evidence_fingerprint`、
  `figures: [{stem, template, provenance: [evidence keys 或 derivation record], generator_hash}]`、
  `demotions: [{from, to, reason, provenance}]`。
- **由單一決定性 assembler 寫入**；manifest 不在 heal 可寫集——healer 觸及圖檔必須經
  同一 assembler 交易（圖+manifest+sections @fig-* 引用原子改寫）。未知 schema_version
  → fail-closed。

## 4. 合約改動（消費點窮舉為交付物）

- **終態**：figure stems 的唯一 runtime 真相源＝figure_manifest；
  `DATA_OUTPUTS` 圖項/`FIGURE_OUTPUTS`/`REVIEW_HEAL_OUTPUTS` 圖項改為 per-run 由 manifest
  推導的 accessor，module-level 常數刪除（或降格為測試 superset 並禁止 runtime 消費）。
- **兩段式合約**：類別偵測是 data phase 的確定性前置步驟，先 persist manifest，
  之後任何以圖 stems 為 expected_outputs 的宣告一律讀 manifest（解 chicken-and-egg）。
- **窮舉清單=spec 附錄 A 交付物**（panel 實測：14 檔 107 處，prod 至少 5 點——
  paper_driver writer prompt 硬編圖清單、tables_inject 三元組、healer 白名單、
  輸出存在性檢查、Gate C；9 個測試檔 69 處）。writer prompt 的圖清單與 tables_inject
  的 (id, filename, caption) 一律由 manifest 模板化生成，caption 是 manifest 欄位。
- 稽核數字（DOI 率/雙源率）**退出正文圖**（Q2 裁決）：改為必產的 provenance 附錄表，
  Gate C 驗「表存在且被 methods 或 data availability 段落引用」，缺任一 fail。
- **廢除 `_ensure_required_minimal_figures`**（由類別 dispatcher 取代）＝明文交付項。

## 5. Gate C 擴充（判準=溯源退化，非數值形狀；各附 healer 可達 pass 態）

| 閘 | fail 條件（溯源判準） | pass（合法事實） | healer 路徑 |
|---|---|---|---|
| C-zi1 溯源退化 | 宣稱比較圖的序列值 provenance **全部指向同一 key 或稽核率類 keys** | 值全等但各 block 有獨立合法溯源 → pass + caption 強制標注 tie | 換 sufficiency 合格的模板或補 tie 標注（不再有「換類別」死路處方） |
| C-zi2 漏斗溯源 | 流程各階段 N **全部溯源自同一 key**（如 bib count 一值填五框） | N 全等但溯源真實檢索 log → pass + caption 揭露 no records excluded | 無階段級資料→降級單框 identification 圖+正文聲明（manifest 記降級） |
| C-zi3 誤差棒溯源 | 誤差棒既無 evidence key 也無 derivation record（公式 id+輸入 keys，閘決定性重算驗證） | 推導 CI 帶 derivation record → pass | 補 derivation record 或去誤差棒 |
| C-zi4 圖溯源 | manifest 缺 entry/provenance，或閘**獨立回 evidence 檔比對數值**不符 | — | 經 assembler 重生成 |
| C-zi5 類別合規 | evidence_fingerprint 一致時：stem ∉ 聯集允許集或無 provenance | — | fingerprint 漂移→**不產 finding**，觸發決定性 re-derive 交易（重分類+圖組+引用改寫） |

- **輸入缺失分支**：manifest/中間數據不存在（legacy run）→ 一律判 `migrate-required`
  觸發 §7 migration，不 pass 不 fail、不裸 fire。
- 覆蓋矩陣明列入 zi1 適用範圍（全 cell 同值=fail）。
- 每閘上線前置：對 golden meta run 跑閘須 0 fail（known-good 假陽鎖）。

## 6. 審查層

- 第八維 `figure_informativeness`（advisory、小權重）；hard 層永遠是 §5。

## 7. 回溯與遷移（v1 政策被推翻，重寫）

1. **migration step 前置**：pre-ADR-002 run 的任何 revalidate，先跑決定性 migration
   （重分類→backfill manifest→圖組重生→sections @fig-* 引用確定性 rewrite），
   禁止 zi4/zi5 對無 manifest run 裸 fire。migration 產物須讓五閘可正常判定（機械驗收）。
2. **存量 inventory 是 S1 交付物**（不再是開放問題）：report-only 模式對全部既有
   done_pass 跑偵測器+zi 閘，產出命中清單（零重開零通知），再依命中內容決定
   pull/annotate/單獨重驅。
3. **已交付 done_pass 的 revalidate 圖閘 fail 不自動 heal**，走 owner-approved 單獨重驅。
4. NILM 案＝migration 路徑的首個 live 驗證案（樣本先行：單案跑通完整路徑——含引用
   改寫與 review 重驗，**不存在 figure-only 重驅**——才開放存量適用）。

## 8. 切片（v1 的 S1 被判過大——ADR-001 slice-1 難產同形——拆為順序子切片）

- **S1a（最小止血，先擋下一篇爛圖）**：偵測器 lite（C1/C4 形狀判定，否則 C2/C0，
  含 probe log）+ figure_manifest v0（schema_version 就位）+ stems 消費點窮舉清單
  （附錄 A）+ DATA_OUTPUTS 動態化 + 地景模板一張（重用既有 year_counts）+ 廢除
  `_ensure_required_minimal_figures`。litmus：NILM 重驅出地景+method_overview 兩張
  誠實圖；golden meta run 行為不變（同 stems 同 verdict）＝硬驗收。
- **S1b**：C-zi1/zi2/zi5（溯源判準）+ migration step + 存量 inventory + 框架圖模板
  （paper-domain 限定+grounding 檢核）。
- **S2**：C-zi3/zi4 + 見證鏈（generator_hash+獨立回驗）+ 覆蓋矩陣模板 + 第八維 +
  provenance 附錄表強制。
- **S3**：決策樹（**兩段式**：上游 contract 先加 schema 驗證的結構化欄位
  `known_threats: [{threat, trigger, decision, kill}]`——現況此欄位只是自由中文，
  全 repo 無結構化資料源；≥3 決策節點才生成）+ C3/C4 模板（等真案例駐留）。

## 9. 審查裁決紀錄（v1→v2）

- 採納（blocker 全數）：zi1/zi2 判準改溯源退化；demotion 紀錄+fingerprint+re-derive 交易；
  C2 probe log+交叉硬閘；見證鏈；migration 前置+golden 0-fail；S1 拆分；決策樹移 S3 兩段式；
  地景 sufficiency predicate；框架圖 paper-domain 限定；覆蓋矩陣入 zi1；Q2 裁決退正文。
- 開放問題收斂後仍待用戶拍板：見 §10。

## 10. 待拍板

- **Q1'**（原 Q1，panel 建議已內建）：C2 必備僅框架圖、其餘選配由 sufficiency predicate
  決定、圖數隨資訊量浮動（1 張也合法）——接受？
- **Q3'**（原 Q3 重寫）：回溯政策 §7（migration 前置+inventory 為 S1 交付+已交付案
  不自動 heal）——接受？
- **Q5**（新）：S1a 先行（僅止血不含新閘），新閘留 S1b——接受此排序？
