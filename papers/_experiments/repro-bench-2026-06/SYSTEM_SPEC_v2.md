# Paper Pipeline System — 規格 v2 (2026-06-11)

> **取代 SYSTEM_SPEC.md (v1, 2026-06-06)**。v1 範圍是「HUPD-like 碩士 benchmark lane」,
> 明寫「不宣稱通用」。v2 起系統已擴成**通用綜合研究引擎**:多 lane + 4 synthesis 類型 +
> 三階梯 tier + capability negotiation + 交付前稽核。v1 留作歷史,本檔是單一真相源。
>
> 手機端 chat.ai 透過 paper MCP 把研究議題收斂成 contract(b),觸發 ac-2012 pipeline(a),
> 產真數據論文。**核心哲學**:每從弱模型(grill)手上拿走一塊「必須正確」的東西改成
> by-construction / 機械閘,就少一個故障點。主觀的留給 chat,確定性的給 a。

## 1. 四層架構(不變)

```
手機 chat.ai (推理大腦) --MCP/SSE--> paper-mcp (Cloudflare Worker)
                                       ├─ D1 (session/project/job/tier) + R2 (PDF/QMD)
                                       --HTTP via Cloudflare Tunnel-->
                                    a job service (ac-2012: FastAPI + job_runner + Hermes big-pickle / codex)
paperlab (Hugo) ── /paper-mcp 子頁發 token + 案例展示
```

| 層 | 職責 | 不做 |
|---|---|---|
| chat.ai | grill 對話、收斂方向 + DOI 清單、feasibility | 不存狀態、不跑 pipeline、不寫 prose paper、不驗 DOI |
| paper-mcp (b) | grill 框架 + state machine + 把 contract 交給 a | 不跑 LLM grill、不跑論文、**不驗 DOI**、不做 compute |
| a (ac-2012) | router + lane 分派 + 真實驗/分析 + 真修正迴圈 + 渲染 + 審查 + 交付稽核 | 不管 grill/UI |
| paperlab (Hugo) | 展示 + token 發放 | 不做工具邏輯 |

## 2. 執行 lane(v2 擴張的核心)

a 依 `data_source.type` 分派:

| lane | data_source.type | 引擎 | 回答 |
|---|---|---|---|
| **實驗 benchmark** | dataset (HUPD) | real_patent_experiment.py | 分類器效能(碩士應用型) |
| **文獻地景** | literature | openalex_analysis.py | 領域版圖/趨勢/熱點(scientometric) |
| **統合分析** | meta-analysis | meta_analysis.py → synthesis.py | 成效/盛行率/關聯/診斷準確度 |

### 2a. 統合分析 = 通用綜合方法庫 `synthesis.py`

領域無關。一個 DerSimonian-Laird 隨機效應核心 + 4 scale transform:

| synthesis.type | 合併數學 | 問題形狀 |
|---|---|---|
| intervention | log-ratio(OR/RR/HR)+ raw(SMD/MD) | X 有沒有效 |
| prevalence | proportion(logit) | 多普遍 |
| correlation | OR/HR + Fisher-z(r) | A 跟 B 有關嗎 |
| diagnostic | sensitivity/specificity(logit) | 診斷多準 |

- **PICOS 篩選**(`screen_picos`):exclude_terms / require_any **來自 contract,不寫死** → 換題目零改動
- **moderator 標記**:contract `picos.moderators=[{name,levels:{level:[kw]}}]` → 按關鍵詞替效應打標 → subgroup 按 level 合併(承諾的 subgroup 才真跑)
- **敏感度套件**:Egger / leave-one-out / subgroup(純數學,把 reviewer「precluded」變「performed」)
- **確定性圖**:`meta_figures.py` forest plot + PRISMA flow(從真 pooled 數字機械繪,圖不可能跟分析打架)
- **誠實邊界**:摘要層抽取、無全文 → 探索性綜述,非全 PRISMA 系統性回顧(寫進 Limitations)

## 3. 三階梯 tier(v2 核心商業/技術軸)

「超出免費」三條軸(更多數據 / 更多運算 / 需人工專業)收斂成同一個付費客製層,跟 GPU、衝 Q1 同 tier:

| 階梯 | 跨越 | 例 | 怎麼跑 |
|---|---|---|---|
| **免費自動**(member/CPU/master 7.5) | — | 摘要層 DL、4 類型、Egger/LOO/subgroup | 全自動到 PDF |
| **Pro 自動**(vip/phd 8.0) | 更多運算 | 更深掃描、(規劃中)Bayesian 階層式合併 | 自動,較重 |
| **客製顧問**(付費 + 人工) | 更多數據 + 人工判斷 | 全文 PRISMA、RoB2/GRADE、Bayesian LCA、network MA、IPD、GPU 實驗 | 人工,報價 |

