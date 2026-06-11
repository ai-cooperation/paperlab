# Grill Record — 正念介入對成人焦慮的改善效果 (intervention meta-analysis)

> 來源:chat.ai PaperLab,2026-06-11 18:01。用戶:alan.chen75 (VIP)。
> 用途:**capability-alignment 修復後的第一個乾淨案例**(對照 burnout 過度承諾案)。
> job: proj_2026-06-11_17d79335｜synthesis.type=intervention｜level=phd/vip｜輸出英文。

## 一句話起點
「我想研究:正念介入對成人焦慮的改善效果」

## 5 步 grill 決策
| 步 | 選擇 | 系統引導重點 |
|---|---|---|
| 0 | 開新題 | 主動比對舊穿戴題(結構類似),問接續還是開新 |
| 1 | C 領域模糊 | 主動講明「成效題=meta-analysis,不需自有資料」 |
| 2 | B 應用延伸 | — |
| 3 | **D + intervention** | **主動列出引擎能力邊界(能做/不能做清單)** + probe 確認 OpenAlex 107,568 筆 |
| 4 | B 穩健 Q2-Q3 | 誠實提醒正念焦慮 meta 已做很多,純合併難上 Q1 |
| 5 | A 完整論文 | — |

## 收斂題目(系統產出,已對齊能力邊界)
「正念介入對成人焦慮的改善效果:傳遞形式作為調節變項的系統性回顧與統合分析」

三條主張(全部對齊引擎做得到的方法):
1. MBI 整體對成人焦慮有顯著小至中效果(SMD 合併)
2. 效果隨傳遞形式不同而有差異(**subgroup-by-delivery-mode**)
3. 異質性部分可由形式/劑量/對照組類型解釋

## ✅ capability-alignment 生效的鐵證(對照 burnout 案)
- grill **主動列出**引擎能力邊界(DL/Egger/LOO/subgroup vs not_supported 清單)
- gap 切角是「傳遞形式調節」——天然想用 **meta-regression**,但 grill **主動把它框成 subgroup**:
  「傳遞形式比較會以 subgroup 分組呈現,**不是 meta-regression**...題目與主張我已照這個邊界框好,**不會讓 a 端被迫改寫**」
- 標題機械檢查:**CLEAN**(無 Bayesian/network/meta-regression/latent-class)
- 對照 burnout 案(承諾 Bayesian LCA → 會被 a backstop 改寫):這次 grill 自己就守住了邊界,backstop 不必啟動

## b→a 交接驗證(contract.json)
```
data_source.type: meta-analysis  ✓
synthesis.type: intervention     ✓
synthesis.picos: exclude[pediatric,children,adolescent] require[randomized,controlled trial]  ✓
title over-promise: CLEAN        ✓
verified_refs: 6 | contract v2, no warnings
```

## 行銷亮點
- 一句口語 → 對齊引擎能力的可執行 intervention meta-analysis,**零過度承諾**
- 系統誠實:主動講「正念焦慮已做很多、純合併難上 Q1、需明確切角」——不灌迷湯
- gap 切角(傳遞形式調節)有真實研究價值,且框在引擎能力內

## meta(對系統的意義)
這是「前端引導 + 後端校正」雙層 capability-alignment 上線後第一個案例,證明**前端引導層自己就能把題目框在引擎能力內**,後端 backstop 是第二道網。從 burnout(承諾超標)到 mindfulness(自守邊界)= 修復前後對照。
