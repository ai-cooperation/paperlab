# AI 學術研究工作坊 — 完整評估報告與實施計畫 v2.1
# Evaluation Report & Implementation Plan

> 日期：2026-03-06
> 版本：v2.1（更新至 55 頁簡報，含 API 驗證、Obsidian、主編分析、平行審查等新增內容）
> 評估人：Claude Code AI 系統分析

---

## 一、現有簡報 vs 升級版對比評估

### 1.1 現有簡報分析（AI研究工作坊_完整課程簡報.pptx，27 頁）

**優勢**：
- 流程清晰：6 個階段的視覺化總覽
- CARE 框架設計完整
- Prompt Engineering 教學紮實
- 圖文搭配良好，視覺設計專業

**不足之處**：

| 項目 | 現有版本 | 需要改進 |
|------|---------|---------|
| 工具深度 | 提到 Claude Code 但未深入 | 需展示 24 Skills + 8 Agents + 5 Commands 完整系統 |
| 實際案例 | 以虛構 HTF-CNN 為例 | 應用真實 NILM+LLM 論文完整歷程 |
| 自動化程度 | 概念層面 | 需展示 `/review-paper` 等一鍵工作流 |
| 文獻驗證 | 僅提概念 | 需展示 CrossRef/Semantic Scholar/OpenAlex API 驗證流程 |
| 知識管理 | 未涵蓋 | 需加入 Obsidian 知識圖譜 + 雙向連結 |
| 統計驗證 | 未涵蓋 | 需加入 Bootstrap、效果量、功效分析 |
| 品質保證 | 6 維度評分 | 升級為 7 維度 + P0-P3 分級 + 三 AI 平行審查 |
| 投稿流程 | 簡略 | 需加入 Cover Letter、rebuttal-matrix、10 項素材清單 |
| 期刊匹配 | 只看 Scope | 需加入主編分析、近期收錄主題分析、6 維度評分 |
| 可帶走的系統 | 無 | 提供 research-workspace.zip |
| 遠端執行 | 未涵蓋 | 需展示 GPU + Telegram Bot 三層監控 |
| 圖表製作 | 未涵蓋 | 需展示 SVG 向量圖 + QMD→TeX 轉換 |
| 多 AI 審查 | 只用一個 AI | 需展示 Claude×ChatGPT×Gemini 平行審查 |

### 1.2 升級版新增內容統計

| 類別 | 新增內容 | 頁數 |
|------|---------|------|
| 完整工具生態系 | 24 Skills + 8 Agents + 5 Commands 全覽 | +4 頁 |
| 真實案例完整歷程 | NILM+LLM → SETA 投稿全流程 | +3 頁 |
| API 驗證流程 | CrossRef/Semantic Scholar/OpenAlex 三重驗證 | +3 頁 |
| Obsidian 知識圖譜 | 文獻筆記卡 + 雙向連結 + Graph View | +2 頁 |
| 主編分析 + 期刊匹配 | 6 維度加權評分 + EIC 偏好分析 | +2 頁 |
| IMRaD + YAML + QMD | 標準架構 + 期刊格式配置 | +2 頁 |
| IDE + GPU + Colab | VS Code 工作流 + 三層執行環境 | +2 頁 |
| TG Bot 監控 | 三層監控系統 + 即時通知 | +1 頁 |
| 統計驗證教學 | Bootstrap, Mann-Whitney, Cohen's d | +2 頁 |
| SVG + QMD→TeX | 向量圖製作 + 快速格式轉換 | +1 頁 |
| P0-P3 品質管控 | 致命/嚴重問題分級與修復 | +2 頁 |
| 平行審查 | Claude×ChatGPT×Gemini 三 AI 交叉檢查 | +1 頁 |
| 投稿全流程 | Cover Letter + Rebuttal + 10 項素材 | +2 頁 |
| 系統部署 | research-workspace.zip 安裝 | +1 頁 |
| **合計新增** | | **+28 頁** |
| **預估總頁數** | 27 原始 - 5 合併 + 28 新增 + 5 更新 = **55 頁** | |

