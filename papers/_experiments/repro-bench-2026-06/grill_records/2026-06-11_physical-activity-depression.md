# Grill Record — 身體活動量與憂鬱風險之關聯 (correlation meta-analysis)

> 來源:chat.ai PaperLab,2026-06-11。用戶:alan.chen75 (VIP)。
> 用途:**第一個 submit 失敗案**(unsupported level → pending_sync)+ pending_sync 機制分析。
> job: proj_2026-06-11_234d5240｜synthesis.type=correlation｜**submit 失敗,卡 pending_sync**。

## 一句話起點
「我想研究:身體活動量跟憂鬱風險的關聯」

## 5 步 grill 決策
| 步 | 選擇 | 重點 |
|---|---|---|
| 3 | **D + correlation** | 正確判定關聯型 → correlation;probe OpenAlex 91,821 筆 |
| 4 | B 穩健 Q2-Q3 | 誠實提醒此題已大量做過,純合併難上 Q1 |
| 5 | A 完整論文 | — |

種子文獻 5 篇全驗證(Schuch 2018 / Pearce 2022 JAMA Psych / Guo 2022 dose-response / Wang 2025 / Yu 2025 UK Biobank)。Gap:更新 2022 後文獻 + 比較測量方式/活動型態/久坐替換/族群差異。

## ❌ submit 失敗:`unsupported level: Q2-Q3`
- chat 把 journal_tier「Q2-Q3」塞進了 contract 的 **level** 欄位
- a router(`router.py:64`):level 必須 ∈ {master, phd, journal},否則 raise → **422**
- b 沒擋:`safeOverrides` 沒 strip `level`,壞值漏過去覆蓋了 server 推導的 defaultLevel
- a 正確 fail-closed,但 project 卡 **pending_sync**

## 根因 + 修法(commits 445a11c + 8e7f8a8)
1. **防漏(b)**:`level`/`tier`/`source`/`target_journal` 是 tier-gated server 決定,從 overrides strip 掉。venue 企圖只走 `meta.journal_tier → defaultLevel`。順帶補一個 **privesc 洞**(`tier` 可被 chat 設成 vip)。
2. **fail-fast(b)**:submit 前先打 a 的 `/jobs/dry-run`;contract 被拒就乾淨回錯、**project 留 ready 不變 pending_sync**。dry-run fail-open(a 掛了不擋有效 submit,真 POST 仍把關)。

## pending_sync 機制分析(用戶問「如何處理」)
- **設計**:submit 是 D1-first——先標 pending_sync + 存 contract mapping,**才** POST。POST 崩潰不丟記錄。
- **轉移**:a 接受→submitted(寫 pipeline_job_id);a 拒→留 pending_sync + 寫 pipeline_error。
- **可重試**:re-submit 同 project_id 會重打(idempotency key 防 double-trigger)。
- **缺口(已補)**:原本「POST 了才知被拒」→ 加 dry-run 前置,壞 contract 連 pending_sync 都不會變成。
- **恢復本案**:journal_tier=B + vip → 修後 defaultLevel=phd(合法)。**用戶回 chat 重 submit 即可恢復**(現在 dry-run 會先過)。

## meta(對系統的意義)
capability-alignment 擋住了「方法層」過度承諾(Bayesian/network),但**「欄位語意混淆」是另一類**——chat 把 journal_tier 當 level。修法同源:**tier-gated 欄位一律 server 決定、不信 chat**(boundary sanitization)。dry-run 前置 = pending_sync 的防禦縱深。