- a `/capabilities.synthesis` 廣告 `automated` vs `customized`(三類)
- grill 撞客製層**不說做不到**,說「客製顧問層,先給自動 DL 版 or 登記付費客製」
- router:`TIER_MAX_LEVEL`(free→master / vip→{master,phd,journal})、`LEVEL_THRESHOLDS`(master 7.5 / phd 8.0)、GPU 需人工核准 + TG 通知

## 4. Capability negotiation(防 grill 過度承諾,雙層)

grill 太聰明會把題目推出引擎能力(burnout 案承諾 Bayesian LCA)。雙層防護:

1. **前端引導(b)**:start_brainstorm fetch a `/capabilities` 的 synthesis 邊界 → 回 `engine_capabilities` + 硬規則「題目只能寫 automated 方法」
2. **後端校正(a, backstop)**:meta_metrics_block 硬指示 writer 把標題/方法的 not_supported 方法改寫成實跑的 DL(grill 漏了 a 也救)

外加 v2 contract negotiation:`schema_hash` pin、experiment recipe 可執行性 gate、contract_version 協商。

## 5. 確定性閘 + 審查 + 交付稽核

- **contract 邊界 sanitize(b)**:`level`/`tier`/`source`/`target_journal` 是 server 決定(tier-gated),從 chat overrides strip(防 unsupported-level + privesc);DOI 不在 b 驗(a 單源 CrossRef)
- **submit 前 dry-run(b)**:POST 前先打 a `/jobs/dry-run`,壞 contract 乾淨回錯、不變 pending_sync(fail-open)
- **reviewer 串接**:copilot → codex(雙帳號輪替)→ big-pickle-skilled → deterministic_floor(lane-aware:meta lane 用綜合分析評分表,非 HUPD)
- **修正迴圈**:degradation ladder + never-ship-worse rollback + citation-key 不可變
- **渲染**:Quarto + elsevier-pdf + xelatex;確定性 natbib finisher;CJK 字型注入
- **交付前稽核(`delivery_audit.py`)**:系統化的人肉 QA 過濾層。合併 render-quality RQ_* + 人眼才抓到的類別(D1 引用太少 / D2 承諾超能力 / D3 subgroup 空頭 / D4 type 不符)。wire 進 extract_output,P0 進 blockers。失敗案例庫 = skill `paper-delivery-audit`

## 6. 資料流(端到端)

```
1. chat.ai 接 connector (URL?token=) → start_brainstorm(收 engine_capabilities)
2. 5 步 grill(資料源那步 probe_data_source 確認可達)→ 收斂方向 + DOI 清單
3. propose → save_project(status=ready)
4. submit_to_pipeline → b sanitize contract → dry-run → POST a /jobs → job_id
5. a: data gate → lane 分派 → 真分析 → 真修正迴圈 → 渲染 → 審查 → 交付稽核 → done
6. 產物存 R2;chat poll get_job_status / get_paper_result;達標案例 → 上架 paperlab
```

## 7. 運維約束(踩過的雷 → 硬規則)

- **job 在跑時可安全部署**:systemd unit `KillMode=process` → restart 只換 uvicorn,in-flight worker(start_new_session 子進程)續活。**但**改 unit/重大依賴仍要確認沒 in-flight job
- **部署用絕對路徑 + md5 驗證**:scp 後 ssh 比對 md5,別 `>/dev/null` 吞錯(r6 silent deploy 失敗教訓)
- **secret 不上 SSH 命令列**:用檔案傳輸;TG token 只寫前綴遮蔽
- **level/tier 永遠 server 決定**:chat 不可設(Q2-Q3 bug + privesc)

## 8. 不做(避免過度工程)

- ❌ 不整合 paperlab(獨立 MCP)
- ❌ 摘要層不假裝做 Bayesian LCA / RoB2 / 全文(誠實標客製層)
- ❌ 不靠 LLM 做交付稽核(純機械;LLM 評分是 reviewer 的事)

## 9. 細節文件指標

grill = PAPER_MCP_GRILL_DESIGN.md｜MCP 工具 = PAPER_MCP_SERVER_SPEC.md｜
contract schema = newarch/job_service_schema.md｜失敗案例庫 = skill paper-delivery-audit｜
grill 案例 = grill_records/*.md