---

## 二、技能覆蓋率評估

### 2.1 論文生命週期各階段的工具覆蓋

```
Phase         Coverage   Tools Used                                      Gap
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
P1 概念探索    ████████░░  80%   Claude Chat, Extended Thinking           缺系統性方法
P2 文獻調研    ██████████  95%   CrossRef/SS/OA API, Zotero, Obsidian    已完善(v2.1)
P3 研究定位    █████████░  90%   innovation-pos, journal-fit, EIC分析     已完善(v2.1)
P4 論文架構    ██████████  95%   IMRaD, QMD+YAML, evidence-indexer       已完善(v2.1)
P5 實驗設計    █████████░  90%   experiment-tracker, IDE+GPU, protocol    已完善
P6 實驗執行    ████████░░  80%   gpu-monitor, SSH, TG Bot 三層監控        已改善(v2.1)
P7 數據分析    █████████░  90%   stats-validator, metric-audit, Skill     已完善
P8 論文撰寫    ██████████  95%   paper-writer, SVG, QMD→TeX, 轉投策略     已完善(v2.1)
P9 品質審查    ██████████  100%  Claude×ChatGPT×Gemini 平行審查           完全覆蓋(v2.1)
P10 投稿準備   █████████░  90%   submission-helper, bundle, 10項清單      已完善(v2.1)
P11 審稿回覆   ████████░░  80%   rebuttal-matrix                          缺實戰經驗
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Overall:       90% (↑3% from v1.0)
```

### 2.2 課程對工具的教學覆蓋率

| 工具類型 | 總數 | 課程涵蓋 | 覆蓋率 |
|---------|------|---------|--------|
| Skills | 24 | 20 (完整/Demo) | 83% (↑8%) |
| Agents | 8 | 8 (全部) | 100% |
| Commands | 5 | 5 (全部) | 100% |
| 外部工具 | 12 | 10 | 83% |
| API 服務 | 4 | 4 (CrossRef/SS/OA/Unpaywall) | 100% (NEW) |

### 2.3 v2.1 新增覆蓋的工具與服務

| 工具/服務 | 類型 | 教學深度 | Session |
|----------|------|---------|---------|
| CrossRef API | 文獻驗證 | 完整教學 + curl Demo | D1/S2 |
| Semantic Scholar API | 文獻驗證 | 完整教學 + Demo | D1/S2 |
| OpenAlex API | 文獻驗證 | 概念 + Demo | D1/S2 |
| Zotero | 文獻管理 | 4 種匯入方式 | D1/S2 |
| Obsidian | 知識管理 | 筆記卡 + Graph View | D1/S2 |
| ChatGPT (GPT-4o) | 平行審查 | Prompt + Demo | D2/S5 |
| Gemini 2.5 Pro | 平行審查 | Deep Research Demo | D2/S5 |
| Inkscape | SVG 後處理 | Demo | D2/S4 |
| Google Colab | GPU 訓練 | 實戰流程 | D2/S3 |
| VS Code Remote-SSH | 遠端開發 | Demo | D2/S3 |

### 2.4 未涵蓋的 4 個 Skills（進階選修）

| Skill | 原因 | 建議 |
|-------|------|------|
| `software-dev-quality-guard` | 偏軟體開發，非學術研究 | 不需涵蓋 |
| `data-preprocessing` | 領域特定（NILM 數據） | 可在進階班補充 |
| `baseline-min-set` | 進階實驗設計 | 可在進階班補充 |
| `split-leakage-audit` | 進階數據科學 | 可在進階班補充 |

---

## 三、學員能力評估矩陣

### 3.1 入口能力要求

