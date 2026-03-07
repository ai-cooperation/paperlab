/**
 * AI Paper Workshop — Day 1 FULL: AI 研究基礎（詳細版）
 * ~85 slides with teaching-level content depth
 * Matches AI100 course design: concept → step → example → exercise → output
 *
 * Run: NODE_PATH=$(npm root -g) node gen_day1_full.js
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
pres.title = "AI Paper Workshop - Day 1 Full";
pres.author = "Alan Chen";

// ═══════════════════════════════════════════════════════════
// OPENING (Slides 1-10)
// ═══════════════════════════════════════════════════════════

// S1: Cover
coverSlide(pres, {
  tag: "AI Paper Workshop 2026",
  title: "Day 1\nAI 研究基礎",
  subtitle: "從概念探索到文獻調研的完整 AI 協作流程",
  badges: [
    { text: "L1D2 初階進階", color: C.teal },
    { text: "24 Slides/Skills", color: C.goldDark },
    { text: "5 APIs", color: C.tealDark },
  ],
  footerLeft: "Smart Manufacturing Research Application",
  footerRight: "cooperation.tw",
});

// S2: TOC
tocSlide(pres, "今日課程安排", [
  { num: "1", title: "開場：AI 正在重塑學術研究", time: "09:00-09:30（30 min）", desc: "完整工作流程總覽 + 真實案例" },
  { num: "S1", title: "Session 1：AI 概念探索與研究方向", time: "09:30-10:45（75 min）", desc: "CARE 框架 + 多輪對話 + 方向確認" },
  { num: "S2", title: "Session 2：AI 輔助文獻調研", time: "11:00-14:30（含午休）", desc: "種子DOI + API驗證 + Obsidian + BibTeX + Gap分析" },
  { num: "3", title: "自動化工具入門 + Claude Code", time: "14:45-16:00（75 min）", desc: "GAS 自動化 + Claude Code CLI 初體驗" },
  { num: "4", title: "實作練習 + Day 1 回顧", time: "16:00-17:00（60 min）", desc: "核心技能 checklist + 明日預告" },
]);

// S3: Key Points — 今天你會帶走這 5 樣東西
keyPointsSlide(pres, "今天你會帶走這 5 樣東西", [
  { heading: "研究方向文件", desc: "用 CARE 框架與 AI 對話確認的研究方向 + Gap 分析初稿" },
  { heading: "驗證過的文獻清單", desc: "至少 10 篇經 CrossRef API 驗證的正確引用" },
  { heading: "Obsidian 文獻知識庫", desc: "結構化筆記卡 + 雙向連結 + Graph View 知識圖譜" },
  { heading: "references.bib 引用檔", desc: "格式正確、經驗證的 BibTeX 引用檔案" },
  { heading: "Research Gap 分析", desc: "從文獻矩陣中識別的研究缺口 + 創新定位初稿" },
]);

// S4: Workflow Overview
(() => {
  const s = contentSlide(pres, "完整 AI 研究工作流程總覽（11 Phase）", C.navy);
  const phases = [
    { n: "P1", label: "概念\n探索", color: C.teal },
    { n: "P2", label: "文獻\n調研", color: C.teal },
    { n: "P3", label: "研究\n定位", color: C.teal },
    { n: "P4", label: "論文\n架構", color: C.navyLight },
    { n: "P5", label: "實驗\n設計", color: C.navyLight },
    { n: "P6", label: "實驗\n執行", color: C.navyLight },
    { n: "P7", label: "數據\n分析", color: C.navyLight },
    { n: "P8", label: "論文\n撰寫", color: C.navyLight },
    { n: "P9", label: "品質\n審查", color: C.navyLight },
    { n: "P10", label: "投稿\n準備", color: C.navyLight },
    { n: "P11", label: "審稿\n回覆", color: C.navyLight },
  ];
  const pw = 0.75, gap = 0.09, startX = 0.25;
  phases.forEach((p, i) => {
    const x = startX + i * (pw + gap);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.0, w: pw, h: 1.1, fill: { color: i < 3 ? C.teal : C.navyLight }, rectRadius: 0.06, shadow: shadow(0.1) });
    s.addText(p.n, { x, y: 1.02, w: pw, h: 0.3, fontSize: 10, bold: true, color: C.gold, align: "center" });
    s.addText(p.label, { x, y: 1.3, w: pw, h: 0.7, fontSize: 10, color: C.white, align: "center", valign: "middle" });
    if (i < phases.length - 1) s.addText("\u25B8", { x: x + pw, y: 1.35, w: gap, h: 0.4, fontSize: 9, color: C.grayText, align: "center" });
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.25, y: 2.3, w: 2.52, h: 0.3, fill: { color: C.teal, transparency: 20 } });
  s.addText("Day 1 範圍 (P1-P3)", { x: 0.25, y: 2.3, w: 2.52, h: 0.3, fontSize: 10, bold: true, color: C.teal, align: "center", valign: "middle" });
  s.addShape(pres.shapes.RECTANGLE, { x: 2.94, y: 2.3, w: 6.81, h: 0.3, fill: { color: C.navyLight, transparency: 20 } });
  s.addText("Day 2 範圍 (P4-P11)", { x: 2.94, y: 2.3, w: 6.81, h: 0.3, fontSize: 10, bold: true, color: C.navy, align: "center", valign: "middle" });
  tipBox(s, 0.25, 4.7, 9.5, "AI 參與度 70-75%  |  24 Skills + 8 Agents + 5 Commands + 5 APIs  |  真實案例：NILM+LLM 論文 (SETA)");
})();

// S5: Why AI Research — concept
conceptSlide(pres,
  "為什麼需要 AI 輔助學術研究？",
  "每年 300 萬篇新論文，人工篩選已不可能",
  "AI 不是取代研究者，而是成為你的「超級助教」— 處理重複性工作，讓你專注創意",
  [
    "文獻爆炸：2023 年全球發表 340 萬篇論文，年增 5%，人工無法全面追蹤",
    "寫作瓶頸：英文非母語的研究者，改稿平均需要 3-5 輪，每輪 2-3 天",
    "品質風險：30% 的投稿因引用錯誤、數據不一致被 desk reject",
    "AI 可以：30 秒評估一篇論文、自動驗證引用、多維度品質審查",
    "關鍵原則：AI 產出必須驗證 — 本課程的核心就是「信任但驗證」",
  ]
);

// S6: Pain vs Solution
(() => {
  const s = contentSlide(pres, "研究者的三大痛點 vs AI 解方");
  const pairs = [
    { pain: "文獻海量\n每年 300 萬篇新論文\n人工篩選耗時耗力", sol: "AI 文獻篩選\nAPI 驗證 + 語義比對\n30 秒評估一篇論文", pc: C.orange, sc: C.teal },
    { pain: "寫作瓶頸\n英文非母語\n學術風格難掌握", sol: "AI 寫作助手\n學術風格指導 + 潤稿\n結構化撰寫流程", pc: C.orange, sc: C.teal },
    { pain: "品質不一\n引用錯誤、數據不一致\n投稿被 desk reject", sol: "AI 品質審查\n七維度評分 + P0-P3 分級\n多 AI 平行審查", pc: C.orange, sc: C.teal },
  ];
  pairs.forEach((p, i) => {
    const y = 0.95 + i * 1.35;
    infoCard(s, pres, 0.3, y, 4.2, 1.15, `痛點 ${i + 1}`, p.pain, p.pc);
    s.addText("\u27A1", { x: 4.55, y: y + 0.3, w: 0.5, h: 0.4, fontSize: 18, color: C.teal, align: "center" });
    infoCard(s, pres, 5.1, y, 4.6, 1.15, `AI 解方 ${i + 1}`, p.sol, p.sc);
  });
})();

// S7: Before/After
beforeAfterSlide(pres, "傳統研究 vs AI 輔助研究",
  [
    "Google Scholar 手動搜尋",
    "逐篇閱讀 Abstract",
    "手動記錄到 Excel",
    "不確定引用是否正確",
    "手動排版 Word/LaTeX",
    "請同事幫忙審閱",
    "投稿被退 → 從頭再來",
    "",
    "耗時 6-12 個月",
  ],
  [
    "AI 產出種子 DOI 清單",
    "API 自動驗證 + 30 秒評估",
    "Obsidian 知識圖譜自動連結",
    "CrossRef API 100% 驗證引用",
    "QMD 一鍵轉 PDF/TeX",
    "Claude×ChatGPT×Gemini 平行審查",
    "投稿前七維度品質保證",
    "",
    "耗時 2-4 個月",
  ]
);

// S8: Real case intro
(() => {
  const s = contentSlide(pres, "真實案例：NILM+LLM 論文的 AI 協作歷程");
  infoCard(s, pres, 0.3, 0.9, 4.5, 2.0, "論文資訊", [
    "標題：Training-Free Industrial NILM via LLM",
    "期刊：SETA (Sustainable Energy Technologies",
    "        and Assessments)",
    "狀態：已投稿，Under Review",
    "AI 參與度：~70%",
  ].join("\n"), C.teal);
  infoCard(s, pres, 5.1, 0.9, 4.6, 2.0, "AI 使用統計", [
    "43 篇引用 → 全部經 CrossRef 驗證",
    "5 圖 11 表 → evidence-indexer 追溯",
    "3 個數據集 → 跨域驗證 F1=0.85",
    "七維度審查 → P0 問題歸零才投稿",
    "平行審查 → Claude + ChatGPT + Gemini",
  ].join("\n"), C.navy);
  infoCard(s, pres, 0.3, 3.1, 9.4, 1.2, "本課程的教學方法", [
    "不是教「工具怎麼用」，而是教「論文怎麼做」— 工具服務流程",
    "每個 Phase 都有真實案例對照 — 你看到的不是示範，是實戰經驗",
    "結業帶走 research-workspace.zip — 24 Skills + 8 Agents + 5 Commands 完整系統",
  ].join("\n"), C.goldDark);
})();

// S9: Quote
quoteSlide(pres,
  "AI 不會寫論文，\n但會用 AI 的研究者\n效率提升 3-5 倍",
  "本工作坊的目標：讓你成為「會用 AI 的研究者」"
);

// S10: Transition
transitionSlide(pres, "準備好了嗎？", "Session 1：AI 概念探索");

// ═══════════════════════════════════════════════════════════
// SESSION 1: AI 概念探索（Slides 11-30）
// ═══════════════════════════════════════════════════════════

// S11: Section Divider
sectionDivider(pres, {
  dayLabel: "Session 1",
  title: "AI 概念探索\n與研究方向確定",
  subtitle: "Phase 1 | 75 分鐘 | CARE 框架 + 多輪對話 + 方向確認",
});

// S12: Module cards
moduleSection(pres, "S1", "AI 概念探索與研究方向確定", "09:30-10:45（75 分鐘）", [
  { title: "研究 Prompt 工程", desc: "CARE 框架\n5 套研究專用模板\n結構化提問方法" },
  { title: "多輪對話策略", desc: "漸進式縮焦法\nExtended Thinking\n從寬到窄聚焦" },
  { title: "方向確認方法論", desc: "三角驗證法\nSMART 化研究問題\n創新性初步定位" },
  { title: "即時練習", desc: "選定研究主題\nCARE Prompt 撰寫\n與 AI 進行 3 輪對話" },
]);

// S13: Concept — What is Research Prompt Engineering
conceptSlide(pres,
  "什麼是「研究 Prompt 工程」？",
  "好的 Prompt = 好的研究問題 = 好的 AI 回答",
  "研究 Prompt 不同於一般聊天 — 需要結構化、可驗證、逐步深入",
  [
    "一般 Prompt：「幫我找 NILM 的論文」→ AI 給你一堆可能錯誤的清單",
    "研究 Prompt：提供背景 + 指定角色 + 明確任務 + 要求格式 → 高品質可驗證的回答",
    "關鍵差異：研究 Prompt 要求 AI 的回答必須「可驗證」（DOI、數據、來源）",
    "目標：不是讓 AI 給你答案，而是讓 AI 幫你「問對問題」",
  ]
);

// S14: CARE Framework
(() => {
  const s = contentSlide(pres, "研究 Prompt 工程：CARE 框架");
  const care = [
    { letter: "C", word: "Context", desc: "提供研究背景\n\n「我在研究工業 NILM，\n使用 CNN 方法，\n目標發表 Q1 期刊」", color: C.teal },
    { letter: "A", word: "Action", desc: "明確任務指令\n\n「請分析 2020-2025 年\n該領域的 research gap，\n列出未解決的問題」", color: C.navy },
    { letter: "R", word: "Role", desc: "指定 AI 角色\n\n「你是 Energy & Buildings\n的資深審稿人，\n有 10 年審稿經驗」", color: C.goldDark },
    { letter: "E", word: "Example", desc: "給出範例格式\n\n「請用表格列出：\n論文/方法/數據集/\nF1-score/限制」", color: C.tealDark },
  ];
  care.forEach((c, i) => {
    const x = 0.3 + i * 2.4;
    s.addShape(pres.shapes.OVAL, { x: x + 0.65, y: 0.9, w: 0.9, h: 0.9, fill: { color: c.color } });
    s.addText(c.letter, { x: x + 0.65, y: 0.9, w: 0.9, h: 0.9, fontSize: 32, bold: true, color: C.white, align: "center", valign: "middle" });
    s.addText(c.word, { x, y: 1.9, w: 2.2, h: 0.35, fontSize: 14, bold: true, color: c.color, align: "center" });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.3, w: 2.2, h: 2.2, fill: { color: C.white }, shadow: shadow(0.1) });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.3, w: 2.2, h: 0.06, fill: { color: c.color } });
    s.addText(c.desc, { x: x + 0.08, y: 2.4, w: 2.04, h: 2.0, fontSize: 9.5, color: C.darkText, lineSpacingMultiple: 1.2 });
  });
  tipBox(s, 0.3, 4.7, 9.4, "CARE = 結構化的研究提問法 — 每一次與 AI 對話都應該遵循這個框架");
})();

// S15: CARE detail — Context
exampleSlide(pres, "CARE 深入 — C: Context（背景）",
  "你正在準備投稿 SCI 期刊，需要 AI 幫你分析 research gap",
  [
    "不好的 Context：",
    "  「幫我找 AI 的論文」（太模糊）",
    "",
    "好的 Context：",
    "  「我是台科大工業管理博士生，研究主題是工業場景的非侵入式",
    "   負載監測 (NILM)。目前使用 1Hz 低採樣率數據，方法是",
    "   CNN + 頻域特徵。目標期刊是 Energy & Buildings 或 SETA，",
    "   需要在 3 個月內完成投稿。」",
    "",
    "關鍵：越具體的 Context → AI 的回答越精準、越相關",
  ]
);

// S16: CARE detail — Role
exampleSlide(pres, "CARE 深入 — R: Role（角色）",
  "不同角色會給出完全不同的回答 — 選對角色是關鍵",
  [
    "「你是一位資深研究者」→ 給你研究方向建議",
    "「你是 Energy & Buildings 的審稿人」→ 指出論文弱點",
    "「你是統計學顧問」→ 幫你選對統計方法",
    "「你是學術英文編輯」→ 幫你潤稿改寫作風格",
    "",
    "5 個研究常用角色：",
    "  1. 領域專家 — 分析趨勢、識別 Gap",
    "  2. 期刊審稿人 — 找出論文弱點",
    "  3. 統計顧問 — 驗證分析方法",
    "  4. 英文編輯 — 改善寫作品質",
    "  5. 研究方法論者 — 審查實驗設計",
  ]
);

// S17: 5 Research Prompt Templates
(() => {
  const s = contentSlide(pres, "5 套研究專用 Prompt 模板");
  const templates = [
    ["領域掃描", "「列出 [領域] 近 5 年的\n5 個主要研究方向」", C.teal],
    ["Gap 識別", "「分析 [方法] 在 [場景]\n的已知限制和未解問題」", C.navy],
    ["可行性分析", "「評估 [方法] 解決 [問題]\n的可行性和風險」", C.tealDark],
    ["創新定位", "「與現有方法相比，\n[方法] 的獨特貢獻是什麼」", C.goldDark],
    ["問題精煉", "「把 [研究方向] 轉化為\n一個可驗證的研究問題」", C.navyLight],
  ];
  templates.forEach((t, i) => {
    const x = 0.3 + i * 1.92;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.9, w: 1.8, h: 3.0, fill: { color: C.white }, shadow: shadow(0.1) });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.9, w: 1.8, h: 0.45, fill: { color: t[2] } });
    s.addText(t[0], { x, y: 0.9, w: 1.8, h: 0.45, fontSize: 12, bold: true, color: C.white, align: "center", valign: "middle" });
    s.addText(t[1], { x: x + 0.08, y: 1.5, w: 1.64, h: 1.8, fontSize: 10, color: C.darkText, lineSpacingMultiple: 1.3 });
  });
  tipBox(s, 0.3, 4.15, 9.4, "模板只是起點 — 結合 CARE 框架，根據你的具體研究調整每個模板的內容");
})();

// S18: Multi-round Dialogue Concept
conceptSlide(pres,
  "多輪對話策略：漸進式縮焦法",
  "不要一次問完 — 用 5 輪對話從「寬」聚焦到「窄」",
  "像漏斗一樣，每一輪都基於上一輪的回答，逐步縮小範圍",
  [
    "Round 1：領域概覽 — 了解大方向和主要研究流派",
    "Round 2：聚焦子領域 — 選定具體技術方向",
    "Round 3：識別問題 — 找出未解決的具體問題",
    "Round 4：驗證假設 — 確認你的想法是否有研究基礎",
    "Round 5：確定貢獻 — 明確你的獨特貢獻點",
  ]
);

// S19: Funnel diagram
(() => {
  const s = contentSlide(pres, "漸進式縮焦法：5 輪對話示範");
  const rounds = [
    { r: "Round 1", q: "「智慧製造有哪些 AI 應用方向？」", w: 9.0, color: C.teal },
    { r: "Round 2", q: "「NILM 目前有哪些深度學習方法？」", w: 7.6, color: C.tealDark },
    { r: "Round 3", q: "「低採樣率 NILM 有什麼尚未解決的問題？」", w: 6.2, color: C.navy },
    { r: "Round 4", q: "「Training-free NILM 可行嗎？有沒有相關研究？」", w: 4.8, color: C.navyLight },
    { r: "Round 5", q: "「LLM + NILM 作為 training-free 方案的創新性？」", w: 3.4, color: C.goldDark },
  ];
  rounds.forEach((rd, i) => {
    const y = 0.85 + i * 0.72;
    const x = (10 - rd.w) / 2;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: rd.w, h: 0.6, fill: { color: rd.color }, rectRadius: 0.08, shadow: shadow(0.08) });
    s.addText(rd.r, { x: x + 0.15, y, w: 1.2, h: 0.6, fontSize: 11, bold: true, color: C.gold, valign: "middle" });
    s.addText(rd.q, { x: x + 1.4, y, w: rd.w - 1.6, h: 0.6, fontSize: 11, color: C.white, valign: "middle" });
  });
  tipBox(s, 0.3, 4.55, 9.4, "每一輪都以上一輪的回答為基礎 — 不是 5 個獨立問題，而是一個連貫的探索過程");
})();

// S20: Extended Thinking
(() => {
  const s = contentSlide(pres, "Extended Thinking：讓 AI 「想深一點」");
  infoCard(s, pres, 0.3, 0.9, 4.5, 2.5, "三個思考深度指令", [
    "think",
    "→ 標準深度思考，適合一般研究問題",
    "",
    "think hard",
    "→ 深度推理，適合複雜的方法論問題",
    "",
    "ultrathink",
    "→ 極限推理（31K tokens），適合架構設計",
  ].join("\n"), C.teal);
  infoCard(s, pres, 5.1, 0.9, 4.6, 2.5, "使用時機建議", [
    "一般問題（文獻搜索、格式調整）：",
    "→ 不需要 Extended Thinking",
    "",
    "中等問題（Gap 分析、方法比較）：",
    "→ think — 標準深度即可",
    "",
    "複雜問題（創新性論證、實驗設計）：",
    "→ think hard 或 ultrathink",
  ].join("\n"), C.navy);
  codeBox(s, pres, 0.3, 3.6, 9.4, 1.0, "Prompt 範例", [
    "think hard",
    "分析 training-free NILM 的三個核心創新點，並評估每個創新點的學術價值和可行性。",
    "請用表格列出：創新點 | 學術價值(1-5) | 實現難度(1-5) | 類似前例 | 風險",
  ].join("\n"));
  tipBox(s, 0.3, 4.8, 9.4, "Extended Thinking 會消耗更多 tokens — 不是每個問題都需要，選擇性使用");
})();

// S21: Direction Confirmation
keyPointsSlide(pres, "方向確認方法論：三角驗證", [
  { heading: "AI 建議", desc: "AI 分析 research gap、建議研究方向\n但 AI 可能有盲點、幻覺、過時資訊" },
  { heading: "文獻證據", desc: "用 API 驗證 AI 建議的論文是否存在\n確認 gap 是否真的未被解決" },
  { heading: "導師意見", desc: "與指導教授討論 AI + 文獻的分析結果\n確認可行性、時間表、資源" },
  { heading: "SMART 研究問題", desc: "Specific + Measurable + Achievable\n+ Relevant + Time-bound" },
]);

// S22: Case Study — NILM+LLM exploration
(() => {
  const s = contentSlide(pres, "真實案例：NILM+LLM 的概念探索歷程");
  const steps = [
    { label: "Week 1", desc: "領域掃描\n工業能源管理\nAI 應用全景", color: C.teal },
    { label: "Week 2", desc: "聚焦 NILM\n非侵入式負載\n識別技術", color: C.tealDark },
    { label: "Week 3", desc: "發現 Gap\n低採樣率場景\n缺乏解方", color: C.navy },
    { label: "Week 4", desc: "創新假設\nLLM 知識遷移\n取代 training", color: C.navyLight },
    { label: "Week 5", desc: "三大貢獻\n確立論文定位\n鎖定期刊", color: C.goldDark },
  ];
  processSteps(s, pres, steps.map((st, i) => ({ n: String(i + 1), title: st.label, desc: st.desc, color: st.color })), 0.9);
  infoCard(s, pres, 0.3, 3.75, 3.0, 1.3, "C1: Training-Free", "首次提出 LLM 驅動的\n免訓練 NILM 框架\n→ 打破「必須標註數據」的假設", C.teal);
  infoCard(s, pres, 3.5, 3.75, 3.0, 1.3, "C2: Prompt Engineering", "設計工業設備專用的\n結構化 Prompt 範本\n→ 可遷移到其他工業場景", C.navy);
  infoCard(s, pres, 6.7, 3.75, 3.0, 1.3, "C3: Multi-Dataset", "跨三個數據集驗證\n9 類設備 F1=0.85\n→ 泛化能力實證", C.goldDark);
})();

// S23: Exercise — S1 Practice
exerciseSlide(pres, "S1 即時練習 — 用 CARE 寫你的第一個研究 Prompt", [
  "選定你自己的研究主題（或用工作坊提供的範例主題）",
  "用 CARE 框架寫一個完整的研究 Prompt（Context + Action + Role + Example）",
  "打開 Claude / ChatGPT，貼上你的 Prompt",
  "與 AI 進行 3 輪漸進式對話（寬→中→窄）",
  "記錄 AI 的回答，標記「需要驗證」的內容",
  "（進階）使用 think hard 嘗試一個複雜問題",
], "15 分鐘 — 個人練習");

// S24: S1 Output
outputSlide(pres, "Session 1 成果", [
  { item: "CARE Prompt", desc: "至少 1 個完整的研究 Prompt（含 Context/Action/Role/Example）" },
  { item: "3 輪對話記錄", desc: "從寬到窄的漸進式對話，含 AI 回答和你的追問" },
  { item: "研究方向初稿", desc: "初步確定的研究主題 + 可能的 research gap" },
]);

// S25: Transition
transitionSlide(pres, "有了研究方向，接下來 —", "找文獻、驗證文獻！");

// ═══════════════════════════════════════════════════════════
// SESSION 2: AI 輔助文獻調研（Slides 26-65）
// ═══════════════════════════════════════════════════════════

// S26: Section Divider
sectionDivider(pres, {
  dayLabel: "Session 2",
  title: "AI 輔助文獻調研\n核心環節",
  subtitle: "Phase 2-3 | 文獻正確性是本課程的核心",
});

// S27: Module cards
moduleSection(pres, "S2", "AI 輔助文獻調研", "11:00-14:30（含午休，共 210 分鐘）", [
  { title: "種子 DOI + API 驗證", desc: "AI 產出候選清單\n三層 API 驗證流程\nCrossRef/Semantic Scholar" },
  { title: "Zotero + Obsidian", desc: "四種匯入方式\n文獻筆記卡\nGraph View 知識圖譜" },
  { title: "BibTeX + Research Gap", desc: "references.bib 管理\nbib-manager 防呆\n文獻矩陣 + Gap 識別" },
  { title: "創新定位 + 期刊匹配", desc: "三層創新框架\n六維度期刊評估\n主編偏好分析" },
]);

// S28: Concept — Trust but Verify
conceptSlide(pres,
  "AI 文獻搜索的核心原則",
  "信任但驗證 — Trust but Verify",
  "AI 可以快速產出文獻清單，但每一篇都必須經過 API 驗證",
  [
    "AI 幻覺問題：GPT-4 產出的學術引用約 30-50% 有錯誤（虛構 DOI、錯誤作者/年份）",
    "但 AI 擅長：識別研究方向、建議搜索關鍵詞、評估相關性",
    "正確做法：AI 產出候選清單 → API 驗證每一篇 → 只保留「確認存在」的文獻",
    "本課程策略：結合 3 個免費 API（CrossRef + Semantic Scholar + OpenAlex）做多重驗證",
  ]
);

// S29: Seed DOI — Prompt example
(() => {
  const s = contentSlide(pres, "種子 DOI 生成：用 AI 產出候選文獻清單");
  codeBox(s, pres, 0.3, 0.9, 4.5, 2.8, "研究 Prompt 範例", [
    "Role: 你是 NILM (Non-Intrusive Load",
    "      Monitoring) 領域的資深研究者",
    "",
    "Context: 我在研究低採樣率(1Hz)工業",
    "         NILM，使用 LLM 作為推理引擎",
    "",
    "Action: 請列出以下三個方向近 5 年最",
    "        重要的 20 篇論文，每篇包含 DOI",
    "  1. 深度學習 NILM 方法",
    "  2. 低採樣率 NILM",
    "  3. LLM 在能源領域的應用",
    "",
    "Example: 格式：作者(年份) 標題 DOI",
  ].join("\n"));
  codeBox(s, pres, 5.1, 0.9, 4.6, 2.8, "AI 產出範例", [
    "1. Kelly & Knottenbelt (2015)",
    "   Neural NILM: Deep Neural Networks",
    "   Applied to Energy Disaggregation",
    "   DOI: 10.1145/2821650.2821672",
    "",
    "2. Zhang et al. (2018)",
    "   Sequence-to-Point Learning with",
    "   Neural Networks for NILM",
    "   DOI: 10.1109/TSG.2017.2743342",
    "",
    "3. [更多候選文獻...]",
    "   (共 20 篇，含 DOI)",
  ].join("\n"));
  warnBox(s, 0.3, 3.9, 9.4, "AI 產出的 DOI 不能直接信任！必須經過 API 驗證。AI 可能：虛構 DOI、張冠李戴作者/年份、捏造論文。");
  tipBox(s, 0.3, 4.6, 9.4, "三層搜索策略：Google Scholar（手動確認）→ ArXiv/IEEE Xplore（資料庫搜索）→ Citation Graph（引用追蹤）");
})();

// S30: 3-layer search strategy
cardsSlide(pres, "三層搜索策略", [
  { icon: "1", title: "Google Scholar", desc: "最基本的學術搜索\n用 AI 建議的關鍵詞搜索\n手動確認論文存在\n適合快速驗證 5-10 篇" },
  { icon: "2", title: "專業資料庫", desc: "ArXiv（預印本）\nIEEE Xplore（工程）\nScienceDirect（綜合）\n用 DOI 直接查找" },
  { icon: "3", title: "Citation Graph", desc: "Forward: 誰引用了這篇？\nBackward: 這篇引用了誰？\nSemantic Scholar 提供\n發現 AI 沒提到的重要文獻" },
  { icon: "+", title: "AI 語義比對", desc: "用 Abstract 做相關性評分\n1-5 分量化篩選\n30 秒評估一篇論文\n快速決定 keep/skip" },
]);

// S31: CrossRef API detail
(() => {
  const s = contentSlide(pres, "API 驗證 Step 1：CrossRef — DOI 存在性驗證");
  codeBox(s, pres, 0.3, 0.9, 5.5, 2.4, "CrossRef API 呼叫", [
    "# 驗證 DOI 是否存在",
    'curl "https://api.crossref.org/works/',
    '  10.1016/j.seta.2020.100921"',
    "",
    "# 回應 (如果存在):",
    '{ "status": "ok",',
    '  "message": {',
    '    "title": ["Industrial NILM..."],',
    '    "author": [{"given":"M","family":"Eskander"}],',
    '    "published": {"date-parts": [[2020,12]]}',
    "  }}",
  ].join("\n"));
  infoCard(s, pres, 6.0, 0.9, 3.7, 2.4, "CrossRef 能做什麼？", [
    "1. 確認 DOI 存在（最基本）",
    "2. 比對 AI 給的 title 是否正確",
    "3. 比對 author 名字是否匹配",
    "4. 比對發表年份是否正確",
    "5. 取得期刊名稱、ISSN",
    "",
    "免費、無需 API Key",
    "速率：50 次/秒",
  ].join("\n"), C.teal);
  infoCard(s, pres, 0.3, 3.5, 9.4, 1.0, "驗證邏輯", [
    "DOI 存在 + Title 匹配 + Author 匹配 + Year 匹配 → 通過驗證 → 加入 references.bib",
    "任何一項不匹配 → 標記為「需人工確認」| DOI 不存在 → 直接淘汰",
  ].join("\n"), C.navy);
  tipBox(s, 0.3, 4.7, 9.4, "CrossRef 涵蓋 1.5 億+ 學術文獻 — 幾乎所有正式出版的期刊論文都能找到");
})();

// S32: Semantic Scholar API
(() => {
  const s = contentSlide(pres, "API 驗證 Step 2：Semantic Scholar — Abstract + 引用數");
  codeBox(s, pres, 0.3, 0.9, 5.5, 2.4, "Semantic Scholar API 呼叫", [
    '# 取得 Abstract + 引用數',
    'curl "https://api.semanticscholar.org/',
    '  graph/v1/paper/DOI:10.1016/j.seta...',
    '  ?fields=abstract,citationCount,year"',
    "",
    '# 回應:',
    '{ "abstract": "This paper presents...",',
    '  "citationCount": 42,',
    '  "year": 2020,',
    '  "authors": [{"name": "M. Eskander"}]}',
  ].join("\n"));
  infoCard(s, pres, 6.0, 0.9, 3.7, 2.4, "Semantic Scholar 能做什麼？", [
    "1. 取得完整 Abstract",
    "2. 查看引用數 (影響力)",
    "3. 查看被引用論文清單",
    "4. 取得研究領域標籤",
    "5. 建立 Citation Graph",
    "",
    "免費、需 API Key (免費)",
    "速率：100 次/5 分鐘",
  ].join("\n"), C.teal);
  tipBox(s, 0.3, 3.5, 9.4, "有了 Abstract，就可以用 AI 做「語義相關性評分」— 自動判斷這篇論文跟你的研究有多相關");
  infoCard(s, pres, 0.3, 4.1, 9.4, 0.9, "進階用法：Citation Graph", [
    "Forward Citation：誰引用了這篇？→ 找到最新的後續研究",
    "Backward Citation：這篇引用了誰？→ 找到經典基礎文獻",
  ].join("\n"), C.navy);
})();

// S33: OpenAlex API
(() => {
  const s = contentSlide(pres, "API 驗證 Step 3：OpenAlex — OA 狀態 + Concepts");
  codeBox(s, pres, 0.3, 0.9, 5.5, 2.0, "OpenAlex API 呼叫", [
    '# 查詢 OA 狀態 + 概念標籤',
    'curl "https://api.openalex.org/works/',
    '  doi:10.1016/j.seta.2020.100921"',
    "",
    '# 回應:',
    '{ "is_oa": true,',
    '  "concepts": [{"display_name": "NILM"},',
    '               {"display_name": "Energy"}],',
    '  "cited_by_count": 45 }',
  ].join("\n"));
  infoCard(s, pres, 6.0, 0.9, 3.7, 2.0, "OpenAlex 獨特價值", [
    "1. OA 狀態 → 能否免費取得全文",
    "2. Concepts 標籤 → 自動分類",
    "3. 機構資訊 → 哪些大學在做",
    "4. 完全免費、無需 API Key",
    "5. 涵蓋 2.5 億+ 文獻",
  ].join("\n"), C.teal);
  // Bottom summary table
  const s2 = s;
  tableSlide(s2,
    ["API", "主要功能", "免費", "需 API Key", "速率"],
    [
      ["CrossRef", "DOI 驗證 + Metadata", "是", "否", "50/秒"],
      ["Semantic Scholar", "Abstract + 引用圖", "是", "是(免費)", "100/5min"],
      ["OpenAlex", "OA + Concepts", "是", "否", "10/秒"],
    ],
    { y: 3.2, colW: [2.0, 2.5, 0.8, 1.3, 1.3] }
  );
  tipBox(s2, 0.3, 4.7, 9.4, "三個 API 互補使用：CrossRef 驗證存在 → Semantic Scholar 取 Abstract → OpenAlex 查 OA 狀態");
})();

// S34: API Demo — curl commands
(() => {
  const s = contentSlide(pres, "API 實戰：一行 curl 驗證 DOI");
  codeBox(s, pres, 0.3, 0.85, 9.4, 1.5, "Step 1: CrossRef 驗證 DOI 存在", [
    '$ curl -s "https://api.crossref.org/works/10.1145/2821650.2821672" | python3 -m json.tool',
    '',
    '# 如果 status=200 → DOI 存在',
    '# 比對 title 是否包含 "Neural NILM" → 確認 AI 沒有張冠李戴',
    '# 比對 author family name → 確認作者正確',
  ].join("\n"));
  codeBox(s, pres, 0.3, 2.5, 9.4, 1.2, "Step 2: Semantic Scholar 取 Abstract", [
    '$ curl -s "https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/2821650.2821672',
    '  ?fields=abstract,citationCount" | python3 -m json.tool',
    '',
    '# 取得 abstract → 交給 AI 做相關性評分 (1-5 分)',
  ].join("\n"));
  codeBox(s, pres, 0.3, 3.85, 4.5, 1.1, "Python 批次驗證（概念）", [
    'import requests',
    'for doi in seed_dois:',
    '  r = requests.get(f"https://api.crossref.org/works/{doi}")',
    '  if r.status_code == 200:',
    '    verified.append(doi)',
  ].join("\n"));
  infoCard(s, pres, 5.0, 3.85, 4.7, 1.1, "驗證結果", [
    "案例：NILM+LLM 論文",
    "AI 產出 50 個候選 DOI",
    "→ CrossRef 驗證：43 存在、7 虛構",
    "→ 最終保留 43 篇進入 .bib",
  ].join("\n"), C.teal);
})();

// S35: Verification Pipeline
(() => {
  const s = contentSlide(pres, "完整文獻驗證流水線");
  const flow = [
    { label: "AI 產出\n候選 DOI", color: C.orange },
    { label: "CrossRef\n存在驗證", color: C.teal },
    { label: "Semantic\nScholar", color: C.navy },
    { label: "OpenAlex\nOA 查詢", color: C.tealDark },
    { label: "AI 相關性\n評分 1-5", color: C.goldDark },
    { label: "Zotero\n匯入", color: C.green },
  ];
  flow.forEach((f, i) => {
    const x = 0.25 + i * 1.6;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.0, w: 1.4, h: 1.0, fill: { color: f.color }, rectRadius: 0.08, shadow: shadow(0.1) });
    s.addText(f.label, { x, y: 1.0, w: 1.4, h: 1.0, fontSize: 11, bold: true, color: C.white, align: "center", valign: "middle", lineSpacingMultiple: 1.15 });
    if (i < flow.length - 1) s.addText("\u25B6", { x: x + 1.4, y: 1.3, w: 0.2, h: 0.4, fontSize: 12, color: C.grayText, align: "center" });
  });
  // Stats
  const stats = [
    ["AI 產出", "50 篇候選", C.orange],
    ["CrossRef 通過", "43 篇 (86%)", C.teal],
    ["Abstract 取得", "41 篇 (95%)", C.navy],
    ["相關性 ≥ 3", "38 篇 (93%)", C.goldDark],
    ["最終收錄", "43 篇", C.green],
  ];
  stats.forEach((st, i) => {
    const y = 2.4 + i * 0.42;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y, w: 9.4, h: 0.38, fill: { color: i % 2 === 0 ? C.white : C.lightBlue } });
    s.addText(st[0], { x: 0.5, y, w: 2.5, h: 0.38, fontSize: 11, bold: true, color: st[2], valign: "middle" });
    s.addText(st[1], { x: 3.2, y, w: 2.5, h: 0.38, fontSize: 11, color: C.darkText, valign: "middle" });
    // Progress bar
    const pct = [1.0, 0.86, 0.82, 0.76, 0.86][i];
    s.addShape(pres.shapes.RECTANGLE, { x: 6.0, y: y + 0.08, w: 3.5 * pct, h: 0.22, fill: { color: st[2], transparency: 30 } });
  });
  tipBox(s, 0.3, 4.6, 9.4, "整個流程可自動化 — Claude Code 可以幫你寫 Python 腳本批次處理 50+ 篇文獻");
})();

// S36: Zotero concept
conceptSlide(pres,
  "Zotero：你的文獻管理中心",
  "免費、開源的文獻管理工具，支援 Word / LaTeX / QMD 引用插入",
  "把驗證過的文獻統一管理，自動抓 PDF + metadata",
  [
    "為什麼用 Zotero？— 免費、跨平台、開源、社群活躍",
    "核心功能：PDF 管理 + 引用插入 + 群組分享 + 同步",
    "與 AI 工作流整合：API 驗證 DOI → BibTeX 匯出 → Zotero 匯入 → 自動抓 PDF",
    "Zotero 6 的標註功能：直接在 PDF 上畫重點 → 匯出到 Obsidian",
  ]
);

// S37: Zotero 4 methods
cardsSlide(pres, "Zotero 四種匯入方式", [
  { icon: "1", title: "Magic Wand", desc: "在工具列貼上 DOI 清單\n自動取得完整 metadata\n最簡單\n適合 5-10 篇" },
  { icon: "2", title: "Browser Connector", desc: "瀏覽器擴充套件\nGoogle Scholar 頁面\n一鍵批次儲存\n適合搜索中匯入" },
  { icon: "3", title: "BibTeX 匯入", desc: "匯入 references.bib\n保留所有欄位\n適合已有 BibTeX\n適合 AI 驗證後的清單" },
  { icon: "4", title: "Zotero API", desc: "程式化匯入 (pyzotero)\n大量文獻自動化\n適合 50+ 篇\n適合與 Claude Code 整合" },
]);

// S38: Zotero step-by-step
stepSlide(pres, "Zotero 匯入實作", 1, "DOI 匯入（最簡單的方式）", [
  "打開 Zotero → 點擊工具列的「魔術棒」圖示（Add Item by Identifier）",
  "貼上 DOI：10.1145/2821650.2821672",
  "Zotero 自動從 CrossRef 取得完整 metadata（標題、作者、期刊、年份）",
  "自動嘗試下載 PDF（如果有 Open Access 版本）",
  "重複貼上其他 DOI — 可以一次貼多個（一行一個）",
]);

stepSlide(pres, "Zotero 匯入實作", 2, "BibTeX 匯入（適合批次匯入）", [
  "先用 AI + API 驗證，產出一份乾淨的 references.bib",
  "Zotero → File → Import... → 選擇 references.bib",
  "所有條目自動匯入，保留 citekey、DOI、完整欄位",
  "建議：建立一個 Collection 叫「AI-Verified」存放驗證過的文獻",
  "之後在 QMD 寫作時，直接用 citekey 引用（如 @kelly2015）",
]);

// S40: Obsidian concept
conceptSlide(pres,
  "Obsidian：文獻知識圖譜",
  "每篇論文一張筆記卡 + 雙向連結 = 可視化的知識網路",
  "Obsidian 的 Graph View 讓你「看見」文獻之間的關係",
  [
    "為什麼不只用 Zotero？— Zotero 管文獻，Obsidian 管知識和關係",
    "核心概念：每篇論文 = 一個 Markdown 文件 + YAML frontmatter",
    "雙向連結 [[paper]]：論文 A 引用論文 B → 自動建立雙向關係",
    "Graph View：所有文獻的視覺化網路圖 → 孤立節點 = 可能遺漏的重要文獻",
    "模板系統：AI 幫你生成標準化的筆記卡，確保每篇論文都記錄相同的資訊",
  ]
);

// S41: Obsidian note card template
(() => {
  const s = contentSlide(pres, "Obsidian 文獻筆記卡模板");
  codeBox(s, pres, 0.3, 0.85, 4.6, 4.0, "標準化筆記卡範例", [
    "---",
    "tags: [NILM, training-free, CNN]",
    'doi: "10.1145/2821650.2821672"',
    "year: 2015",
    "authors: [Kelly, Knottenbelt]",
    "journal: BuildSys",
    "relevance: 5/5",
    "cite_in: [Introduction, Related Work]",
    "---",
    "",
    "# Kelly2015 - Neural NILM",
    "",
    "## Core Contribution",
    "首篇將 deep learning 應用於 NILM",
    "提出 seq2point 和 seq2seq 兩種架構",
    "",
    "## Key Results",
    "REDD dataset, F1=0.83 (washing machine)",
    "",
    "## Link to My Research",
    "-> 支撐 Related Work -> [[Research_Gap]]",
    "-> 比較 baseline -> [[Experiment_Design]]",
    "",
    "## Related Papers",
    "-> [[Hart1992]] [[Zhang2018]]",
  ].join("\n"));
  infoCard(s, pres, 5.1, 0.85, 4.6, 1.8, "YAML Frontmatter 說明", [
    "tags → 分類標籤，Obsidian 搜索用",
    "doi → 連回原始論文",
    "relevance → 與我研究的相關性 (1-5)",
    "cite_in → 計劃引用在論文哪個章節",
    "",
    "所有欄位都可以用 AI 自動生成！",
    "Prompt：「幫我為這篇論文建立",
    "Obsidian 文獻筆記卡」",
  ].join("\n"), C.teal);
  infoCard(s, pres, 5.1, 2.85, 4.6, 2.0, "雙向連結的力量", [
    "[[Research_Gap]] → 連到你的 Gap 分析",
    "[[Hart1992]] → 連到其他文獻卡",
    "[[Experiment_Design]] → 連到實驗設計",
    "",
    "Graph View 會自動顯示：",
    "• 哪些論文經常被一起引用",
    "• 哪些論文是「孤島」（可能遺漏）",
    "• 哪個主題的文獻最密集",
  ].join("\n"), C.navy);
})();

// S42: Obsidian Graph View
(() => {
  const s = contentSlide(pres, "Obsidian Graph View：可視化知識圖譜");
  // Simulated graph
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 0.85, w: 5.5, h: 4.0, fill: { color: C.slate }, shadow: shadow() });
  s.addText("Graph View 示意", { x: 0.3, y: 0.88, w: 5.5, h: 0.3, fontSize: 12, bold: true, color: C.gold, align: "center" });
  const nodes = [
    { x: 1.2, y: 1.5, r: 0.22, label: "Hart\n1992", color: C.teal },
    { x: 2.8, y: 1.3, r: 0.28, label: "Kelly\n2015", color: C.teal },
    { x: 0.8, y: 2.3, r: 0.2, label: "Zhang\n2018", color: C.tealDark },
    { x: 2.2, y: 2.5, r: 0.35, label: "My\nResearch", color: C.gold },
    { x: 3.8, y: 2.2, r: 0.22, label: "Esk.\n2021", color: C.tealDark },
    { x: 1.5, y: 3.3, r: 0.18, label: "LLM\nNILM", color: C.goldDark },
    { x: 3.5, y: 3.1, r: 0.2, label: "GPT\nEnergy", color: C.navyLight },
    { x: 4.5, y: 1.5, r: 0.15, label: "Gap", color: C.red },
    { x: 4.8, y: 3.5, r: 0.15, label: "Lone\nPaper", color: C.grayText },
  ];
  nodes.forEach(n => {
    s.addShape(pres.shapes.OVAL, { x: n.x, y: n.y, w: n.r * 2, h: n.r * 2, fill: { color: n.color, transparency: 30 } });
    s.addText(n.label, { x: n.x, y: n.y, w: n.r * 2, h: n.r * 2, fontSize: 7, bold: true, color: C.white, align: "center", valign: "middle" });
  });
  // Legend + explanation
  infoCard(s, pres, 6.1, 0.85, 3.6, 2.0, "如何解讀 Graph View", [
    "大節點 = 被多篇引用（重要文獻）",
    "連線密集 = 主題聚類",
    "孤立節點 = 可能遺漏相關文獻",
    "「My Research」應該在中心位置",
    "",
    "紅色「Gap」= 你的研究切入點",
  ].join("\n"), C.teal);
  infoCard(s, pres, 6.1, 3.1, 3.6, 1.7, "實用技巧", [
    "1. 每加一篇文獻 → 建立連結",
    "2. 每週看一次 Graph View",
    "3. 找出孤立節點 → 補充文獻",
    "4. 用 tag 過濾 → 專注子主題",
    "5. 截圖放入論文 Committee",
  ].join("\n"), C.navy);
})();

// S43: Abstract 5-dimension evaluation
(() => {
  const s = contentSlide(pres, "AI 30 秒評估一篇論文：5 維度快速篩選");
  const dims = [
    { name: "相關性", w: "30%", desc: "與我研究的\n直接關聯", color: C.teal },
    { name: "新穎性", w: "20%", desc: "方法的\n原創程度", color: C.navy },
    { name: "影響力", w: "20%", desc: "引用數\n期刊等級", color: C.tealDark },
    { name: "可比較", w: "15%", desc: "能否做\nbaseline", color: C.goldDark },
    { name: "引用值", w: "15%", desc: "放在哪個\n章節引用", color: C.navyLight },
  ];
  dims.forEach((d, i) => {
    const x = 0.3 + i * 1.92;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.85, w: 1.8, h: 2.3, fill: { color: C.white }, shadow: shadow(0.1) });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.85, w: 1.8, h: 0.45, fill: { color: d.color } });
    s.addText(d.name, { x, y: 0.85, w: 1.8, h: 0.45, fontSize: 13, bold: true, color: C.white, align: "center", valign: "middle" });
    s.addText(d.w, { x, y: 1.4, w: 1.8, h: 0.35, fontSize: 18, bold: true, color: d.color, align: "center" });
    s.addText(d.desc, { x: x + 0.1, y: 1.8, w: 1.6, h: 0.8, fontSize: 10, color: C.darkText, align: "center", lineSpacingMultiple: 1.25 });
  });
  codeBox(s, pres, 0.3, 3.35, 9.4, 1.3, "Prompt 範例：30 秒文獻評估", [
    "請用 5 維度評估以下論文的 Abstract 對我研究的價值。",
    "我的研究：工業 NILM + LLM，低採樣率，投稿 SETA。",
    "論文 Abstract：[貼上 Abstract]",
    "請用表格列出：維度 | 分數(1-5) | 理由（一句話） | 建議引用章節",
  ].join("\n"));
  tipBox(s, 0.3, 4.85, 9.4, "Claude 可以 30 秒完成評估 — 50 篇文獻 25 分鐘搞定，人工至少需要 2-3 天");
})();

// S44: BibTeX structure
(() => {
  const s = contentSlide(pres, "BibTeX 引用管理基礎");
  codeBox(s, pres, 0.3, 0.85, 4.5, 2.8, "references.bib 結構", [
    "@article{kelly2015neural,",
    "  title   = {Neural NILM: Deep Neural",
    "             Networks Applied to Energy",
    "             Disaggregation},",
    "  author  = {Kelly, Jack and",
    "             Knottenbelt, William},",
    "  journal = {BuildSys},",
    "  year    = {2015},",
    "  doi     = {10.1145/2821650.2821672}",
    "}",
    "",
    "@article{zhang2018seq2point,",
    "  title   = {Sequence-to-Point Learning",
    "             for NILM},",
    "  ...",
    "}",
  ].join("\n"));
  infoCard(s, pres, 5.1, 0.85, 4.6, 1.4, "BibTeX 關鍵欄位", [
    "citekey → QMD 中引用的 ID (@kelly2015neural)",
    "title → 完整論文標題",
    "author → 作者（姓, 名 格式）",
    "journal → 期刊/會議名稱",
    "year → 發表年份",
    "doi → DOI（最重要，可追溯）",
  ].join("\n"), C.teal);
  infoCard(s, pres, 5.1, 2.45, 4.6, 1.2, "QMD 引用語法", [
    "單引用：@kelly2015neural",
    "括號引用：[@kelly2015neural]",
    "多引用：[@kelly2015; @zhang2018]",
    "行內引用：如 @kelly2015 所述",
  ].join("\n"), C.navy);
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 3.9, w: 9.4, h: 0.6, fill: { color: "FFF7E6" } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 3.9, w: 0.07, h: 0.6, fill: { color: C.gold } });
  s.addText("黃金規則：絕不添加 references.bib 中不存在的引用 — AI 要引用，必須先驗證 DOI、新增到 .bib、再引用", {
    x: 0.5, y: 3.9, w: 9.0, h: 0.6, fontSize: 11, bold: true, color: C.goldDark, valign: "middle",
  });
  tipBox(s, 0.3, 4.7, 9.4, "DOI → BibTeX 自動生成：https://doi.org/[DOI] 加上 Accept: application/x-bibtex header");
})();

// S45: bib-manager skill
keyPointsSlide(pres, "bib-manager Skill 防呆機制", [
  { heading: "重複條目偵測", desc: "自動偵測相同 DOI 或相似 title 的重複條目" },
  { heading: "格式一致性", desc: "field 命名統一（title/author/year）、縮排一致" },
  { heading: "幽靈引用警告", desc: ".bib 中有但論文中沒引用的條目 → 是否該刪除？" },
  { heading: "遺漏引用偵測", desc: "論文中引用了但 .bib 中沒有的 → 必須補上" },
  { heading: "CrossRef 交叉驗證", desc: "自動比對 .bib 中的年份/作者與 CrossRef 回傳是否一致" },
  { heading: "案例統計", desc: "NILM+LLM 論文 43 篇引用：發現 3 個格式問題 + 2 個幽靈引用" },
]);

// S46: Research Gap
conceptSlide(pres,
  "Research Gap 識別方法",
  "Gap = 現有研究已知但未解決的問題",
  "好的 Gap 需要文獻證據支撐 — 不是你「覺得」有 Gap，而是文獻「證明」有 Gap",
  [
    "Step 1：建立文獻分類矩陣 — 方法 × 數據集 × 場景 × 指標",
    "Step 2：識別矩陣中的「空白格」— 沒有研究覆蓋的組合",
    "Step 3：分析空白的原因 — 是技術困難？還是被忽視？",
    "Step 4：評估填補可行性 — 你的方法能否解決這個問題？",
    "Step 5：文獻佐證 — 找到明確說「this remains unsolved」的引用",
  ]
);

// S47: 3-layer gap
(() => {
  const s = contentSlide(pres, "三層 Research Gap 識別法");
  const layers = [
    { label: "現有方法", desc: "CNN/RNN/Transformer 需要大量標註數據，監督式學習佔 NILM 研究 85%", w: 9.0, color: C.teal },
    { label: "已知限制", desc: "工業場景標註成本高（$5K-50K/設備）；低採樣率 (1Hz) 資訊量不足", w: 7.0, color: C.navy },
    { label: "研究機會", desc: "Training-free NILM：利用 LLM 世界知識取代訓練 = 本論文的核心貢獻", w: 5.0, color: C.goldDark },
  ];
  layers.forEach((l, i) => {
    const x = (10 - l.w) / 2;
    const y = 0.9 + i * 1.05;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: l.w, h: 0.85, fill: { color: l.color }, rectRadius: 0.08, shadow: shadow(0.1) });
    s.addText(l.label, { x: x + 0.2, y, w: 1.6, h: 0.85, fontSize: 13, bold: true, color: C.gold, valign: "middle" });
    s.addText(l.desc, { x: x + 1.9, y, w: l.w - 2.2, h: 0.85, fontSize: 10.5, color: C.white, valign: "middle", lineSpacingMultiple: 1.2 });
  });
  infoCard(s, pres, 0.3, 4.1, 4.5, 1.0, "literature-synthesis Skill", "觸發詞：「文獻回顧」「research gap」\n自動建立分類矩陣 + 識別 Gap", C.teal);
  infoCard(s, pres, 5.1, 4.1, 4.6, 1.0, "/analyze-literature Command", "一鍵啟動：輸入主題關鍵詞\n輸出 Gap 分析 + 文獻矩陣 + 建議結構", C.navy);
})();

// S48: Innovation positioning
(() => {
  const s = contentSlide(pres, "創新性定位：innovation-positioning Skill");
  infoCard(s, pres, 0.3, 0.85, 4.5, 2.5, "三層創新框架", [
    "Layer 1: 技術創新",
    "→ 新方法、新架構、新演算法",
    "→ 最高價值，Q1 期刊看重",
    "",
    "Layer 2: 應用創新",
    "→ 新場景、新數據集、新領域",
    "→ 需搭配技術差異化",
    "",
    "Layer 3: 整合創新",
    "→ 跨域結合（如 LLM + NILM）",
    "→ 需證明整合的獨特價值",
  ].join("\n"), C.teal);
  infoCard(s, pres, 5.1, 0.85, 4.6, 2.5, "避免的陷阱", [
    '\"Inspired by the success of...\"',
    "→ 暗示跟風，不是創新",
    "",
    '\"We improve upon...\"',
    "→ 暗示改進，不是突破",
    "",
    '\"Few studies have explored...\"',
    "→ 要有數據佐證「few」有多少",
    "",
    "正確做法：「To the best of our knowledge,",
    "this is the first work that...」+ 文獻佐證",
  ].join("\n"), C.orange);
  tipBox(s, 0.3, 3.55, 9.4, "NILM+LLM 論文的創新聲明：「the first training-free framework using LLM for industrial NILM」— 有文獻佐證");
  infoCard(s, pres, 0.3, 4.15, 9.4, 0.9, "journal-fit Skill — 期刊適配度分析", [
    "六維度加權評分：Scope 35% + IF 15% + 主編偏好 20% + 近期主題 15% + 審稿週期 10% + OA/APC 5%",
    "含 desk-reject 風險評估 + 主編研究方向分析（Google Scholar + Editorial）",
  ].join("\n"), C.navy);
})();

// S49: Journal matching
(() => {
  const s = contentSlide(pres, "期刊匹配：六維度加權評分");
  tableSlide(s,
    ["維度", "權重", "內容", "案例 (SETA)"],
    [
      ["Scope 契合度", "35%", "Aims & Scope 關鍵詞重疊", "能源+AI+永續 = 高"],
      ["Impact Factor", "15%", "JCR + CiteScore 排名", "IF=7.4, Q1"],
      ["主編研究偏好", "20%", "主編領域、近期 Editorial", "偏好 AI+Energy"],
      ["近期收錄主題", "15%", "近 2 年 topic clustering", "NILM 6 篇/年"],
      ["審稿週期", "10%", "First Decision 時間", "~45 天"],
      ["OA / APC", "5%", "Open Access 費用", "APC $2,500"],
    ],
    { y: 0.85, colW: [1.8, 0.8, 2.8, 2.5] }
  );
  infoCard(s, pres, 0.3, 3.9, 9.4, 1.1, "主編分析方法（關鍵新增）", [
    "1. 期刊官網 → Editorial Board → 記錄 EIC + AE",
    "2. Google Scholar 查主編近 5 年發表 → h-index + 研究關鍵詞",
    "3. 分析 Editorial/Guest Editorial → 偏好方向",
    "4. 時機判斷：新主編上任 = 更開放 | Special Issue = 高契合度",
  ].join("\n"), C.teal);
})();

// S50: S2 Exercise
exerciseSlide(pres, "S2 綜合練習 — 建立你的文獻系統", [
  "用 AI 產出你研究主題的 10 個種子 DOI",
  "用 CrossRef API 驗證至少 5 個 DOI（curl 或 Python）",
  "在 Obsidian 建立 3 篇文獻筆記卡（含 YAML frontmatter + 雙向連結）",
  "建立 references.bib（至少 5 篇驗證過的引用）",
  "嘗試 Research Gap 識別：建立簡單的文獻分類矩陣",
  "（進階）用 Semantic Scholar API 取 Abstract + 做相關性評分",
], "45 分鐘 — 個人實作");

// S51: S2 Output
outputSlide(pres, "Session 2 成果", [
  { item: "驗證過的文獻清單", desc: "至少 5 篇經 CrossRef API 驗證的正確引用" },
  { item: "Obsidian 知識庫", desc: "3 篇文獻筆記卡 + 雙向連結 + Graph View" },
  { item: "references.bib", desc: "格式正確的 BibTeX 引用檔案" },
  { item: "文獻分類矩陣", desc: "方法 × 數據集 × 場景 的初步矩陣" },
  { item: "Research Gap 初稿", desc: "識別的研究缺口 + 佐證文獻" },
]);

// S52: Transition
transitionSlide(pres, "手動做太累了？", "讓自動化工具幫你！");

// ═══════════════════════════════════════════════════════════
// AUTOMATION + CLAUDE CODE (Slides 53-65)
// ═══════════════════════════════════════════════════════════

// S53: Section Divider
sectionDivider(pres, {
  dayLabel: "Day 1 下午",
  title: "自動化工具入門\n+ Claude Code 初體驗",
  subtitle: "Google Apps Script + Claude Code CLI 入門",
});

// S54: GAS concept
conceptSlide(pres,
  "Google Apps Script：零程式基礎的自動化",
  "GAS = Google 內建的自動化引擎 — 免費、免安裝、用 AI 幫你寫腳本",
  "把你的重複性工作自動化：批次 PDF 分析、文獻追蹤通知、引用格式轉換",
  [
    "你不需要會寫程式 — 把需求描述給 AI，AI 產出 GAS 腳本",
    "串接所有 Google 服務：Drive + Sheets + Gmail + Calendar",
    "研究場景：Google Drive 上傳 PDF → Claude API 擷取摘要 → Sheet 彙整",
    "文獻追蹤：每週自動查 Semantic Scholar → 新引用 → Email 通知",
  ]
);

// S55: 3 GAS use cases
cardsSlide(pres, "GAS 研究自動化三大用途", [
  { icon: "1", title: "批次 PDF 分析", desc: "Google Drive 上傳 PDF\n→ Apps Script 觸發\n→ Claude API 擷取摘要\n→ Google Sheet 彙整" },
  { icon: "2", title: "文獻追蹤通知", desc: "每週排程執行\n→ Semantic Scholar API\n→ 查詢你論文的新引用\n→ Email/TG 通知" },
  { icon: "3", title: "引用格式轉換", desc: "Google Sheet 文獻清單\n→ CrossRef API 取 metadata\n→ 自動生成 BibTeX\n→ 匯出 references.bib" },
]);

// S56: GAS quick start
(() => {
  const s = contentSlide(pres, "GAS 快速上手：5 行搞定 PDF 分析");
  codeBox(s, pres, 0.3, 0.85, 9.4, 2.3, "Google Apps Script 範例", [
    "function analyzePDF() {",
    "  // 1. 從 Drive 取得檔案",
    '  const file = DriveApp.getFileById("FILE_ID");',
    "",
    "  // 2. 呼叫 Claude API 分析",
    '  const response = UrlFetchApp.fetch("https://api.anthropic.com/v1/messages", {',
    '    method: "POST",',
    '    headers: {"x-api-key": "YOUR_KEY", "content-type": "application/json"},',
    '    payload: JSON.stringify({model: "claude-sonnet-4-6", messages: [{role: "user",',
    '      content: "Summarize this paper: " + file.getBlob().getDataAsString()}]})',
    "  });",
    "",
    "  // 3. 結果寫入 Sheet",
    '  SpreadsheetApp.getActive().getSheetByName("Results")',
    "    .appendRow([file.getName(), JSON.parse(response).content[0].text]);",
    "}",
  ].join("\n"));
  tipBox(s, 0.3, 3.35, 9.4, "這段腳本用 AI 幫你寫 — 你只需說「幫我寫一個分析 Drive PDF 並寫入 Sheet 的 GAS 腳本」");
  infoCard(s, pres, 0.3, 3.95, 9.4, 1.1, "設定觸發器 → 全自動", [
    "事件觸發：新 PDF 上傳到 Drive → 自動分析",
    "時間觸發：每週一早上 8 點 → 自動查新引用",
    "一次設定，永久自動執行 — 你什麼都不用做",
  ].join("\n"), C.teal);
})();

// S57: Claude Code concept
conceptSlide(pres,
  "Claude Code：你的 AI 研究助手",
  "Claude Code = AI + 終端機 + 專案知識 — 在你的電腦上執行研究任務",
  "不只是聊天，而是能讀寫檔案、執行程式碼、管理你的研究專案",
  [
    "安裝：npm install -g @anthropic-ai/claude-code",
    "啟動：在你的研究專案目錄中輸入 claude",
    "特色：能存取你的檔案 → 理解你的專案結構 → 主動執行任務",
    "Day 2 深入學習：CLAUDE.md + Skills + Agents + Commands",
  ]
);

// S58: CLAUDE.md concept
(() => {
  const s = contentSlide(pres, 'CLAUDE.md = AI 的「工作手冊」');
  codeBox(s, pres, 0.3, 0.85, 4.5, 3.2, "CLAUDE.md 核心結構", [
    "# 引用處理原則（最高優先級）",
    "1. 只使用 references.bib 中存在的引用",
    "2. 絕不自行推測或添加新引用",
    "3. 發現引用問題時，指出而非自動修正",
    "",
    "# 檔案操作原則",
    "1. 不刪除 data/raw/ 內的原始數據",
    "2. 不覆蓋既有檔案",
    "3. 所有產出放到 05_outputs/",
    "",
    "# 專案目錄結構",
    "01_literature/  → 文獻管理",
    "02_research/    → 研究核心",
    "03_manuscripts/ → 論文撰寫",
    "04_presentations/ → 簡報",
    "05_outputs/     → Claude 產出區",
  ].join("\n"));
  infoCard(s, pres, 5.1, 0.85, 4.6, 1.5, "為什麼需要 CLAUDE.md？", [
    "AI 沒有「記憶」— 每次對話都是新開始",
    "CLAUDE.md 讓 AI 一啟動就知道：",
    "• 你是誰、在做什麼研究",
    "• 引用的紅線（不能虛構）",
    "• 檔案放在哪裡",
    "• 你的工作流程和偏好",
  ].join("\n"), C.teal);
  infoCard(s, pres, 5.1, 2.55, 4.6, 1.5, "Skills / Agents / Commands", [
    "Skills (24 個)：專業知識庫",
    "→ 說「引用」自動觸發 bib-manager",
    "",
    "Agents (8 個)：AI 專家團隊",
    "→ citation-checker 只讀不改，安全",
    "",
    "Commands (5 個)：一鍵工作流",
    "→ /review-paper → 完整審查",
  ].join("\n"), C.navy);
  tipBox(s, 0.3, 4.3, 9.4, "Day 2 深入教學：CLAUDE.md 撰寫 + Skills 系統 + Agents 協作 + Commands 自動化");
})();

// S59: Claude Code demo
exampleSlide(pres, "Claude Code Demo：批次驗證 DOI",
  "你有一份 AI 產出的 50 個 DOI 清單，需要全部驗證正確性",
  [
    "$ claude",
    "> 請幫我驗證 seed_dois.txt 中所有 DOI 的正確性。",
    "  使用 CrossRef API 檢查每個 DOI 是否存在，",
    "  並比對 AI 產出的作者/年份是否與 CrossRef 一致。",
    "  將結果整理成表格：DOI | 狀態 | AI作者 | 實際作者 | 匹配",
    "",
    "Claude Code 自動執行：",
    "  1. 讀取 seed_dois.txt（50 個 DOI）",
    "  2. 寫 Python 腳本呼叫 CrossRef API",
    "  3. 逐一驗證 → 比對 → 標記",
    "  4. 輸出驗證報告表格",
    "  → 2 分鐘完成，手動需要 2 小時",
  ]
);

// S60: Before/After workflow
beforeAfterSlide(pres, "手動 vs AI 自動化研究工作流",
  [
    "手動 Google Scholar 搜索",
    "逐篇開 DOI 檢查是否存在",
    "手動複製 BibTeX 到 .bib 檔",
    "用 Excel 記錄文獻資訊",
    "手動撰寫 Related Work",
    "請同事幫忙審閱引用",
    "",
    "每篇文獻 ~15 分鐘",
    "50 篇 = 12.5 小時",
  ],
  [
    "AI 產出種子 DOI 清單",
    "Claude Code 批次 API 驗證",
    "自動生成 references.bib",
    "Obsidian 結構化知識圖譜",
    "literature-synthesis 生成初稿",
    "bib-manager + citation-checker",
    "",
    "每篇文獻 ~2 分鐘",
    "50 篇 = 1.5 小時",
  ]
);

// ═══════════════════════════════════════════════════════════
// CLOSING (Slides 61-67)
// ═══════════════════════════════════════════════════════════

// S61: Day 1 Review
keyPointsSlide(pres, "Day 1 核心技能回顧（10 項）", [
  { heading: "CARE Prompt 框架", desc: "結構化研究提問法" },
  { heading: "漸進式縮焦法", desc: "5 輪對話從寬到窄" },
  { heading: "Extended Thinking", desc: "think / think hard / ultrathink" },
  { heading: "種子 DOI 生成", desc: "AI 產出 + 必須驗證" },
  { heading: "CrossRef API 驗證", desc: "DOI 存在性 + metadata 比對" },
  { heading: "Semantic Scholar / OpenAlex", desc: "Abstract + 引用數 + OA" },
]);

keyPointsSlide(pres, "Day 1 核心技能回顧（續）", [
  { heading: "Zotero 文獻管理", desc: "4 種匯入方式 + PDF 管理" },
  { heading: "Obsidian 知識圖譜", desc: "筆記卡 + 雙向連結 + Graph View" },
  { heading: "BibTeX 引用管理", desc: "黃金規則：不添加未驗證引用" },
  { heading: "Research Gap 識別", desc: "三層法 + 文獻矩陣" },
]);

// S63: Comprehensive Exercise
exerciseSlide(pres, "Day 1 綜合實作練習", [
  "用 CARE 框架寫 3 個研究 Prompt（不同角度）",
  "與 AI 進行 5 輪漸進式對話，確定研究方向",
  "用 AI 產出 10 個種子 DOI",
  "用 CrossRef API 驗證至少 5 個 DOI 正確性",
  "建立 3 篇 Obsidian 文獻筆記卡（含雙向連結）",
  "建立 references.bib（至少 5 篇驗證過的引用）",
  "（進階）用 Semantic Scholar 取 Abstract 做相關性評分",
  "（進階）嘗試 Research Gap 識別",
], "30 分鐘 — 個人實作");

// S64: Homework
(() => {
  const s = contentSlide(pres, "回家作業（可選）");
  infoCard(s, pres, 0.3, 0.9, 4.5, 2.0, "基礎任務", [
    "1. 擴充文獻到 20 篇",
    "   （全部經 CrossRef API 驗證）",
    "",
    "2. 完成 Research Gap 分析初稿",
    "   （含文獻分類矩陣）",
    "",
    "3. 寫一份 1 頁研究方向說明",
    "   （含 Gap + 貢獻 + 預期成果）",
  ].join("\n"), C.teal);
  infoCard(s, pres, 5.1, 0.9, 4.6, 2.0, "進階任務（Day 2 前準備）", [
    "1. 安裝 Claude Code CLI",
    "   npm i -g @anthropic-ai/claude-code",
    "",
    "2. 安裝 Quarto",
    "   brew install quarto (Mac)",
    "",
    "3. 準備至少 5 篇 PDF 文獻",
    "   （Day 2 會用 AI 分析）",
  ].join("\n"), C.navy);
  infoCard(s, pres, 0.3, 3.1, 9.4, 1.2, "Day 2 預告", [
    "Session 3：IMRaD 論文架構 + QMD/YAML + 實驗設計 + GPU 遠端執行 + TG Bot 監控",
    "Session 4：BibTeX 進階 + 學術寫作 + SVG 向量圖 + Claude Code 深度體驗",
    "Session 5：七維度品質審查 + Claude×ChatGPT×Gemini 平行審查 + 投稿策略 + 系統部署",
  ].join("\n"), C.goldDark);
})();

// S65: Day 2 Preview
(() => {
  const s = pres.addSlide();
  s.background = { color: C.navy };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.12, h: 5.625, fill: { color: C.teal } });
  s.addText("明天，你將擁有\n一個完整的 AI 研究團隊", { x: 0.5, y: 0.3, w: 9, h: 1.2, fontSize: 36, bold: true, color: C.white, lineSpacingMultiple: 1.15 });
  const cats = [
    { title: "24 Skills", desc: "paper-review\nbib-manager\nstatistical-validation\nevidence-indexer\nmvp-gatekeeper\n...", color: C.teal },
    { title: "8 Agents", desc: "research-orchestrator\nliterature-researcher\npaper-writer\ncitation-checker\npaper-reviewer\n...", color: C.goldDark },
    { title: "5 Commands", desc: "/review-paper\n/analyze-literature\n/analyze-experiment\n/prepare-submission\n/respond-reviewers", color: C.tealDark },
    { title: "5 APIs", desc: "CrossRef\nSemantic Scholar\nOpenAlex\nClaude API\nZotero API", color: C.navyLight },
  ];
  cats.forEach((c, i) => {
    const x = 0.5 + i * 2.35;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.7, w: 2.15, h: 3.2, fill: { color: c.color, transparency: 25 }, shadow: shadow(0.08) });
    s.addText(c.title, { x, y: 1.8, w: 2.15, h: 0.45, fontSize: 16, bold: true, color: C.gold, align: "center" });
    s.addText(c.desc, { x: x + 0.15, y: 2.35, w: 1.85, h: 2.4, fontSize: 10.5, color: C.mint, lineSpacingMultiple: 1.3 });
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.2, w: 10, h: 0.425, fill: { color: C.teal, transparency: 70 } });
  s.addText("Day 2：從 AI 助教 升級為 AI 研究團隊 — 8 個專家 Agent 各司其職", {
    x: 0.4, y: 5.2, w: 9.2, h: 0.425, fontSize: 11, color: C.white, valign: "middle", align: "center",
  });
})();

// S66: Quote
quoteSlide(pres,
  "Day 1 完成！\n你已經掌握了\nAI 研究的基礎功",
  "明天，讓這些基礎功升級為完整的研究系統"
);

// S67: Closing
closingSlide(pres,
  "Day 1 完成",
  "AI 研究基礎 — 從概念到文獻",
  "明天見！帶著你的文獻系統來 Day 2"
);

// ═══════════════════════════════════════════════════════════
// OUTPUT
// ═══════════════════════════════════════════════════════════
const path = require("path");
const outFile = path.join(__dirname, "..", "dist", "Day1_Full_AI研究基礎.pptx");
pres.writeFile({ fileName: outFile })
  .then(() => console.log(`Done → ${outFile} (${pres.slides.length} slides)`))
  .catch(console.error);
