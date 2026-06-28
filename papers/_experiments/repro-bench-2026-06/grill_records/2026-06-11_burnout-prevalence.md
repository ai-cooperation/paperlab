# Grill Record — 護理人員 burnout 盛行率 (prevalence meta-analysis)

> 來源:chat.ai PaperLab connector,2026-06-11 15:44。用戶:alan.chen75。
> 用途:b 段 grill 流程分析 + 行銷素材 + 引擎能力對齊案例。

## 一句話起點
「我想研究:護理人員 burnout 的盛行率有多高」

## 5 步 grill 決策(用戶實選)
| 步 | 維度 | 選擇 | 系統引導重點 |
|---|---|---|---|
| 1 | 研究起點 | C 領域興趣 | 主動指出盛行率題多半無自有資料,推 C 合理 |
| 2 | 創新策略 | A 方法創新 | 主動點出盛行率題的衝突點=各研究數字落差大(30-70%) |
| 3 | 資料來源 | **D 統合分析** | 正確判定「盛行率有多高」→ meta-analysis,且**自動指定 synthesis 子類型=prevalence** |
| 4 | 期刊層級 | B 穩健 Q2-Q3 | — |
| 5 | 產出範圍 | A 完整論文 | — |

## 收斂題目(系統產出)
「護理人員 burnout 盛行率的測量整合:以 Bayesian Latent Class Meta-Analysis 校正 cutoff 異質性」

## Gap 論述(系統自己挖的,非用戶給)
- 既有 meta-analysis 數字散到無法用(umbrella review 落差極大)
- 根因 = burnout 量測 cutoff 無共識,所有既有 meta 用 naive pooling 把測量誤差當真實差異
- **方法移植(method import)**:精神科已用 Bayesian latent class 在無金標準下估盛行率 → 移植到 burnout

## 6 篇種子文獻(全 search_literature 找到、記錄)
Getie 2025 umbrella / Gómez-Urquiza 2017 急診護理 / Leiter-Maslach 2017 量測挑戰 /
Laliberté 2015 精神科 Bayesian LCA(方法源)/ Chen 2005 無金標準 Bayesian 診斷 meta(方法源)/ Kong 2023 護生 meta

## 行銷亮點(這次 grill 真正強的地方)
- 從**一句口語**收斂出**博士級方法移植**研究框架(不是又一個 naive pooled 數字)
- 系統**主動挖 gap**(cutoff 異質性是根因)、**主動找跨領域方法源**(精神科 LCA),不是被動等用戶給
- 全程引導式、每步給推薦+理由,且**誠實警告**自動跑風險(model identifiability)

## ⚠️ 引擎能力對齊缺陷(這次暴露的關鍵問題)
- **grill 承諾了引擎做不到的方法**:題目定為 Bayesian latent class MA(需 R/Stan、無金標準建模);
  引擎實作的是 **DerSimonian-Laird 頻率學派 pooling**(正則抽取 + logit 合併)。
- 後果:submit 後引擎只會跑標準 prevalence pooling,與論文承諾的 Bayesian LCA 不符 → reviewer P0 promise-mismatch(r6 同型缺陷)。
- 根因:grill 沒有對齊 a 的 `/capabilities` 廣告的分析能力清單,chat 自由發揮把題目推出能力邊界。
- 修法(天花板待辦):capability negotiation 延伸到分析方法——a 廣告 meta lane 支援的合併方法(DL random-effects / 4 synthesis types / Egger / LOO / subgroup),grill 只能在清單內承諾;要 Bayesian LCA 就標「超出自動引擎能力,需人工」。
