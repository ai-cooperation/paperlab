/**
 * AI Paper Workshop — Day 2 FULL: AI 研究進階（詳細版）
 * ~85 slides with teaching-level content depth
 * Matches AI100 course design: concept → step → example → exercise → output
 *
 * Run: NODE_PATH=$(npm root -g) node gen_day2_full.js
 */
const pptxgen = require("pptxgenjs");
const {
  C, shadow, coverSlide, sectionDivider, contentSlide,
  conceptSlide, stepSlide, exampleSlide, exerciseSlide,
  compareSlide, cardsSlide, keyPointsSlide,
  quoteSlide, transitionSlide, outputSlide,
  beforeAfterSlide, tocSlide, moduleSection,
  infoCard, codeBox, tipBox, warnBox, processSteps, tableSlide,
  closingSlide,
} = require("./slide_lib");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "AI Paper Workshop - Day 2 Full";
pres.author = "Alan Chen";

// ═══════════════════════════════════════════════════════════
// OPENING (Slides 1-8)
// ═══════════════════════════════════════════════════════════

// S1: Cover
coverSlide(pres, {
  tag: "AI Paper Workshop 2026",
  title: "Day 2\nAI 研究進階",
  subtitle: "從論文架構到投稿策略的完整 AI 寫作系統",
  badges: [
    { text: "L2D1 中階", color: C.teal },
    { text: "24 Skills", color: C.goldDark },
    { text: "8 Agents", color: C.tealDark },
  ],
  footerLeft: "Smart Manufacturing Research Application",
  footerRight: "cooperation.tw",
});

// S2: TOC
tocSlide(pres, "Day 2 課程安排", [
  { num: "R", title: "Day 1 回顧 + 概念升級", time: "09:00-09:20（20 min）", desc: "從 AI 助教升級到 AI 研究團隊" },
  { num: "S3", title: "Session 3：論文架構設計與實驗規劃", time: "09:20-12:00（145 min）", desc: "IMRaD + QMD/YAML + GPU + TG Bot + 統計" },
  { num: "S4", title: "Session 4：QMD + BibTeX 論文撰寫系統", time: "13:00-14:45（105 min）", desc: "各章節寫作策略 + SVG + Claude Code 深度" },
  { num: "S5", title: "Session 5：多維度分析 & 品質保證", time: "15:00-16:30（90 min）", desc: "七維度審查 + 平行審查 + 投稿策略" },
  { num: "C", title: "總結與下一步", time: "16:30-17:30（60 min）", desc: "系統部署 + 學習路徑 + Q&A" },
]);

// S3: Day 1 回顧
(() => {
  const s = contentSlide(pres, "Day 1 回顧：已掌握的核心技能");
  const skills = [
    { icon: "C", title: "CARE 框架", desc: "Context-Ask-Refine-Extract\n結構化 Prompt 設計" },
    { icon: "S", title: "種子 DOI 搜索", desc: "CrossRef / Semantic Scholar\nOpenAlex API 驗證" },
    { icon: "Z", title: "Zotero + Obsidian", desc: "文獻管理 + 知識圖譜\n筆記卡雙向連結" },
    { icon: "G", title: "Gap 分析", desc: "三層 Research Gap\n創新性定位策略" },
  ];
  skills.forEach((sk, i) => {
    const x = 0.3 + i * 2.4;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.0, w: 2.2, h: 3.8, fill: { color: C.greenBg }, rectRadius: 0.08 });
    s.addShape(pres.shapes.OVAL, { x: x + 0.75, y: 1.2, w: 0.7, h: 0.7, fill: { color: C.teal } });
    s.addText(sk.icon, { x: x + 0.75, y: 1.2, w: 0.7, h: 0.7, fontSize: 22, bold: true, color: C.white, align: "center", valign: "middle" });
    s.addText(sk.title, { x: x + 0.1, y: 2.1, w: 2.0, h: 0.4, fontSize: 13, bold: true, color: C.navy, align: "center" });
    s.addText(sk.desc, { x: x + 0.1, y: 2.55, w: 2.0, h: 2.0, fontSize: 10, color: C.darkText, align: "center", lineSpacingMultiple: 1.3 });
  });
})();

// S4: 概念升級
conceptSlide(pres,
  "概念升級：從 AI 助教 → AI 研究團隊",
  "Day 1 = 一對一助教    Day 2 = 八位專家組成的研究團隊",
  "每位 Agent 各司其職：文獻、寫作、審查、統計、投稿...",
  [
    "literature-researcher → 文獻搜索與 Gap 識別",
    "paper-writer → 論文撰寫與潤稿",
    "citation-checker → 引用驗證（唯讀，安全不改檔）",
    "paper-reviewer → 七維度論文審查",
    "data-validator → 數據品質 + 過擬合檢測",
    "stats-validator → Bootstrap + 效果量 + 統計功效",
    "submission-helper → Cover Letter + 投稿準備",
    "research-orchestrator → 工作流程協調中樞",
  ]
);

// S5: 今日路線圖
(() => {
  const s = contentSlide(pres, "今日路線圖：論文產出完整流程");
  processSteps(s, pres, [
    { n: "1", title: "論文架構", desc: "IMRaD 設計\nQMD/YAML\n圖表規劃", color: C.navy },
    { n: "2", title: "實驗規劃", desc: "GPU 環境\nTG 監控\n統計驗證", color: C.teal },
    { n: "3", title: "論文撰寫", desc: "各章策略\nSVG 圖表\nBibTeX", color: C.goldDark },
    { n: "4", title: "品質審查", desc: "七維度評分\n平行審查\n引用驗證", color: C.tealDark },
    { n: "5", title: "投稿策略", desc: "期刊匹配\nCover Letter\n投稿打包", color: C.navy },
  ]);
  tipBox(s, 0.3, 4.2, 9.4, "目標：走完 Phase 4-12，掌握從架構設計到投稿送出的完整 AI 輔助流程");
})();

// ═══════════════════════════════════════════════════════════
// SESSION 3: 論文架構設計與實驗規劃 (Slides 9-35)
// ═══════════════════════════════════════════════════════════

sectionDivider(pres, {
  dayLabel: "Session 3",
  title: "論文架構設計\n與實驗規劃",
  subtitle: "09:20-12:00 | IMRaD + QMD + GPU + 統計驗證",
});

// --- 3.1 IMRaD (25 min) ---

conceptSlide(pres,
  "3.1 IMRaD 標準論文架構（25 min）",
  "Introduction → Methods → Results → and Discussion",
  "90% 以上 SCI/SCIE 期刊採用的標準架構",
  [
    "I (Introduction)：背景 → 問題 → 目的 → 貢獻聲明（漏斗式寫法）",
    "M (Methods)：問題定義 → 系統架構 → 演算法 → 物理約束",
    "R (Results)：實驗設置 → 主結果 → Ablation → 統計驗證 → 錯誤分析",
    "aD (Discussion)：意義分析 → 邊界條件 → 限制坦承 → 未來展望",
    "三個「必寫」附件：Abstract + Keywords + Highlights",
  ]
);

// IMRaD detail: Introduction 漏斗式
(() => {
  const s = contentSlide(pres, "Introduction：漏斗式寫法四步驟");
  const layers = [
    { title: "Layer 1：大背景", desc: "全球/產業趨勢\n「能源效率已成為...」", w: 8.5, color: C.lightBlue, accent: C.teal },
    { title: "Layer 2：具體問題", desc: "現有方法的不足\n「然而，傳統 NILM...」", w: 6.8, color: "E8EDF4", accent: C.navy },
    { title: "Layer 3：本研究方法", desc: "你的解決方案\n「本研究提出 HTF-CNN...」", w: 5.0, color: C.greenBg, accent: C.green },
    { title: "Layer 4：貢獻聲明", desc: "2-3 點具體貢獻\n(1) 首次將... (2) 提出...", w: 4.0, color: C.goldLight, accent: C.goldDark },
  ];
  layers.forEach((l, i) => {
    const x = (9.4 - l.w) / 2 + 0.3;
    const y = 0.95 + i * 1.0;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: l.w, h: 0.9, fill: { color: l.color }, rectRadius: 0.06 });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.06, h: 0.9, fill: { color: l.accent } });
    const titleW = Math.min(2.0, l.w * 0.4);
    s.addText(l.title, { x: x + 0.15, y, w: titleW, h: 0.9, fontSize: 11, bold: true, color: l.accent, valign: "middle" });
    s.addText(l.desc, { x: x + titleW + 0.2, y, w: l.w - titleW - 0.4, h: 0.9, fontSize: 10, color: C.darkText, valign: "middle", lineSpacingMultiple: 1.2, fit: "shrink" });
  });
})();

