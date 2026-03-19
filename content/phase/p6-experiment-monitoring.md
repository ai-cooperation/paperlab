---
title: "程式跑了 12 小時，醒來發現第 2 小時就 crash 了"
description: "三層監控機制 + Telegram Bot 即時通知，讓長時間實驗不再白等"
date: 2026-03-19
tags: ["Phase 6", "實驗執行", "遠端監控", "Google Colab"]
keywords: ["實驗監控", "Google Colab 斷線", "Telegram Bot 通知", "OOM crash", "GPU 監控"]
summary: "睡前按下 Run，隔天發現 OOM crash，10 小時白等。用三層監控機制，讓你即時知道實驗狀態。"
weight: 6
faq:
  - q: "Google Colab 一直斷線怎麼辦？"
    a: "三個策略：(1) 用 Colab Pro 延長 session 時限；(2) 每 30 分鐘自動存 checkpoint 到 Google Drive；(3) 如果實驗超過 4 小時，認真考慮改用實驗室伺服器或 Kaggle Notebook（免費 GPU 時間較長）。"
  - q: "我不會寫 Telegram Bot 怎麼辦？"
    a: "最簡單的版本只需要 3 行 Python：用 requests 庫呼叫 Telegram Bot API 的 sendMessage 端點。建立 Bot 只需要跟 BotFather 說話 5 分鐘。完整的教學在論文方法學的工具包中提供。"
  - q: "wandb 免費版夠用嗎？"
    a: "學術用途完全夠用。免費版支援無限個人專案、100GB 儲存。唯一限制是團隊協作功能需要付費，但個人研究不需要。"
---

## 你是不是也遇到這個問題？

晚上 11 點，你按下 Run，程式開始訓練模型。預估要跑 12 小時，你安心去睡了。

早上起來一看 — 程式在第 2 小時就因為 Out of Memory（OOM）crash 了。10 個小時白等，什麼結果都沒有。更慘的是用 Google Colab 的人，session 在半夜斷線了，不但程式中斷，連中間結果都沒存到。

> 「Colab 跑到一半斷線，checkpoint 也沒存到，三天的訓練全部重來」
> — 學員反饋

> 「程式跑了一整晚，早上看 log 才發現第一個 epoch 就有 NaN，後面全是垃圾」
> — 學員反饋

長時間實驗就像無人值守的工廠 — 如果沒有監控系統，出了問題你要到第二天才知道。

## 為什麼會這樣？

長時間實驗面臨三大風險：

1. **資源耗盡**：GPU 記憶體不足（OOM）、磁碟空間滿了、CPU 記憶體洩漏
2. **連線中斷**：Google Colab session 過期、SSH 斷線、網路波動
3. **靜默失敗**：程式沒有 crash 但結果是錯的（NaN、loss 不下降、指標異常）

前兩種會讓你的程式直接停掉，第三種更危險 — 程式「看起來」在跑，但產出的結果毫無意義，你卻要到最後才發現。

這些問題的共同根源是：**你按了 Run 之後就失去了對實驗的可見性。** 沒有即時回饋機制，所有問題都要事後發現。

## 怎麼解決？

### 步驟 1：Colab 通知 — 最低成本的基礎監控

如果你用 Google Colab，加上幾行程式碼就能在實驗完成或失敗時收到通知：

在訓練程式的最後加上 Email 通知，或用 Google Apps Script 串接 LINE Notify / Telegram Bot。當 Colab cell 執行完畢或拋出例外時，自動發送通知。

同時，養成在每個 epoch 結束時存 checkpoint 的習慣。即使 session 斷線，至少不用從頭來過。

### 步驟 2：Telegram Bot 即時監控

對於跑在實驗室伺服器上的長時間實驗，用 Telegram Bot 做即時監控：

- **訓練進度通知**：每個 epoch 結束時發送 loss 和指標
- **異常警報**：loss 出現 NaN、指標突然下降、GPU 溫度過高時立即通知
- **完成通知**：訓練結束時發送最終結果摘要

收到異常通知後，你可以遠端登入處理，不需要等到隔天才發現問題。一個簡單的 Python 函數就能做到：用 Telegram Bot API 的 `sendMessage` 方法，在關鍵時間點發送狀態訊息。

### 步驟 3：三層監控機制

根據實驗的重要程度，選擇對應的監控層級：

**第一層 — 被動日誌（適合短實驗）**：
- 把所有 print 輸出導到 log 檔案
- 用 `tee` 同時輸出到螢幕和檔案
- 事後檢查 log 即可

**第二層 — 主動通知（適合過夜實驗）**：
- Telegram Bot 在關鍵節點推播
- 每個 epoch 報告一次進度
- 異常時立即警報

**第三層 — 全面儀表板（適合多實驗並行）**：
- Weights & Biases (wandb) 或 TensorBoard 即時視覺化
- GPU 使用率、記憶體、溫度持續追蹤
- 多個實驗在同一介面比較

大部分研究生用第二層就夠了。第三層適合同時跑 5 個以上實驗、需要即時比較的場景。

<div class="tip-box">

**核心原則：** 按下 Run 不是結束，是開始。長時間實驗必須有監控，讓問題即時被發現而不是事後才知道。

</div>

## 常見問題

**Q：Google Colab 一直斷線怎麼辦？**

三個策略：(1) 用 Colab Pro 延長 session 時限；(2) 每 30 分鐘自動存 checkpoint 到 Google Drive；(3) 如果實驗超過 4 小時，認真考慮改用實驗室伺服器或 Kaggle Notebook（免費 GPU 時間較長）。

**Q：我不會寫 Telegram Bot 怎麼辦？**

最簡單的版本只需要 3 行 Python：用 `requests` 庫呼叫 Telegram Bot API 的 `sendMessage` 端點。建立 Bot 只需要跟 BotFather 說話 5 分鐘。完整的教學在 論文方法學的工具包中提供。

**Q：wandb 免費版夠用嗎？**

學術用途完全夠用。免費版支援無限個人專案、100GB 儲存。唯一限制是團隊協作功能需要付費，但個人研究不需要。

---

*這是 [論文方法學 12 Phase](/phases/) 的 Phase 6：實驗執行。*
