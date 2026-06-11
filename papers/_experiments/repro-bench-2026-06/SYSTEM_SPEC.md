# Paper Pipeline System — 完整系統規格 v1（2026-06-06）

> ⚠️ **已被 SYSTEM_SPEC_v2.md 取代（2026-06-11）**。v1 範圍是「HUPD 碩士 benchmark lane」、
> 明寫「不宣稱通用」；v2 起系統已擴成多 lane + 4 synthesis 類型 + 三階梯 tier + capability
> negotiation + 交付稽核。**單一真相源是 v2**，本檔留作歷史參照。
>
> 手機端 chat.ai 透過 paper MCP 形成研究議題（b），觸發 ac-2012 的論文產出 pipeline（a），
> 產出真數據草稿。碩士應用型用免費池達標（6.0），博士創新型走付費 + 完整研究 lane（7.0+）。
> 細節文件：grill 設計 = PAPER_MCP_GRILL_DESIGN.md；MCP 工具 = PAPER_MCP_SERVER_SPEC.md；
> contract schema = newarch/job_service_schema.md。本檔是整合 + 部署總規格。

## 1. 架構總覽（4 層）

```
手機 chat.ai (推理大腦) --MCP/SSE--> paper-mcp (Cloudflare Worker, 獨立 repo)
                                        ├─ D1  (結構化: session/job/tier)
                                        └─ R2  (產出物: PDF/QMD)
                                        --HTTP via Cloudflare Tunnel-->
                                     a job service (ac-2012: FastAPI + job_runner + Hermes)
paperlab (Hugo 網站) ── /paper-mcp 子頁(發 token) + 案例展示
```

| 層 | 職責 | 不做 |
|---|---|---|
| chat.ai | grill 對話、推理、選項生成 | 不存狀態、不跑 pipeline |
| paper-mcp (Worker) | grill 框架 + state machine + research 工具 + 轉發 a | 不跑 LLM grill、不跑論文 |
| a (ac-2012) | router + job_runner + Hermes 產論文 | 不管 grill/UI |
| paperlab (Hugo) | 展示 + token 發放子頁 | 不做工具邏輯 |

## 2. 部署拓撲

| 元件 | 平台 | repo | 說明 |
|---|---|---|---|
| paper-mcp | Cloudflare Worker | **ai-cooperation/paper-mcp**（獨立新 repo） | SSE MCP server |
| D1 | Cloudflare D1 | (同上) | session/findings/job-meta/users/idempotency |
| R2 | Cloudflare R2 | (同上) | 論文產出物 PDF/QMD |
| Tunnel 橋 | cloudflared on ac-2012 | — | 把 a 的 FastAPI 對外（公網 Worker → Tailscale 內網） |
| a job service | ac-2012 | (現有 newarch/) | FastAPI + job_runner + Hermes big-pickle |
| 入口子頁 | paperlab Hugo | ai-cooperation/paperlab（現有） | /paper-mcp 發 token + connector URL |

## 3. 端到端資料流

```
1. 用戶手機 chat.ai 接 paper-mcp connector (URL?token=, 從 paperlab 子頁取)
2. start_paper_session → grill 7 步(層級先定: master/phd) → record_grill_decision
3. deep_research + probe_data_source(調 a data gate) + add_finding(source_url)
4. assess_feasibility(價值/創新/資料) → confirm_research_contract(輸出 a schema 含 level)
5. submit_to_pipeline → Worker POST (Tunnel) → ac-2012 /jobs → job_id (即回)
6. ac-2012 跑: data gate → 真實驗 → 真數據整合 → 真修正迴圈 (分鐘級, async)
7. chat.ai poll get_job_status → done → get_paper_result (content_score/meets_threshold/pdf)
8. 產出存 R2; 達標案例 → case-publish → paperlab 展示
```

## 4. a 段規格（ac-2012, 第一步要建）

**FastAPI wrapper over job_runner（codex 建議,非 raw Popen）**:
| endpoint | 作用 |
|---|---|
| `POST /jobs/dry-run` | validate contract against router.validate_contract → 回 route + derived threshold（**先揪 schema mismatch**） |
| `POST /jobs` | 需 **idempotency key** + 建 persisted state(SQLite/jobs dir) → job_id |
| `GET /jobs/{id}/status` | map job_runner.status (submitted→running→data-gate→done/blocked) |
| `GET /jobs/{id}/result` | map job_runner.result (content_score/meets_threshold/level/pdf/blockers) |

- research_contract schema = newarch/job_service_schema.md（含 level/tier/data_source/content_threshold）— **單一真相源**
- 既有閉環: router.py(路由含 level) + job_runner.py + Hermes big-pickle + data gate(fail-closed)

## 5. b 段規格（paper-mcp Worker）

- 工具(引用 PAPER_MCP_SERVER_SPEC.md): 流程引導(start/record_decision/confirm) + 執行(deep_research/probe/add_finding/assess/submit/status/result)
- **state machine**(codex 強調,別當被動文件服務): grill 步驟強制順序,level 先定再約束後續選項
- **缺工具補**: get_paper_session / list_paper_sessions / resume_paper_session / search_existing_topics / validate_research_contract
- grill 7 步 + 層級分流 = PAPER_MCP_GRILL_DESIGN.md

## 6. 資料模型

**D1 tables**:
- `sessions`(session_id, user_id, level, tier, grill_state, contract_draft, created/updated)
- `findings`(finding_id, session_id, claim, source_url, created)
- `jobs`(job_id, session_id, user_id, status, content_score, meets_threshold, r2_pdf_key, created)
- `users`(user_id, tier, quota_used, quota_limit)
- `idempotency`(key, job_id, created)

**R2**: `papers/{job_id}/paper_draft_v0.pdf`, `.qmd`, `real_results.json`

**research_contract**: 真相源在 a 的 job_service_schema.md(b 只填+驗證)

## 7. 安全 + Production（codex 缺漏清單）

- **token**: paperlab /paper-mcp 子頁發 fine-grained token → chat.ai connector URL `?token=`（mcp-connector-pattern）
- **idempotency**: `POST /jobs` 必帶 key（防重複觸發真 compute）
- **rate limit + quota/tier cost**: free 慢/限量(big-pickle), vip 付費(agy→codex) — 路由已分,加每用戶 quota 計數
- **submit 確認**: submit_to_pipeline 觸發真 compute,要明確確認
- **audit log**: 每次 submit/job 寫審計
- **Tunnel auth**: cloudflared 綁 token,只 Worker 可調 ac-2012

## 8. 實作順序（codex 定，最高槓桿優先）

```
1. a FastAPI wrapper + POST /jobs/dry-run(contract adapter test)  ← 第一步,釘死 a/b 接口
2. Cloudflare Tunnel: ac-2012 跑 cloudflared 把 a 對外(綁域名+token)
3. paper-mcp Worker 骨架: start_session + grill state machine + confirm_contract + D1
4. 執行工具: probe→a data gate, submit/status/result→a HTTP(Tunnel), deep_research, R2
5. 安全: token/idempotency/quota/audit
6. paperlab /paper-mcp 子頁(發 token) + 接 chat.ai SSE → 手機端全鏈測試
```

## 9. 不做（codex push back，避免過度工程）

- ❌ 不整合 paperlab（保持獨立 MCP）
- ❌ 不現在抽象 insurance/paper MCP 共用 base（reuse pattern 即可，領域會分歧）
- ❌ 不宣稱「通用 production-ready」—— 目前是「HUPD-like 碩士/應用型 benchmark lane」就緒；其他 lane 要各自驗證