// Methods & Results tips
cardsSlide(pres, "Methods + Results 撰寫策略", [
  { icon: "M", title: "Methods", desc: [
    "問題定義（數學形式化）",
    "系統架構（必配圖）",
    "演算法流程（偽代碼）",
    "物理約束 & 假設",
    "可重現細節：",
    "  - 超參數表格",
    "  - 硬體配置",
    "  - 訓練/測試比例",
  ].join("\n") },
  { icon: "R", title: "Results", desc: [
    "實驗設置（數據集描述）",
    "主結果表格（vs Baseline）",
    "Ablation Study（驗證必要性）",
    "統計顯著性（p-value）",
    "錯誤案例分析（提高可信度）",
    "計算成本比較（可選）",
  ].join("\n") },
  { icon: "D", title: "Discussion", desc: [
    "結果意義分析",
    "為什麼你的方法有效？",
    "邊界條件在哪裡？",
    "限制性坦承（加分項）",
    "未來工作（具體 2-3 點）",
    "與現有方法的本質區別",
  ].join("\n") },
]);

// 圖表規劃
(() => {
  const s = contentSlide(pres, "論文圖表配置策略：Claim → Evidence 追溯");
  tableSlide(s, ["圖/表編號", "類型", "對應 Claim", "數據來源"],
    [
      ["Fig. 1", "系統架構圖", "研究方法的整體設計", "手繪/SVG"],
      ["Fig. 2", "數據預處理流程", "時頻轉換方法", "code/preprocess.py"],
      ["Table 1", "數據集統計", "實驗規模與代表性", "data/*.csv"],
      ["Table 2", "主結果比較", "優於 Baseline 的證據", "results/*.json"],
      ["Fig. 3", "混淆矩陣", "分類效能的細節", "results/*.json"],
      ["Table 3", "Ablation Study", "各組件貢獻的證據", "ablation/*.json"],
      ["Fig. 4", "錯誤案例分析", "模型限制的誠實揭示", "error_analysis/"],
    ],
    { y: 0.85, colW: [1.4, 1.8, 3.0, 3.2] }
  );
  tipBox(s, 0.3, 4.7, 9.4, "evidence-indexer skill：自動追溯 Claim → Table/Figure → Result File");
})();

// --- 3.2 QMD + YAML (30 min) ---

transitionSlide(pres, "Phase 5", "MD → QMD\nYAML 檔頭設定");

conceptSlide(pres,
  "3.2 從 Markdown 到 QMD（30 min）",
  "Markdown + YAML 檔頭 = Quarto 論文 → PDF + TeX + DOCX",
  "寫作門檻最低的學術排版方案：一份源碼，多種輸出",
  [
    "Step 1：用熟悉的 Markdown 寫內容（語法零學習成本）",
    "Step 2：加上 YAML 檔頭 → 定義期刊格式、作者、引用",
    "Step 3：quarto render → 自動生成 PDF / TeX / DOCX",
    "支援數學公式（LaTeX 語法）、交叉引用、BibTeX 引用",
    "4 大期刊格式一鍵切換：Elsevier / IEEE / Springer / MDPI",
  ]
);

// YAML 檔頭範例
(() => {
  const s = contentSlide(pres, "YAML 檔頭完整範例（Elsevier/SETA 配置）");
  codeBox(s, pres, 0.3, 0.85, 5.2, 4.3, "paper.qmd — YAML 檔頭",
    `---
title: "Hybrid Time-Frequency CNN..."
author:
  - name: Chung-Kuang Chen
    affiliations:
      - name: NTUST
        department: GIMT
abstract: |
  This study proposes...
bibliography: references.bib
csl: elsevier-vancouver-author-date.csl
format:
  elsevier-pdf:
    keep-tex: true
    journal:
      name: SETA
      cite-style: authoryear
    classoption: [preprint, review, 12pt]
---`);
  infoCard(s, pres, 5.7, 0.85, 4.0, 2.0, "關鍵欄位說明",
    "bibliography → 引用檔案路徑\ncsl → 引用格式樣式\nformat → 輸出格式\nkeep-tex → 保留 .tex 源碼\nclassoption → 期刊排版選項", C.teal);
  infoCard(s, pres, 5.7, 3.05, 4.0, 2.1, "支援的期刊格式",
    "Elsevier → elsevier-pdf (authoryear)\nIEEE → ieee-pdf (journal)\nSpringer → springer-pdf\nMDPI → mdpi-pdf\n5 秒切換：改 format + csl 即可", C.navy);
})();

// 期刊格式對照表
(() => {
  const s = contentSlide(pres, "四大期刊格式一鍵切換");
  tableSlide(s, ["期刊體系", "format 值", "classoption", "csl 檔案", "特色"],
    [
      ["Elsevier", "elsevier-pdf", "authoryear, preprint", "elsevier-vancouver", "最多 SCI 期刊"],
      ["IEEE", "ieee-pdf", "journal", "ieee.csl", "工程領域首選"],
      ["Springer", "springer-pdf", "(預設)", "springer-basic", "Nature 系列"],
      ["MDPI", "mdpi-pdf", "(預設)", "mdpi.csl", "OA 期刊首選"],
    ],
    { y: 0.85, colW: [1.5, 1.8, 2.0, 2.3, 1.8] }
  );
  codeBox(s, pres, 0.3, 3.3, 9.4, 1.65, "一行指令渲染",
    `# PDF（同時產生 .tex）        # Word（給合作者修改）
quarto render paper.qmd       quarto render paper.qmd --to docx

# 保留 .tex（直接上傳 Overleaf）
quarto render paper.qmd --keep-tex`);
})();

// --- 3.3 實驗設計 + GPU (30 min) ---

transitionSlide(pres, "Phase 5", "實驗設計 + IDE 工作流\n+ 遠端 GPU");

// 實驗設計六要素
keyPointsSlide(pres, "實驗設計六要素 + Skill 支援", [
  { heading: "1. 基線選擇 (Baseline)", desc: "baseline-min-set skill：根據貢獻類型推薦最小基線集" },
  { heading: "2. 消融實驗 (Ablation)", desc: "ablation-min-proof skill：設計最小消融方案證明組件必要性" },
  { heading: "3. 數據分割 (Split)", desc: "split-leakage-audit skill：檢測時間/實體洩漏風險" },
  { heading: "4. 統計驗證 (Statistics)", desc: "statistical-validation skill：Bootstrap + 效果量 + P0-P2 分級" },
  { heading: "5. 可重現性 (Reproducibility)", desc: "seed=42 + YAML 配置 + NumpyEncoder + metric-audit" },
  { heading: "6. 計算預算 (Compute)", desc: "GPU 使用率 > 60% 驗證 + TG Bot 三層監控" },
]);

// IDE 工作流
cardsSlide(pres, "IDE 工作流：VS Code 四大 Extension", [
  { icon: "Py", title: "Python Extension", desc: [
    "IntelliSense 智能補全",
    "Jupyter Notebook 整合",
    "Debug 斷點除錯",
    "虛擬環境切換",
  ].join("\n") },
  { icon: "Q", title: "Quarto Extension", desc: [
    "即時預覽論文 PDF",
    "YAML 語法提示",
    "Markdown 學術語法",
    "交叉引用跳轉",
  ].join("\n") },
  { icon: "SSH", title: "Remote-SSH", desc: [
    "連接遠端 GPU 伺服器",
    "本地 VS Code 操作",
    "檔案同步 + Terminal",
    "無縫切換本地/遠端",
  ].join("\n") },
  { icon: "CC", title: "Claude Code CLI", desc: [
    "終端機 AI 研究助手",
    "24 Skills 自動載入",
    "程式碼生成 + 除錯",
    "論文撰寫 + 審查",
  ].join("\n") },
]);

// 三層執行環境
(() => {
  const s = contentSlide(pres, "三層 GPU 執行環境");
  tableSlide(s, ["環境", "GPU", "用途", "費用", "適合場景"],
    [
      ["本地 MacBook", "無/MPS", "開發 + 調試", "免費", "程式碼撰寫、小數據測試"],
      ["Google Colab", "T4 / A100", "原型驗證", "免費~$10/月", "快速實驗、教學展示"],
      ["遠端 3090", "RTX 3090 24GB", "完整實驗", "電費", "正式訓練、大規模實驗"],
    ],
    { y: 0.85, colW: [1.5, 1.5, 1.5, 1.5, 3.4] }
  );
  codeBox(s, pres, 0.3, 3.3, 4.5, 2.0, "Colab 快速設定",
    `from google.colab import drive
drive.mount('/content/drive')

!pip install torch torchvision
!python train.py --epochs 100`);
  codeBox(s, pres, 5.0, 3.3, 4.7, 2.0, "遠端 3090 標準流程",
    `ssh ac-3090
conda activate gpu
PYTHONUNBUFFERED=1 \\
  nohup python -u train.py \\
  > exp.log 2>&1 &
nvidia-smi  # 1min 內檢查 GPU>60%`);
})();