| 能力 | L1D2（Day 1） | L2D1（Day 2） |
|------|--------------|--------------|
| AI 基礎 | 用過 ChatGPT/Claude | 能寫結構化 Prompt |
| 研究能力 | 有基本研究概念 | 有明確研究主題 |
| 技術能力 | 會用瀏覽器 | 會用 Terminal 基本操作 |
| 寫作能力 | 會寫報告 | 了解論文結構 |
| 工具 | 無特殊要求 | 已安裝 VS Code |

### 3.2 出口能力目標

| 能力 | Day 1 結束 | Day 2 結束 |
|------|-----------|-----------|
| Prompt Engineering | CARE 框架熟練 | 研究專用 Prompt 自如 |
| 文獻管理 | API 驗證 + Obsidian 筆記卡 | BibTeX 系統化管理 |
| 知識圖譜 | Obsidian Graph View 建立 | 文獻矩陣→Related Work |
| 論文撰寫 | — | QMD + YAML + SVG 完整流程 |
| 品質保證 | — | 多 AI 平行審查 + 七維度分析 |
| 工具使用 | Claude Chat + API 驗證 | Claude Code + ChatGPT + Gemini |
| 自動化 | 概念了解 | 能部署 research-workspace |

### 3.3 Bloom 分類法對應

| 層級 | Day 1 | Day 2 |
|------|-------|-------|
| 記憶 | AI 研究工具名稱 + API endpoint | Skills/Agents 名稱 |
| 理解 | CARE 框架原理 + API 驗證邏輯 | QMD/BibTeX/IMRaD 原理 |
| 應用 | 用 Prompt 做文獻搜索 + API 驗證 | 用 QMD 寫論文 + 平行審查 |
| 分析 | Research Gap 識別 + 主編偏好分析 | P0-P3 問題分級 |
| 評估 | 期刊匹配 6 維度評分 | 七維度論文評分 + 三 AI 比對 |
| 創造 | 研究方向設計 + Obsidian 知識網絡 | 完整論文框架 + 投稿策略 |

---

## 四、風險評估與應對方案

### 4.1 教學風險

| 風險 | 機率 | 影響 | 應對方案 |
|------|------|------|---------|
| Claude API 不穩定 | 中 | 高 | 準備離線 Demo 錄影 + 本機快取範例 |
| ChatGPT/Gemini 無法使用 | 低 | 中 | 準備截圖/錄影；Claude 可單獨完成審查 |
| 學員程度差異大 | 高 | 中 | 準備進階/基礎兩套實作任務 |
| Claude Code 安裝失敗 | 中 | 中 | 準備預裝 VM 或 Docker 映像 |
| Quarto 安裝問題 | 低 | 中 | 準備 Web IDE（quarto.org playground） |
| API 服務暫時無回應 | 中 | 低 | 準備 API 回應快取 JSON（CrossRef/SS） |
| 時間不夠 | 高 | 中 | 每個 Session 標記「必教/選教」 |
| 學員無研究主題 | 中 | 低 | 準備 5 個範例研究主題供選擇 |

### 4.2 技術風險

| 風險 | 機率 | 應對方案 |
|------|------|---------|
| 網路不穩 | 中 | 準備離線素材 + 手機熱點備用 |
| 投影設備問題 | 低 | 測試 + 備用筆電 |
| API 費用超支 | 低 | 設定每人用量上限 |
| Obsidian 外掛不相容 | 低 | 準備預配置 Vault zip |

---

## 五、成本估算

### 5.1 課程執行成本

| 項目 | 單位成本 | 30 人班 |
|------|---------|---------|
| Claude API（教學 Demo） | ~$8/天 | $16 |
| Claude API（學員實作） | ~$3/人/天 | $180 |
| ChatGPT Plus（教學帳號） | $20/月 | $20 |
| Gemini Advanced（教學帳號） | $20/月 | $20 |
| 場地（假設自有） | $0 | $0 |
| 教材印刷 | $5/人 | $150 |
| 茶點 | $10/人/天 | $600 |
| **合計** | | **~$986** |