// 遠端執行注意事項
stepSlide(pres, "遠端 GPU 實驗：必要步驟", 1, "環境初始化 + 啟動驗證", [
  "明確初始化 Conda：source ~/miniconda3/etc/profile.d/conda.sh",
  "啟用正確環境：conda activate gpu（不要用 base）",
  "無緩衝輸出：PYTHONUNBUFFERED=1 python -u（即時看日誌）",
  "持久化執行：nohup ... & 或 tmux（SSH 斷線不中斷）",
  "1 分鐘內驗證：nvidia-smi 確認 GPU 使用率 > 60%",
  "若 GPU < 30% → 立即停止，檢查 model.to(device)",
]);

// --- 3.4 TG Bot (20 min) ---

transitionSlide(pres, "Phase 6", "TG Bot 實驗監控\n手機掌控 GPU 狀態");

conceptSlide(pres,
  "3.4 Telegram Bot 三層實驗監控（20 min）",
  "實驗投入 GPU → 手機即時掌控 → 異常自動通知",
  "讓你安心離開電腦，實驗狀態盡在掌握",
  [
    "Level 1（即時）：啟動 1 分鐘檢查 GPU、5 分鐘檢查日誌輸出",
    "Level 2（定期）：每 15 分鐘確認進程存在 + GPU + 日誌更新時間",
    "Level 3（異常通知）：進程消失 / 日誌 10 分鐘未更新 / OOM 錯誤",
    "TG Bot 指令：/check（GPU）、/all（完整報告）、/log（日誌）",
    "自動通知範例：OOM → 手機收到通知 + 建議減少 batch_size",
  ]
);

// TG Bot 實際案例
exampleSlide(pres, "TG Bot 異常通知實例",
  "RTX 3090 上訓練 HTF-CNN 模型，batch_size=256，第 47 epoch 觸發 OOM",
  [
    "[TG Bot 自動通知]",
    "!! GPU 異常警報 !!",
    "主機: ac-3090 | GPU: RTX 3090",
    "狀態: CUDA Out of Memory",
    "時間: 2026-03-06 14:23:07",
    "詳情: RuntimeError: CUDA OOM at epoch 47",
    "  已用顯存: 23.8GB / 24GB",
    "",
    "建議處理方式:",
    "1. 減少 batch_size (256 -> 128)",
    "2. 啟用 gradient checkpointing",
    "3. 使用 mixed precision (fp16)",
  ]
);

// --- 3.5 統計驗證 (25 min) ---

transitionSlide(pres, "Phase 7", "Skill 驅動的\n自動化統計驗證");

// 自動化統計流程
(() => {
  const s = contentSlide(pres, "3.5 自動化統計驗證流程（25 min）");
  processSteps(s, pres, [
    { n: "1", title: "指令觸發", desc: "/analyze-experiment\nresults.json", color: C.navy },
    { n: "2", title: "數據驗證", desc: "data-validator\n品質 + 過擬合", color: C.teal },
    { n: "3", title: "統計分析", desc: "stats-validator\nBootstrap + 效果量", color: C.goldDark },
    { n: "4", title: "分級報告", desc: "P0-P3 分級\n論文用文本", color: C.tealDark },
  ]);
  tipBox(s, 0.3, 4.2, 9.4, "一條指令完成：數據品質 → 統計驗證 → P0-P3 分級 → 可直接貼入論文的文字");
})();

// 數據一致性三角驗證
conceptSlide(pres,
  "數據一致性三角驗證：Text ↔ Table ↔ Figure",
  "論文中的每個數字必須三方一致，不一致 = P0 致命問題",
  "figure-table-checker + evidence-indexer 自動掃描",
  [
    "Text：「本方法 F1 達到 0.848...」",
    "Table 2：F1 = 0.8488（保留四位小數）",
    "Figure 3：混淆矩陣計算得 F1 = 0.848",
    "不一致案例：F1=0.820（文中）vs 0.8488（表中）→ P0 問題！",
    "Claim → Evidence 追溯鏈：evidence-indexer skill 自動建立",
    "修正流程：results/*.json → EXPERIMENT_RESULTS.md → paper.qmd",
  ]
);

// 統計方法選擇指南
(() => {
  const s = contentSlide(pres, "統計方法選擇指南");
  tableSlide(s, ["場景", "推薦方法", "何時使用", "P 級別"],
    [
      ["兩組比較 (正態)", "配對 t-test", "樣本 > 30、常態分佈", "P1（未做則缺失）"],
      ["兩組比較 (非正態)", "Mann-Whitney U", "小樣本、非常態", "P1"],
      ["多組比較", "Friedman + Nemenyi", "多模型排名比較", "P1"],
      ["信賴區間", "Bootstrap (10K)", "任何分佈皆可", "P0（強烈建議）"],
      ["效果量", "Cohen's d", "量化差異實際大小", "P2"],
      ["統計功效", "Power Analysis", "樣本量是否足夠", "P2"],
    ],
    { y: 0.85, colW: [2.0, 2.0, 3.0, 2.4] }
  );
  warnBox(s, 0.3, 4.6, 9.4, "常見陷阱：只報 p < 0.05 不報效果量 → 審稿人質疑「統計顯著但實際差異微小」");
})();

// --- 3.6 可重現性 (15 min) ---

keyPointsSlide(pres, "3.6 可重現性設計五原則", [
  { heading: "固定隨機種子", desc: "seed=42 + torch.manual_seed + np.random.seed + cudnn.deterministic" },
  { heading: "參數配置文件化", desc: "YAML/JSON 儲存所有超參數，不在程式碼中寫死（magic number）" },
  { heading: "結果 JSON 可序列化", desc: "使用 NumpyEncoder 處理 numpy/tensor 類型，確保可存取可重讀" },
  { heading: "指標定義一致性", desc: "metric-audit skill：確認 macro/micro/weighted F1 定義統一" },
  { heading: "數字流管道", desc: "results/*.json → EXPERIMENT_RESULTS.md → paper.qmd（唯一真相來源）" },
]);

// 實作練習 1
exerciseSlide(pres, "思考練習 1：論文架構設計", [
  "為你的研究畫出 IMRaD 各章節大綱（標題 + 2-3 句摘要）",
  "列出預計的圖表清單（編號 + 類型 + 對應 Claim）",
  "建立 QMD 檔案，填入 YAML 檔頭（選擇你的目標期刊格式）",
  "定義實驗設計六要素：Baseline / Ablation / Split / 統計方法",
  "（進階）設定 quarto render 並產出第一份 PDF",
], "15 min");

// ═══════════════════════════════════════════════════════════
// SESSION 4: QMD + BibTeX 論文撰寫系統 (Slides 36-58)
// ═══════════════════════════════════════════════════════════

sectionDivider(pres, {
  dayLabel: "Session 4",
  title: "QMD + BibTeX\n論文撰寫系統",
  subtitle: "13:00-14:45 | 寫作策略 + SVG + Claude Code 深度",
});

// --- 4.1 論文撰寫策略 (30 min) ---

conceptSlide(pres,
  "4.1 各章節撰寫策略（30 min）",
  "IMRaD 對應撰寫順序：Methods → Results → Introduction → Discussion → Abstract",
  "不要從 Introduction 開始寫！先寫你最確定的部分",
  [
    "Methods：最先寫 — 你最了解自己做了什麼",
    "Results：第二寫 — 用數據說話",
    "Introduction：第三寫 — 知道結果後才能精準定位",
    "Discussion：第四寫 — 回應 Introduction 的問題",
    "Abstract：最後寫 — 濃縮全文精華",
  ]
);