### 5.2 課程開發成本（一次性）

| 項目 | 估計工時 |
|------|---------|
| 簡報升級（27→55 頁） | 24h |
| API 驗證腳本 + Demo 準備 | 4h |
| Obsidian 範例 Vault 建置 | 4h |
| 實作教材準備 | 8h |
| Demo 腳本與錄影（含平行審查） | 10h |
| research-workspace 打包 | 4h |
| 範例研究主題準備 | 4h |
| 測試與修正 | 8h |
| **合計** | **66h** |

---

## 六、實施時程計畫

### 6.1 準備階段（開課前 4 週）

```
Week -4: 確認開課日期、場地、學員名單
         └ 發送前置準備通知（安裝軟體、準備研究主題）
         └ 確認 Claude/ChatGPT/Gemini 教學帳號

Week -3: 簡報升級製作
         └ 新增 28 頁簡報（API 驗證、Obsidian、平行審查...）
         └ 更新真實案例（NILM+LLM → SETA）
         └ 準備 API 驗證腳本 + Obsidian Vault

Week -2: 教材準備
         └ 實作練習教材（Handout）含 API curl 命令
         └ Demo 腳本撰寫與錄影（含三 AI 平行審查）
         └ research-workspace.zip 打包測試
         └ 準備 API 回應快取（離線備用）

Week -1: 最終測試
         └ 完整 Run-through（模擬教學）
         └ 技術環境測試（網路、投影、API、Obsidian）
         └ 備用方案確認（離線素材、快取）
```

### 6.2 執行階段

```
Day 1 (L1D2):
  09:00  開場 + AI 趨勢
  09:30  Session 1: 概念探索 + Prompt Engineering
  11:00  Session 2: 文獻查找 + API 驗證 + Obsidian
  13:00  Session 2 續: BibTeX + Literature Review + 主編分析
  14:45  自動化工具 + 實作練習 1（含 API 驗證 + Obsidian 筆記卡）
  16:00  回顧 + 作業

Day 2 (L2D1):
  09:00  回顧 + 中階導入（8 Agent 團隊）
  09:20  Session 3: IMRaD 架構 + YAML + IDE/GPU + TG Bot
  11:00  數據彙整 + Skill 自動驗證 + 統計
  13:00  Session 4: QMD 撰寫 + SVG + 轉投策略
  14:15  Claude Code 自動化（3 個完整 Demo）
  15:00  Session 5: 平行審查（Claude×ChatGPT×Gemini）+ 品質保證
  16:30  投稿策略 + 系統部署 + 總結
```

### 6.3 後續追蹤（開課後）

```
Week +1: 發送 research-workspace.zip + Obsidian Vault + 安裝指南
Week +2: 線上 Q&A（1 小時）
Week +4: 學員成果回報（研究方向 + 文獻管理 + API 驗證）
Week +8: 進階班招生（針對有論文進度的學員）
```

---

## 七、與現有簡報的頁面對照

### 保留頁面（27 頁中保留 13 頁原樣）

| 原始頁碼 | 內容 | 處理 |
|---------|------|------|
| 1 | 封面 | 保留，更新副標題 |
| 4 | Day 1 封面 | 保留 |
| 5 | 為什麼需要 AI | 保留 |
| 6 | Session 1 概念探索 | 保留 |
| 7 | CARE 框架 | 保留 |
| 8 | 多輪對話策略 | 保留 |
| 10 | 文獻整理流程 | 保留 |
| 12 | Apps Script | 保留 |
| 14 | Day 2 封面 | 保留 |
| 24 | 期刊策略 | 保留 |
| 27 | 結尾 | 保留 |

### 大幅更新頁面（10 頁）