// 各章節 AI 寫作策略
cardsSlide(pres, "各章節 AI 輔助策略", [
  { icon: "I", title: "Introduction", desc: [
    "倒金字塔 + 貢獻聲明",
    "AI 協助：",
    "- 產業趨勢數據收集",
    "- Research Gap 論述",
    "- 貢獻聲明精煉",
    "Skill: innovation-positioning",
  ].join("\n") },
  { icon: "M", title: "Methods", desc: [
    "圖表先行、AI 生文字",
    "AI 協助：",
    "- 流程圖描述文字",
    "- 演算法偽代碼",
    "- 數學公式排版",
    "Skill: academic-writing",
  ].join("\n") },
  { icon: "R", title: "Results+Disc.", desc: [
    "數據表 → AI 統計分析",
    "AI 協助：",
    "- 統計結果解讀",
    "- 圖表描述文字",
    "- 限制性坦承措辭",
    "Skill: statistical-validation",
  ].join("\n") },
]);

// 轉投策略
stepSlide(pres, "轉投期刊策略：5 步快速調整", 1, "分析目標期刊熱點",
  [
    "抓取目標期刊近 100 篇標題 → AI topic clustering → 識別當前熱點",
    "分析主編偏好：Google Scholar profile + 最近 Editorial 內容",
    "調整 Title：對齊期刊熱門關鍵詞（避免太窄或太廣）",
    "調整 Abstract + Intro 第一段：引用該期刊近期文章（表示你了解它）",
    "修改 YAML format + CSL → quarto render → 新格式 PDF（5 秒完成）",
    "journal-fit skill：自動評估你的論文與目標期刊的適配度",
  ]
);

// 轉投 Before/After
beforeAfterSlide(pres, "轉投案例：Energy & Buildings → SETA",
  [
    "Title: CNN-based NILM for Industrial...",
    "Format: Elsevier (Energy & Buildings)",
    "Abstract: 強調 building energy...",
    "Keywords: building, energy efficiency",
    "引用: EB 相關文獻為主",
    "CSL: elsevier-with-titles.csl",
    "",
    "Scope 不完全匹配 → 可能 Desk Reject",
  ],
  [
    "Title: Hybrid Time-Frequency CNN for",
    "    Industrial NILM with LLM-enhanced...",
    "Format: Elsevier (SETA)",
    "Abstract: 強調 sustainable energy...",
    "Keywords: sustainable, technology",
    "引用: 加入 SETA 近期文章",
    "CSL: elsevier-vancouver.csl",
    "5 秒切換 → quarto render → 新 PDF",
  ]
);

// --- 4.2 SVG + QMD→TeX (20 min) ---

transitionSlide(pres, "Phase 9", "圖表呈現\nSVG 向量圖 + 出版級規範");

// SVG 為什麼重要
compareSlide(pres, "為什麼需要 SVG 向量圖？",
  "PNG/JPG 點陣圖", [
    "放大後模糊（像素化）",
    "300 DPI 以上檔案很大",
    "無法後續編輯",
    "螢幕截圖品質不穩定",
    "某些期刊直接退回",
  ],
  "SVG/PDF 向量圖", [
    "無限放大不失真",
    "檔案小、品質高",
    "可用 Inkscape 後編輯",
    "期刊要求 300+ DPI 自動滿足",
    "專業學術出版標準",
  ]
);

// Python 圖表輸出
(() => {
  const s = contentSlide(pres, "Python 三格式圖表輸出 + QMD 引用");
  codeBox(s, pres, 0.3, 0.85, 4.8, 2.2, "Python 儲存三格式",
    `import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(x, y)
ax.set_xlabel('Epoch')
ax.set_ylabel('F1 Score')
# 三格式輸出
fig.savefig('fig.svg', format='svg')
fig.savefig('fig.pdf', format='pdf')
fig.savefig('fig.png', dpi=300)`);
  codeBox(s, pres, 5.3, 0.85, 4.4, 1.05, "QMD 引用圖片",
    `![F1 趨勢](fig.pdf){#fig-f1 width="100%"}
如 @fig-f1 所示，F1 在 epoch 50 後趨穩。`);
  infoCard(s, pres, 5.3, 2.1, 4.4, 0.95, "Inkscape 後處理",
    "SVG → PDF/EPS（某些期刊要求）\ninkscape fig.svg --export-pdf=fig.pdf", C.tealDark);
  codeBox(s, pres, 0.3, 3.25, 9.4, 1.7, "QMD → TeX + PDF 一行完成",
    `# 同時得到 PDF + TeX
quarto render paper.qmd             # → paper.pdf
quarto render paper.qmd --keep-tex  # → paper.pdf + paper.tex
# .tex 可直接上傳 Overleaf 或期刊系統`);
})();

// --- 4.3 BibTeX 進階 (10 min) ---

conceptSlide(pres,
  "4.3 BibTeX 進階管理（10 min）",
  "引用格式 + CSL 切換 + 雙重防呆 = 零引用錯誤",
  "黃金規則：絕不添加 references.bib 中不存在的引用",
  [
    "基本語法：@citekey（如 @Chen2024）或 [@a; @b]（多引用）",
    "CSL 樣式一鍵切換：APA / IEEE / Elsevier / Springer",
    "bib-manager skill：檢測重複 key、缺失欄位、格式錯誤",
    "citation-checker agent：逐筆驗證 DOI 有效性 + 作者正確性",
    "雙重防呆：AI 絕不自行添加引用 + 發現問題只指出不修正",
  ]
);

// 實作練習 2
exerciseSlide(pres, "實作練習 2：QMD 論文撰寫", [
  "建立 QMD 論文骨架（含完整 YAML 檔頭 + 目標期刊格式）",
  "設定 bibliography: references.bib + csl 樣式檔",
  "撰寫 Abstract 初稿（200 字以內，結構：背景-方法-結果-結論）",
  "加入 3 個引用（@citekey 格式），quarto render 驗證格式",
  "（進階）用 Python 產出一張 SVG 圖並嵌入 QMD",
  "（進階）嘗試切換期刊格式，觀察 PDF 差異",
], "15 min");

// ═══════════════════════════════════════════════════════════
// Phase 9: 圖表呈現 — 出版級學術圖表規範 (NEW MODULE, 25 min)
// ═══════════════════════════════════════════════════════════

transitionSlide(pres, "Phase 9", "圖表呈現\n出版級學術圖表規範");

// 簡報圖 vs 學術圖
compareSlide(pres, "簡報圖表 vs 學術圖表 — 完全不同的世界",
  "簡報圖表", [
    "PNG / JPG 點陣圖",
    "72-150 DPI，放大模糊",
    "配色好看就好",
    "字體大小隨意",
    "標注可省略",
    "Excel 截圖常見",
  ],
  "學術圖表（期刊要求）", [
    "SVG / EPS / PDF 向量格式",
    "300-600 DPI 出版級解析度",
    "色彩語義一致（同變項同色）",
    "最小 8pt，軸標籤清晰可讀",
    "軸標籤、單位、誤差線、顯著性標記",
    "Reviewer 看圖就知道你的水準",
  ]
);

// 頂級期刊圖表解析 — Nature Medicine 案例（含實際圖片）
(() => {
  // Overview slide
  const s0 = contentSlide(pres, "頂級期刊圖表解析：Nature Medicine (2026)");
  s0.addText("Antibiotic use and gut microbiome composition\nlinks from individual-level prescription data of 14,979 individuals", {
    x: 0.3, y: 0.85, w: 9.4, h: 0.8, fontSize: 14, color: C.grayText, lineSpacingMultiple: 1.4,
  });
  s0.addText("這篇論文的圖表是頂級期刊的標準範例：", {
    x: 0.3, y: 1.75, w: 9.4, h: 0.4, fontSize: 13, bold: true, color: C.navy,
  });
  const figTypes = [
    "Fig 1 — 多面板折線圖 + 熱力圖 + Forest Plot（三種圖組合）",
    "Fig 2 — 函數回歸 + 信賴帶（時序趨勢 6×3 多面板）",
    "Fig 3 — 大型熱力圖（1,340 species × 11 抗生素）",
    "Fig 4 — 複合熱力圖（抗生素 + 代謝標記雙色系）",
    "Table 1-2 — 標準三線表（人口統計 + 抗生素用量）",
  ];
  figTypes.forEach((t, i) => {
    s0.addText("\u2022 " + t, {
      x: 0.5, y: 2.25 + i * 0.45, w: 9.0, h: 0.4, fontSize: 12.5, color: C.darkText,
    });
  });

  // Fig 1: Diversity — 左圖右標注
  const s1 = contentSlide(pres, "Fig 1：多面板圖表組合（折線 + 熱力 + Forest）");
  s1.addImage({ path: "assets/nature_medicine/fig1_cropped.png", x: 0.2, y: 0.8, w: 5.5, h: 4.2 });
  const fig1Notes = [
    "a: 折線圖 — 三種 diversity metric",
    "   色彩區分時間段，誤差棒清晰",
    "b: 熱力圖 — 星號標注顯著性",
    "   FDR < 5% 才標，避免過度宣稱",
    "c: Forest Plot — 迴歸係數 + 95% CI",
    "   填充 = 顯著，空心 = 不顯著",
    "",
    "設計要點：",
    "• 色彩語義一致（全圖同色系）",
    "• 子圖用 a, b, c 粗體小寫標記",
    "• 圖說獨立，不看正文也能理解",
  ];
  fig1Notes.forEach((n, i) => {
    s1.addText(n, { x: 5.9, y: 0.85 + i * 0.38, w: 3.9, h: 0.35, fontSize: 10.5, color: n.startsWith("設計") ? C.navy : C.darkText, bold: n.startsWith("設計"), lineSpacingMultiple: 1.1 });
  });

  // Fig 2: Recovery — 左圖右標注
  const s2 = contentSlide(pres, "Fig 2：函數回歸 + 信賴帶（時序多面板）");
  s2.addImage({ path: "assets/nature_medicine/fig2_cropped.png", x: 0.2, y: 0.8, w: 5.5, h: 3.8 });
  const fig2Notes = [
    "6 種抗生素 × 3 種 diversity",
    "= 18 面板，統一軸範圍",
    "",
    "設計要點：",
    "• 信賴帶（shaded area）= 95% CI",
    "• 實線 = 回歸係數，色彩區分藥物",
    "• X 軸統一（1-8 年），方便比較",
    "• 每列同一個 metric",
    "• 每欄同一個藥物",
  ];
  fig2Notes.forEach((n, i) => {
    s2.addText(n, { x: 5.9, y: 0.85 + i * 0.42, w: 3.9, h: 0.38, fontSize: 10.5, color: n.startsWith("設計") ? C.navy : C.darkText, bold: n.startsWith("設計"), lineSpacingMultiple: 1.1 });
  });

  // Fig 3: Large heatmap
  const s3 = contentSlide(pres, "Fig 3：大型熱力圖（1,340 species）");
  s3.addImage({ path: "assets/nature_medicine/fig3_cropped.png", x: 0.2, y: 0.8, w: 5.5, h: 4.0 });
  const fig3Notes = [
    "1,340 個物種 × 11 種抗生素",
    "× 3 個時間段 = 超大規模",
    "",
    "設計要點：",
    "• 藍色 = 負相關，紅色 = 正相關",
    "• 只顯示顯著（FDR < 5%）",
    "• Y 軸按 Phylum 分群排列",
    "• 底部附比例尺和圖例",
    "• 用量長條圖附在下方",
  ];
  fig3Notes.forEach((n, i) => {
    s3.addText(n, { x: 5.9, y: 0.85 + i * 0.42, w: 3.9, h: 0.38, fontSize: 10.5, color: n.startsWith("設計") ? C.navy : C.darkText, bold: n.startsWith("設計"), lineSpacingMultiple: 1.1 });
  });

  // Fig 4: Combined heatmap
  const s4 = contentSlide(pres, "Fig 4：複合熱力圖（抗生素 × 代謝標記）");
  s4.addImage({ path: "assets/nature_medicine/fig4_cropped.png", x: 0.2, y: 0.8, w: 5.5, h: 4.2 });
  const fig4Notes = [
    "101 species × 3 抗生素 + 代謝標記",
    "",
    "設計要點：",
    "• 雙色系：抗生素用 teal/pink",
    "  代謝標記用 purple/pink",
    "• 階層聚類排列物種",
    "• 星號分級（* FDR<5%, ** FDR<1%）",
    "• 整合多資料源在同一張圖",
    "• 這種圖讓 reviewer 印象深刻",
  ];
  fig4Notes.forEach((n, i) => {
    s4.addText(n, { x: 5.9, y: 0.85 + i * 0.42, w: 3.9, h: 0.38, fontSize: 10.5, color: n.startsWith("設計") ? C.navy : C.darkText, bold: n.startsWith("設計"), lineSpacingMultiple: 1.1 });
  });

  // Table example
  const s5 = contentSlide(pres, "Table 1：標準三線表（學術表格規範）");
  s5.addImage({ path: "assets/nature_medicine/table1_cropped.png", x: 0.2, y: 0.8, w: 5.5, h: 3.5 });
  const tblNotes = [
    "學術三線表規範：",
    "• 只有三條橫線（頂/表頭下/底）",
    "• 無縱線、無網格",
    "• 數值對齊（小數點/百分比）",
    "• 連續變項：median [IQR]",
    "• 類別變項：n (%)",
    "• 表注用上標字母標記",
    "• 縮寫在表注統一解釋",
  ];
  tblNotes.forEach((n, i) => {
    s5.addText(n, { x: 5.9, y: 0.85 + i * 0.42, w: 3.9, h: 0.38, fontSize: 10.5, color: n.startsWith("學術") ? C.navy : C.darkText, bold: n.startsWith("學術"), lineSpacingMultiple: 1.1 });
  });
})();

// 學術圖表的 6 大規範
keyPointsSlide(pres, "學術圖表 6 大規範", [
  { heading: "1. 向量格式", desc: "SVG 原始 → PDF/EPS 投稿。PNG 只用於預覽，絕不投稿" },
  { heading: "2. 色彩語義一致", desc: "同一個變項在所有圖中用同一種顏色，建立「色彩字典」" },
  { heading: "3. 軸標籤完整", desc: "X/Y 軸名稱 + 單位 + 刻度。缺一項 reviewer 就會質疑" },
  { heading: "4. 誤差表示", desc: "Error bar（SD/SE/95%CI）+ 信賴帶。沒有誤差 = 不可信" },
  { heading: "5. 顯著性標注", desc: "星號（* p<0.05, ** p<0.01）或直接標 p 值。位置對齊比較組" },
  { heading: "6. 多面板編排", desc: "a, b, c 子圖標記 + 統一尺寸 + 共享圖例。Nature 標準是粗體小寫" },
]);

// 常見圖表類型 × 使用場景
(() => {
  const s = contentSlide(pres, "常見學術圖表類型 × 適用場景");
  tableSlide(s, ["圖表類型", "適用場景", "範例"],
    [
      ["折線圖 (Line)", "時序趨勢、訓練曲線", "Loss/Accuracy vs Epoch"],
      ["長條圖 (Bar)", "類別比較、消融實驗", "Baseline vs Proposed"],
      ["Forest Plot", "迴歸係數 + CI", "多變項效果量比較"],
      ["熱力圖 (Heatmap)", "相關性、大規模比較", "Species × Antibiotic 關聯"],
      ["箱型圖 (Box)", "分布比較", "各組的分數分布"],
      ["散點圖 (Scatter)", "兩變項關係", "預測值 vs 實際值"],
      ["架構圖 (Diagram)", "方法論流程", "研究架構 / 模型結構"],
    ],
    { y: 0.85, colW: [2.2, 3.3, 4.0] }
  );
})();

// SVG 圖表產出流程
stepSlide(pres, "圖表產出三步驟", 1, "Python 產出三格式", [
  "savefig(svg) 原始向量圖，可編輯",
  "savefig(pdf) 投稿用，嵌入字體",
  "savefig(png, dpi=300) 預覽用",
  "三格式同時輸出，一次滿足所有需求",
]);

stepSlide(pres, "圖表產出三步驟", 2, "Inkscape 後處理", [
  "SVG 轉 PDF/EPS（某些期刊要求特定格式）",
  "微調標籤位置和字體大小",
  "合併多面板圖（a, b, c 子圖）",
]);

stepSlide(pres, "圖表產出三步驟", 3, "QMD 嵌入 + 交叉引用", [
  "嵌入圖片並設定 figure ID",
  "文中用交叉引用，自動編號",
  "quarto render 一鍵產出 PDF",
  "切換期刊格式時圖表位置自動調整",
]);

// 圖表自我檢查清單
conceptSlide(pres,
  "投稿前圖表自我檢查清單",
  "Reviewer 看圖的前 10 秒就決定你的論文水準",
  "每張圖都要過這 8 項檢查",
  [
    "□ 格式正確？（SVG/PDF/EPS，不是 PNG 截圖）",
    "□ 解析度足夠？（300 DPI 以上，放大不模糊）",
    "□ 軸標籤完整？（名稱 + 單位 + 合理刻度範圍）",
    "□ 色彩一致？（同變項同色，跨圖不變）",
    "□ 有誤差表示？（Error bar 或 CI band）",
    "□ 顯著性標注？（* / ** / *** 或 p 值）",
    "□ 子圖標記？（a, b, c 粗體小寫，左上角）",
    "□ 圖說完整？（看圖說就能理解，不需讀正文）",
  ]
);