| 頁碼 | 內容 | 更新 |
|------|------|------|
| 2 | 流程總覽 | 6→11 Phase |
| 3 | 議程 | 加入新 Session + 新工具 |
| 9 | Session 2 文獻策略 | 加入 API 驗證 + Obsidian |
| 11 | Abstract 捕捉 | 加入 5 維度評估 |
| 13 | Day 1 回顧 | 更新實作內容（API + Obsidian） |
| 15-17 | Session 3 | 加入 IMRaD + YAML + GPU |
| 21 | Claude Code | 擴充為 Skill/Agent/Command 系統 |
| 25 | 完整流程 | 更新為 11 Phase |
| 26 | 下一步 | 加入部署指南 |

### 新增頁面（+32 頁）

| 編號 | 內容 | 位置 |
|------|------|------|
| S3 | 案例：NILM+LLM → SETA 投稿歷程 | 開場後 |
| S10 | 24 Skills + 8 Agents + 5 Commands 全覽 | S1 後 |
| S11 | 種子 DOI 生成 + AI 產出警告 | S2 |
| S12 | CrossRef API 驗證 Demo | S2 |
| S13 | Semantic Scholar + OpenAlex API | S2 |
| S14 | Zotero 批次匯入 4 種方式 | S2 |
| S15 | Obsidian 文獻筆記卡格式 | S2 |
| S16 | Obsidian Graph View 知識圖譜 | S2 |
| S17 | BibTeX 進階管理 + bib-manager | S2 |
| S18 | Research Gap + literature-synthesis | S2 |
| S19 | 期刊匹配 6 維度評分 | S2 |
| S20 | 主編分析方法 | S2 |
| S22 | 8 Agents 專家團隊 | D2 開場 |
| S23 | 5 Commands 一鍵工作流 | D2 開場 |
| S30 | IMRaD 架構詳解 | S3 |
| S31 | MD→QMD + YAML 檔頭 | S3 |
| S32 | 期刊格式 YAML 對照表 | S3 |
| S34 | IDE 工作流（VS Code） | S3 |
| S35 | 三層執行環境（本地/Colab/3090） | S3 |
| S36 | TG Bot 三層監控 | S3 |
| S37 | Skill 驅動自動化驗證 | S3 |
| S38 | 數據一致性三角檢查 | S3 |
| S39 | 統計方法選擇 + Bootstrap/CI | S3 |
| S41 | 轉投策略 + 主編匹配 | S4 |
| S42 | SVG 向量圖 + QMD→TeX | S4 |
| S43 | Skills 架構 + 3 個完整 Demo | S4 |
| S47 | 平行審查 Claude×ChatGPT×Gemini | S5 |
| S48 | P0-P3 品質分級系統 | S5 |
| S49 | 七維度評分框架 | S5 |
| S50 | Reviewer 預測問答 | S5 |
| S51 | 投稿 10 項素材清單 | S5 |
| S54 | 系統部署 + research-workspace | 結尾前 |

### 簡報頁數統計

| 類別 | 頁數 |
|------|------|
| 保留原樣 | 13 |
| 大幅更新 | 10 |
| 全新增加 | 32 |
| **總計** | **55** |

---

## 八、KPI 與成功指標

### 8.1 課程成功指標

| 指標 | 目標值 | 衡量方式 |
|------|--------|---------|
| 學員滿意度 | >= 4.2/5.0 | 課後問卷 |
| 實作完成率 | >= 80% | 當場檢查（含 API 驗證 + Obsidian） |
| 工具部署率 | >= 50% | Week +2 追蹤 |
| API 驗證掌握率 | >= 70% | D1 實作檢查 |
| 平行審查理解率 | >= 60% | D2 課後問卷 |
| 論文進度推動 | >= 30% 有進展 | Week +8 回報 |
| NPS 淨推薦值 | >= 40 | 課後問卷 |

### 8.2 內容品質指標