// --- 4.4 Claude Code 深度 (30 min) ---

transitionSlide(pres, "Deep Dive", "Claude Code 深度體驗\n+ Skill 自動化 Demo");

sectionDivider(pres, {
  dayLabel: "14:15-14:45",
  title: "Claude Code\n自動化工作流",
  subtitle: "CLAUDE.md + 24 Skills + 8 Agents + 5 Commands",
});

// CLAUDE.md 詳解
conceptSlide(pres,
  "CLAUDE.md：AI 的工作手冊",
  "一份 Markdown 檔案，定義 AI 在你專案中的所有行為規範",
  "放在專案根目錄，Claude Code 啟動時自動讀取",
  [
    "引用處理原則：只使用 references.bib 中的引用，絕不推測",
    "檔案操作原則：不刪除原始數據、不覆蓋既有檔案",
    "驗證原則：寫入後必須驗證、宣稱前先確認",
    "目錄結構定義：01_literature / 02_research / 03_manuscripts ...",
    "實驗執行規範：seed=42 / GPU 驗證 / 三層監控",
    "相當於團隊的「工作守則」— AI 也需要 SOP",
  ]
);

// Skills 系統架構
(() => {
  const s = contentSlide(pres, "Skills 系統：24 個專業知識庫");
  // 基礎 Skills
  infoCard(s, pres, 0.3, 0.85, 4.5, 2.15, "基礎 Skills（14 個）",
    "paper-review-skill → 七維度評分\nbib-manager → BibTeX 管理\nliterature-synthesis → 文獻綜述\njournal-submission → 投稿流程\nfigure-table-checker → 圖表一致性\ninnovation-positioning → 創新定位\nacademic-writing → 學術寫作\nstatistical-validation → 統計驗證", C.teal);
  // 進階 Skills
  infoCard(s, pres, 5.0, 0.85, 4.7, 2.15, "進階 Research Agent Skills（10 個）",
    "mvp-gatekeeper → MVP 門檻\njournal-fit → 期刊適配\nsplit-leakage-audit → 數據洩漏\nevidence-indexer → 證據追溯\nresearch-contract → 研究契約\nablation-min-proof → 消融證明\nmetric-audit → 指標審計\nbaseline-min-set → 基線最小集\nsubmission-bundle → 投稿打包\nrebuttal-matrix → 回覆矩陣", C.navy);
  // 觸發機制
  tipBox(s, 0.3, 3.2, 9.4, "觸發機制：用戶輸入 → 語義匹配 → 自動載入對應 Skill → 應用專業知識指導 AI 回覆");
  // Agents
  infoCard(s, pres, 0.3, 3.8, 9.4, 1.35, "8 個 AI 專家 Agent",
    "唯讀（安全）: citation-checker, paper-reviewer | 讀寫: paper-writer, submission-helper | 執行: data-validator, stats-validator | 協調: research-orchestrator, literature-researcher", C.goldDark);
})();

// 5 Commands
(() => {
  const s = contentSlide(pres, "5 個一鍵工作流 Commands");
  tableSlide(s, ["Command", "功能", "觸發的 Agents", "產出"],
    [
      ["/review-paper", "論文全面審查", "citation-checker → data-validator → paper-reviewer", "七維度評分 + P0-P3 清單"],
      ["/analyze-experiment", "實驗分析", "data-validator → stats-validator", "統計分析報告"],
      ["/prepare-submission", "投稿準備", "paper-reviewer → submission-helper", "Cover Letter + 檢查清單"],
      ["/analyze-literature", "文獻分析", "literature-researcher", "Gap 分析 + 綜述大綱"],
      ["/respond-reviewers", "審稿回覆", "rebuttal-matrix → paper-writer", "回覆信草稿"],
    ],
    { y: 0.85, colW: [2.0, 1.5, 3.5, 2.4] }
  );
  tipBox(s, 0.3, 4.6, 9.4, "每個 Command = 多個 Agent 串接執行 → 一條指令完成原本需要數小時的工作");
})();

// Demo 1
exampleSlide(pres, "Demo 1: /review-paper 論文審查",
  "對 SETA 論文執行完整七維度審查，自動串接 3 個 Agent",
  [
    "$ /review-paper paper.qmd \"SETA\"",
    "",
    "[citation-checker] 掃描 47 筆引用...",
    "  2 筆 DOI 無效、1 筆作者名不匹配",
    "[data-validator] 檢查數據一致性...",
    "  Table 2 F1=0.848 vs 文中 F1=0.82 → P0",
    "[paper-reviewer] 七維度評分:",
    "  結構 8/10 | 方法 7/10 | 實驗 6/10",
    "  數據 5/10 | 寫作 8/10 | 引用 7/10 | 創新 7/10",
    "",
    "P0 問題: 2 個 | P1: 3 個 | P2: 5 個",
  ]
);

// Demo 2
exampleSlide(pres, "Demo 2: /prepare-submission 投稿準備",
  "一鍵生成 Cover Letter + 投稿檢查清單",
  [
    "$ /prepare-submission \"SETA\"",
    "",
    "[paper-reviewer] 最終審查通過（0 個 P0）",
    "[submission-helper] 生成 Cover Letter:",
    "",
    "Dear Editor,",
    "  We submit our manuscript entitled \"Hybrid",
    "  Time-Frequency CNN...\" for consideration in",
    "  Sustainable Energy Technologies and Assessments.",
    "",
    "  投稿檢查: 10/10 項完成",
    "  包含: PDF + TeX + Cover Letter + SVG figures",
    "  + Highlights + Author Statement + Data Avail.",
  ]
);

// ═══════════════════════════════════════════════════════════
// SESSION 5: 多維度分析 & 品質保證 (Slides 59-80)
// ═══════════════════════════════════════════════════════════

sectionDivider(pres, {
  dayLabel: "Session 5",
  title: "多維度分析\n& 品質保證",
  subtitle: "15:00-16:30 | 審查 + 平行 AI + 引用驗證 + 投稿",
});

// --- 5.1 七維度審查 (20 min) ---

conceptSlide(pres,
  "5.1 七維度論文分析系統（20 min）",
  "結構 | 方法 | 實驗 | 數據 | 寫作 | 引用 | 創新",
  "每個維度 1-10 分，搭配 P0-P3 問題分級",
  [
    "結構完整性：IMRaD 完整？章節比例合理？邏輯連貫？",
    "方法論嚴謹性：數學嚴謹？物理約束？可重現？",
    "實驗設計：Baseline 足夠？Ablation 完整？統計有效？",
    "數據可信度：Text ↔ Table ↔ Figure 三方一致？",
    "寫作清晰度：學術語氣？段落邏輯？Grammar？",
    "引用完整性：DOI 有效？作者正確？覆蓋近 3 年？",
    "創新貢獻：超越應用？有方法論貢獻？定位精準？",
  ]
);

// P0-P3 分級
(() => {
  const s = contentSlide(pres, "P0-P3 問題分級系統");
  const levels = [
    { level: "P0 致命", desc: "必須修正，否則 Desk Reject", example: "數據不一致、引用造假、結論無支撐", color: C.red, bg: C.redBg },
    { level: "P1 嚴重", desc: "審稿人一定會指出，Major Revision", example: "缺少 Baseline 比較、統計不足", color: C.orange, bg: C.orangeBg },
    { level: "P2 重要", desc: "可能被要求修改，Minor Revision", example: "圖表品質不佳、寫作不夠清晰", color: C.goldDark, bg: "FFF7E6" },
    { level: "P3 次要", desc: "錦上添花，改了更好", example: "排版微調、用詞優化", color: C.teal, bg: C.lightBlue },
  ];
  levels.forEach((l, i) => {
    const y = 0.85 + i * 1.1;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.3, y, w: 9.4, h: 1.0, fill: { color: l.bg }, rectRadius: 0.06 });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y, w: 0.07, h: 1.0, fill: { color: l.color } });
    s.addText(l.level, { x: 0.5, y, w: 1.5, h: 1.0, fontSize: 14, bold: true, color: l.color, valign: "middle" });
    s.addText(l.desc, { x: 2.1, y, w: 3.0, h: 1.0, fontSize: 11, color: C.darkText, valign: "middle" });
    s.addText(l.example, { x: 5.2, y, w: 4.3, h: 1.0, fontSize: 10, color: C.grayText, valign: "middle" });
  });
})();

// MVP Gatekeeper
keyPointsSlide(pres, "MVP 門檻檢查：mvp-gatekeeper skill", [
  { heading: "Gate 1: 研究問題", desc: "明確定義？與現有文獻有區別？" },
  { heading: "Gate 2: 方法論", desc: "技術上可行？有理論支撐？" },
  { heading: "Gate 3: 實驗設計", desc: "Baseline 足夠？統計有效？" },
  { heading: "Gate 4: 數據支撐", desc: "所有 Claim 都有 Evidence？" },
  { heading: "Gate 5: 寫作完成度", desc: "所有章節完成？語言品質達標？" },
  { heading: "Gate 6: 投稿就緒", desc: "格式正確？附件齊全？Cover Letter？" },
]);

// --- 5.2 平行審查 (25 min) ---

transitionSlide(pres, "多 AI 協作", "Claude × ChatGPT × Gemini\n平行審查策略");

conceptSlide(pres,
  "5.2 為什麼需要多 AI 平行審查？（25 min）",
  "單一 AI 有盲點 → 多 AI 交叉檢查 → 覆蓋率最大化",
  "不同模型擅長不同面向 → 互補而非替代",
  [
    "Claude Code：系統化 Skill 生態系，七維度評分 + 引用驗證 + 數據一致性",
    "ChatGPT (GPT-4o)：結構/寫作流暢度，段落邏輯、Grammar、可讀性",
    "Gemini (2.5 Pro)：事實查核/長文檢索，引用事實核對、最新文獻覆蓋",
    "三者交叉：Claude 找數據問題 + ChatGPT 找寫作問題 + Gemini 找事實問題",
    "人工整合：三份報告合併 → 去重 → P0-P3 排序 → 修改優先級",
  ]
);

// 三 AI 分工表
(() => {
  const s = contentSlide(pres, "三 AI 分工策略表");
  tableSlide(s, ["AI 工具", "強項", "審查重點", "使用方式"],
    [
      ["Claude Code", "系統化 + Skill 生態系", "七維度評分 + P0-P3\n引用驗證 + 數據一致性", "/review-paper 自動化"],
      ["ChatGPT (GPT-4o)", "結構 + 寫作流暢度", "段落邏輯 + Grammar\n論述連貫性 + 可讀性", "Custom GPT / Prompt"],
      ["Gemini 2.5 Pro", "事實查核 + 長文檢索", "引用事實核對 + 數據聲明\n最新文獻覆蓋度", "NotebookLM / Deep Research"],
    ],
    { y: 0.85, colW: [1.8, 2.2, 2.8, 2.6] }
  );
  tipBox(s, 0.3, 3.5, 9.4, "建議順序：Claude（自動化最快）→ ChatGPT（寫作）→ Gemini（事實查核）→ 人工整合");
})();

// 平行審查流程 4 步
stepSlide(pres, "平行審查操作流程", 1, "Claude Code（自動化）",
  [
    "/review-paper paper.qmd \"SETA\"",
    "→ citation-checker → data-validator → paper-reviewer",
    "→ 輸出：七維度評分 + P0-P3 問題清單",
    "優勢：全自動、可重複、有 Skill 知識庫支撐",
    "耗時：約 3-5 分鐘",
  ]
);

stepSlide(pres, "平行審查操作流程", 2, "ChatGPT（寫作審查）",
  [
    "Prompt: \"Review this paper as a senior reviewer for [journal].\"",
    "\"Focus on: structure, argumentation flow, writing clarity,\"",
    "\"and paragraph-level logic. List issues by severity.\"",
    "→ 輸出：寫作/邏輯問題清單",
    "優勢：自然語言流暢度判斷最強",
    "耗時：約 5-10 分鐘（含 Prompt 調整）",
  ]
);

stepSlide(pres, "平行審查操作流程", 3, "Gemini Deep Research（事實查核）",
  [
    "Prompt: \"Fact-check all claims and citations in this paper.\"",
    "\"Verify: (1) cited papers exist (2) claims match source\"",
    "\"(3) any missing recent key references (2023-2026).\"",
    "→ 輸出：事實核查報告 + 遺漏文獻清單",
    "優勢：Deep Research 可深入交叉比對原始文獻",
    "耗時：約 10-15 分鐘（Deep Research 模式）",
  ]
);

stepSlide(pres, "平行審查操作流程", 4, "人工整合",
  [
    "三份報告合併 → 去重（同一問題不同描述）",
    "按 P0-P3 統一分級 → 建立修改優先級",
    "P0 第一時間修正 → P1 本週內修正 → P2/P3 投稿前修正",
    "修正後再跑一輪 Claude 驗證 → 確認 P0 = 0",
    "整合模板：parallel-review-template.md",
  ]
);

// 平行審查案例
exampleSlide(pres, "案例：SETA 論文平行審查發現",
  "同一篇 NILM 論文，三個 AI 分別找到不同問題",
  [
    "Claude Code 發現：",
    "  P0: Table 2 F1=0.848 vs 文中 F1=0.82（數據不一致）",
    "  P1: 2 筆引用 DOI 無效",
    "",
    "ChatGPT 發現：",
    "  P1: Discussion 段 2→3 邏輯跳躍（缺銜接句）",
    "  P2: 全文 passive voice 比例 > 70%（可讀性差）",
    "",
    "Gemini 發現：",
    "  P1: @Lee2023 年份應為 2024（新版已更新）",
    "  P2: 缺少 2025 兩篇重要 survey（競爭力不足）",
  ]
);

// --- 5.3 引用驗證 (15 min) ---

keyPointsSlide(pres, "5.3 三層引用驗證（15 min）", [
  { heading: "Layer 1：存在性驗證", desc: "DOI 是否有效？作者名是否正確？年份是否匹配？→ citation-checker" },
  { heading: "Layer 2：準確性驗證", desc: "你的引用主張是否與原文一致？有無斷章取義？→ 人工 + Gemini" },
  { heading: "Layer 3：完整性驗證", desc: "references.bib 中所有條目都有被引用嗎？有無孤立引用？→ bib-manager" },
  { heading: "圖表交叉引用", desc: "所有 @fig-x 和 @tbl-x 都有對應物件？編號是否連續？→ figure-table-checker" },
]);

// --- 5.4 Reviewer 預測 (15 min) ---

transitionSlide(pres, "投稿前最後一關", "Reviewer 預測與應對");

conceptSlide(pres,
  "5.4 AI 模擬審稿人提問（15 min）",
  "投稿前讓 AI 扮演嚴格審稿人，預測最可能的質疑",
  "提前準備回答 → 直接強化論文 or 備好 Rebuttal 素材",
  [
    "Prompt：\"Act as a critical Reviewer 2 for [journal]...\"",
    "常見問題 1：「你的方法與 [existing method] 的本質區別？」",
    "常見問題 2：「只在一個數據集上驗證，泛化性如何保證？」",
    "常見問題 3：「缺少 computation cost 比較」",
    "常見問題 4：「統計顯著性不足，能否提供 confidence interval？」",
    "rebuttal-matrix skill：建立問題-回答對照表，追蹤修改進度",
  ]
);

// Reviewer 預測案例
exampleSlide(pres, "案例：4 個預測問題與回答策略",
  "AI 模擬 SETA 期刊審稿人，預測最可能的 4 個質疑",
  [
    "Q1: HTF-CNN vs 標準 CNN 的理論優勢？",
    "  → 強化 Methods 中的頻域特徵分析段落",
    "",
    "Q2: 只用工廠數據集，泛化性？",
    "  → 補充 IMDELD 數據集實驗（已有 97.55%）",
    "",
    "Q3: 實際部署的 inference 時間？",
    "  → 新增 Table：inference time comparison",
    "",
    "Q4: 1Hz 採樣的 Nyquist 限制影響？",
    "  → Discussion 中坦承限制 + 提出未來高頻方案",
  ]
);

// --- 5.5 投稿策略 (15 min) ---

transitionSlide(pres, "Phase 11+12", "投稿策略與流程");