| 指標 | 目標值 |
|------|--------|
| 講述:Demo:實作 比例 | 46%:27%:27% |
| 每個 Session 至少 1 次實作/Demo | 100% |
| 真實案例佔比 | >= 60% |
| 工具覆蓋率（Skills+Agents+Commands+API） | >= 85% |
| 多 AI 工具使用 | 3 種（Claude+ChatGPT+Gemini） |

---

## 九、v1.0 → v2.1 改進摘要

| 面向 | v1.0 | v2.1 | 提升幅度 |
|------|------|------|---------|
| 簡報頁數 | 45 頁 | 55 頁 | +22% |
| 工具覆蓋率 | 87% | 90% | +3% |
| Skills 教學覆蓋 | 75% (18/24) | 83% (20/24) | +8% |
| 外部工具 | 6 種 | 12 種 | +100% |
| API 服務 | 0 | 4 種 | NEW |
| 文獻驗證 | 概念 | 完整 API 驗證流程 | 質變 |
| 知識管理 | 無 | Obsidian 知識圖譜 | NEW |
| 期刊匹配 | Scope 只看 | 6 維度 + 主編分析 | 質變 |
| 品質審查 | 單 AI | 三 AI 平行審查 | 質變 |
| 圖表製作 | 概念 | SVG + QMD→TeX | 質變 |
| 實驗監控 | 無 | TG Bot 三層監控 | NEW |
| 投稿準備 | 簡略 | 10 項素材清單 | 質變 |

---

## 十、未來擴展方向

### 10.1 進階課程（L2D2 中階進階）

| 內容 | 時長 |
|------|------|
| 完整 Ablation Study 設計與執行 | 2h |
| 高階統計（Meta-analysis, Bayesian） | 2h |
| 多機器遠端實驗管理 | 1h |
| CI/CD for Research（自動化論文產線） | 2h |
| 審稿回覆實戰演練 | 1h |

### 10.2 領域專班

| 領域 | 客製內容 |
|------|---------|
| 能源/永續 | NILM + 能源審計案例 |
| 製造/工業 | 智慧製造 + IoT 數據 |
| 醫學/生醫 | 臨床試驗 + 統計設計 |
| 社會科學 | 質性研究 + 文本分析 |

### 10.3 線上版本

- 錄製教學影片（每個 Session 30-45 min）
- 建立自學平台（Markdown + Video）
- 提供雲端 Demo 環境（Docker/Codespaces）
- 提供預配置 Obsidian Vault + research-workspace

---

## 十一、結論

### 關鍵發現

1. **完整工具生態系已建立**：24 Skills + 8 Agents + 5 Commands + 4 API 服務 + 12 外部工具，覆蓋論文全生命週期 90%
2. **真實案例驗證**：NILM+LLM 論文從概念到 SETA 投稿，AI 參與度 65-70%
3. **現有簡報基礎良好**：27 頁簡報升級為 55 頁，覆蓋完整流程
4. **課程定位精準**：L1D2 + L2D1 適合研究生初中階，有明確的技能進階路徑
5. **多 AI 協作模式**：Claude×ChatGPT×Gemini 平行審查，提升品質保證覆蓋率

### 建議行動

| 優先級 | 行動 | 預估工時 |
|--------|------|---------|
| P0 | 升級簡報（新增 32 頁 + 更新 10 頁） | 24h |
| P0 | 準備 API 驗證腳本 + Obsidian Vault | 8h |
| P0 | 準備實作教材（含 API curl + Obsidian 筆記卡模板） | 8h |
| P1 | 錄製 Demo 影片（含平行審查、離線備用） | 10h |
| P1 | 打包 research-workspace.zip | 4h |
| P2 | 範例研究主題準備 | 4h |
| P2 | 測試環境確認（含 ChatGPT/Gemini 帳號） | 4h |
| P3 | 進階課程規劃 | 8h |

**總投入：66 小時準備 → 2 天課程 → 可重複使用**