// 期刊選擇
(() => {
  const s = contentSlide(pres, "5.5 期刊選擇方法論：加權評分表");
  tableSlide(s, ["維度", "權重", "SETA", "Energy & Buildings", "Applied Energy"],
    [
      ["Scope 匹配", "30%", "9/10", "7/10", "8/10"],
      ["Impact Factor", "20%", "7.2 (Good)", "7.1 (Good)", "11.2 (High)"],
      ["審稿速度", "15%", "3-4 個月", "4-6 個月", "6-8 個月"],
      ["錄取率", "15%", "~25%", "~20%", "~15%"],
      ["方法論偏好", "10%", "AI+可持續", "建築節能", "綜合能源"],
      ["近期趨勢", "10%", "NILM 相關文章多", "較少 NILM", "有 NILM 專題"],
    ],
    { y: 0.85, colW: [1.5, 1.0, 2.3, 2.3, 2.3] }
  );
  tipBox(s, 0.3, 4.6, 9.4, "journal-fit skill：自動分析目標期刊近 100 篇文章，評估你的論文適配度");
})();

// 投稿 10 項清單
keyPointsSlide(pres, "投稿素材 10 項清單", [
  { heading: "1. 論文 PDF", desc: "期刊格式 + 行號 + review 模式" },
  { heading: "2. 論文 .tex 源碼", desc: "quarto render --keep-tex 產出" },
  { heading: "3. Cover Letter", desc: "submission-helper agent 自動生成" },
  { heading: "4. 高解析度圖表", desc: "SVG/PDF/TIFF, 300+ DPI" },
  { heading: "5. Supplementary Material", desc: "補充實驗、詳細數據" },
  { heading: "6. Author Statement", desc: "CRediT 貢獻聲明" },
]);

// 投稿 10 項清單 (續)
keyPointsSlide(pres, "投稿素材 10 項清單（續）", [
  { heading: "7. Highlights", desc: "3-5 bullet points，每點 < 85 字元" },
  { heading: "8. Graphical Abstract", desc: "800×400px 視覺摘要" },
  { heading: "9. Suggested Reviewers", desc: "3-5 人 + 理由（避免利益衝突）" },
  { heading: "10. Data Availability", desc: "聲明數據可取得性 + 代碼倉庫" },
]);

// submission-bundle
(() => {
  const s = contentSlide(pres, "submission-bundle skill：自動打包驗證");
  processSteps(s, pres, [
    { n: "1", title: "格式檢查", desc: "YAML 欄位完整\n期刊格式正確", color: C.navy },
    { n: "2", title: "內容檢查", desc: "圖表編號連續\n引用完整", color: C.teal },
    { n: "3", title: "檔案清單", desc: "10 項素材\n逐一確認", color: C.goldDark },
    { n: "4", title: "最終打包", desc: "建立 ZIP\n附檢查報告", color: C.tealDark },
  ]);
  tipBox(s, 0.3, 4.2, 9.4, "/prepare-submission \"SETA\" → 自動執行以上 4 步 → 產出 submission-ready.zip");
})();

// ═══════════════════════════════════════════════════════════
// CLOSING (Slides 81-88)
// ═══════════════════════════════════════════════════════════

sectionDivider(pres, {
  dayLabel: "16:30-17:30",
  title: "總結與下一步",
  subtitle: "系統回顧 + 部署指南 + 學習路徑 + Q&A",
});

// 5.6 完整工作流回顧
(() => {
  const s = contentSlide(pres, "5.6 完整工作流回顧：12 Phase 全貌");
  const phases = [
    { n: "P1", label: "方向", color: C.navy },
    { n: "P2", label: "文獻", color: C.teal },
    { n: "P3", label: "Gap", color: C.goldDark },
    { n: "P4", label: "架構", color: C.navy },
    { n: "P5", label: "實驗", color: C.teal },
    { n: "P6", label: "監控", color: C.goldDark },
    { n: "P7", label: "統計", color: C.navy },
    { n: "P8", label: "撰寫", color: C.teal },
    { n: "P9", label: "圖表", color: C.goldDark },
    { n: "P10", label: "審查", color: C.navy },
    { n: "P11", label: "投稿", color: C.teal },
    { n: "P12", label: "回覆", color: C.goldDark },
  ];
  phases.forEach((p, i) => {
    const x = 0.3 + (i % 6) * 1.6;
    const y = i < 6 ? 1.0 : 3.0;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 1.4, h: 1.6, fill: { color: p.color }, rectRadius: 0.08 });
    s.addText(p.n, { x, y: y + 0.15, w: 1.4, h: 0.5, fontSize: 18, bold: true, color: C.gold, align: "center" });
    s.addText(p.label, { x, y: y + 0.7, w: 1.4, h: 0.5, fontSize: 13, bold: true, color: C.white, align: "center" });
    if (i < 5 || (i >= 6 && i < 11)) {
      s.addText("\u25B6", { x: x + 1.4, y: y + 0.5, w: 0.2, h: 0.5, fontSize: 10, color: C.grayText, align: "center", valign: "middle" });
    }
  });
  s.addText("\u25BC", { x: 9.5, y: 2.35, w: 0.5, h: 0.5, fontSize: 14, color: C.grayText, align: "center", valign: "middle" });
  tipBox(s, 0.3, 4.85, 9.4, "24 Skills + 8 Agents + 5 Commands — AI 參與度 65-70%，人類掌握核心決策");
})();

// 5.7 系統部署
keyPointsSlide(pres, "5.7 部署這套系統到你的研究", [
  { heading: "Step 1：安裝基礎工具", desc: "Claude Code CLI + Quarto + VS Code + Zotero + Obsidian" },
  { heading: "Step 2：解壓 research-workspace.zip", desc: "包含 24 Skills + 8 Agents + 5 Commands + 模板" },
  { heading: "Step 3：客製化 CLAUDE.md", desc: "修改研究主題、目標期刊、目錄結構、實驗規範" },
  { heading: "Step 4：建立 Obsidian Vault", desc: "匯入文獻筆記卡、建立雙向連結、啟用 Graph View" },
  { heading: "Step 5：設定 TG Bot（選修）", desc: "遠端 GPU 實驗監控 → 手機即時掌控" },
  { heading: "Step 6：開始第一篇論文", desc: "/analyze-literature → /review-paper → /prepare-submission" },
]);

// 5.8 學習路徑
cardsSlide(pres, "5.8 學習路徑規劃", [
  { icon: "W", title: "本週行動", desc: [
    "安裝所有工具",
    "建立 research-workspace",
    "整理 5 篇核心文獻",
    "建立 QMD 論文骨架",
    "用 CARE 框架探索方向",
  ].join("\n") },
  { icon: "M", title: "1 個月目標", desc: [
    "完成完整文獻調研",
    "確認 Research Gap",
    "完成 Methods 初稿",
    "設計實驗方案",
    "建立 references.bib",
  ].join("\n") },
  { icon: "Q", title: "3 個月目標", desc: [
    "完成實驗 + 統計驗證",
    "撰寫完整論文初稿",
    "通過七維度自我審查",
    "三 AI 平行審查修正",
    "投稿第一篇 SCI/SCIE",
  ].join("\n") },
]);

// Q&A
quoteSlide(pres,
  "AI 不會取代研究者\n但會用 AI 的研究者\n將取代不會的",
  "開始使用這套系統，讓 AI 成為你的研究加速器"
);

// 課程評估
(() => {
  const s = contentSlide(pres, "課程評估");
  tableSlide(s, ["評估項目", "佔比", "評估標準"],
    [
      ["D1 實作練習", "20%", "CARE Prompt + API 驗證 3 DOI + 3 篇 Obsidian 筆記卡 + 5 篇 BibTeX"],
      ["D2 實作練習", "20%", "QMD 骨架 + Abstract + 3 引用 + SVG 圖（進階）"],
      ["課堂參與", "20%", "提問、討論、分享"],
      ["研究方向報告", "15%", "明確研究問題 + Gap 分析 + 期刊匹配初評"],
      ["論文框架", "15%", "完整 QMD 骨架 + BibTeX + 所有引用經 API 驗證"],
      ["系統部署", "10%", "安裝 research-workspace + Obsidian Vault 建立"],
    ],
    { y: 0.85, colW: [2.0, 1.0, 6.4] }
  );
})();

// Closing slide
closingSlide(pres,
  "Thank You!",
  "開始你的 AI 輔助研究之旅",
  "research-workspace.zip | CLAUDE.md | 24 Skills"
);

// ═══════════════════════════════════════════════════════════
// SAVE
// ═══════════════════════════════════════════════════════════

const path = require("path");
const outFile = path.join(__dirname, "..", "dist", "Day2_Full_AI研究進階.pptx");
pres.writeFile({ fileName: outFile }).then(() => {
  console.log(`Done → ${outFile} (${pres.slides.length} slides)`);
}).catch(err => {
  console.error("Error:", err);
});
