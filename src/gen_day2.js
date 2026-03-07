/**
 * AI Paper Workshop — Day 2: AI 研究進階 (L2D1)
 * 31 slides: Cover → S3 Architecture → S4 Writing → S5 Quality → Closing
 * Brand: AI x 論文 (#0B3C5D navy)
 *
 * Run: NODE_PATH=$(npm root -g) node gen_day2.js
 */
const pptxgen = require("pptxgenjs");

// ─── BRAND PALETTE ─────────────────────────────────────────
const C = {
  navy: "0B3C5D", navyLight: "134B6E",
  teal: "0F9D8A", tealLight: "12B89F", tealDark: "0A7A6B",
  gold: "FFC857", goldDark: "E6A820",
  white: "FFFFFF", offwhite: "F5F7FA", lightBlue: "E8F4F2",
  darkText: "1A1A1A", grayText: "5A6B7A", slate: "2C3E50", mint: "D4F0EB",
  green: "0F9D8A", orange: "E07A3A", red: "C0392B", purple: "6C5CE7",
};

const shadow = (o = 0.15) => ({ type: "outer", blur: 6, offset: 3, angle: 135, color: "000000", opacity: o });

// ─── REUSABLE COMPONENTS ───────────────────────────────────
function coverSlide(pres, { tag, title, subtitle, footerLeft, footerRight, badges }) {
  const s = pres.addSlide();
  s.background = { color: C.navy };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.08, fill: { color: C.gold } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0.08, w: 0.12, h: 5.545, fill: { color: C.teal } });
  s.addShape(pres.shapes.OVAL, { x: 7.2, y: -0.5, w: 3.5, h: 3.5, fill: { color: C.teal, transparency: 85 } });
  s.addShape(pres.shapes.OVAL, { x: 7.8, y: 0.5, w: 2.5, h: 2.5, fill: { color: C.gold, transparency: 80 } });
  if (tag) {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 0.7, w: 2.4, h: 0.4, fill: { color: C.teal }, rectRadius: 0.06 });
    s.addText(tag, { x: 0.5, y: 0.7, w: 2.4, h: 0.4, fontSize: 12, bold: true, color: C.white, align: "center", valign: "middle" });
  }
  s.addText(title, { x: 0.5, y: 1.3, w: 7.5, h: 1.8, fontSize: 44, bold: true, color: C.white, lineSpacingMultiple: 1.1 });
  s.addText(subtitle, { x: 0.5, y: 3.2, w: 7.5, h: 0.6, fontSize: 17, color: C.gold });
  if (badges) {
    badges.forEach((b, i) => {
      const bx = 0.5 + i * 1.6;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: bx, y: 4.0, w: 1.4, h: 0.34, fill: { color: b.color }, rectRadius: 0.06 });
      s.addText(b.text, { x: bx, y: 4.0, w: 1.4, h: 0.34, fontSize: 10, bold: true, color: C.white, align: "center", valign: "middle" });
    });
  }
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.2, w: 10, h: 0.425, fill: { color: C.teal, transparency: 60 } });
  if (footerLeft) s.addText(footerLeft, { x: 0.4, y: 5.2, w: 5, h: 0.425, fontSize: 10, color: C.white, valign: "middle" });
  if (footerRight) s.addText(footerRight, { x: 5, y: 5.2, w: 4.6, h: 0.425, fontSize: 10, color: C.white, valign: "middle", align: "right" });
  return s;
}

function sectionDivider(pres, { dayLabel, title, subtitle: sub }) {
  const s = pres.addSlide();
  s.background = { color: C.navy };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.12, h: 5.625, fill: { color: C.teal } });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 0.4, w: 1.6, h: 0.55, fill: { color: C.teal }, rectRadius: 0.08 });
  s.addText(dayLabel, { x: 0.5, y: 0.4, w: 1.6, h: 0.55, fontSize: 14, bold: true, color: C.white, align: "center", valign: "middle" });
  s.addText(title, { x: 0.5, y: 1.2, w: 9, h: 1.5, fontSize: 42, bold: true, color: C.white });
  if (sub) s.addText(sub, { x: 0.5, y: 2.8, w: 9, h: 0.7, fontSize: 18, color: C.teal });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.2, w: 10, h: 0.425, fill: { color: C.teal, transparency: 70 } });
  return s;
}

function contentSlide(pres, title, accent = C.teal) {
  const s = pres.addSlide();
  s.background = { color: C.offwhite };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.72, fill: { color: accent } });
  s.addText(title, { x: 0.4, y: 0, w: 9.2, h: 0.72, fontSize: 22, bold: true, color: C.white, valign: "middle" });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.4, w: 10, h: 0.225, fill: { color: C.navy } });
  return s;
}

function infoCard(s, pres, x, y, w, h, title, body, accent = C.teal) {
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: C.white }, shadow: shadow(0.12) });
  s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.07, h, fill: { color: accent } });
  s.addText(title, { x: x + 0.15, y: y + 0.08, w: w - 0.22, h: 0.32, fontSize: 13, bold: true, color: accent, margin: 0 });
  s.addText(body, { x: x + 0.15, y: y + 0.38, w: w - 0.22, h: h - 0.48, fontSize: 10.5, color: C.darkText, margin: 0, lineSpacingMultiple: 1.2 });
}

function codeBox(s, pres, x, y, w, h, title, code) {
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: C.darkText }, shadow: shadow() });
  if (title) s.addText(title, { x: x + 0.12, y: y + 0.06, w: w - 0.24, h: 0.28, fontSize: 11, bold: true, color: C.gold, margin: 0 });
  const cy = title ? y + 0.34 : y + 0.08;
  const ch = title ? h - 0.42 : h - 0.16;
  s.addText(code, { x: x + 0.12, y: cy, w: w - 0.24, h: ch, fontSize: 9, fontFace: "Consolas", color: C.teal, margin: 0, lineSpacingMultiple: 1.25 });
}

function tipBox(s, x, y, w, text) {
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h: 0.42, fill: { color: C.lightBlue } });
  s.addText(text, { x: x + 0.12, y, w: w - 0.24, h: 0.42, fontSize: 10.5, color: C.navy, valign: "middle" });
}

function processSteps(s, pres, steps, startY = 1.2) {
  const gap = 0.15;
  const sw = (9.5 - (steps.length - 1) * gap) / steps.length;
  steps.forEach((st, i) => {
    const x = 0.25 + i * (sw + gap);
    s.addShape(pres.shapes.RECTANGLE, { x, y: startY, w: sw, h: 2.6, fill: { color: st.color }, shadow: shadow() });
    s.addShape(pres.shapes.OVAL, { x: x + sw / 2 - 0.35, y: startY + 0.12, w: 0.7, h: 0.7, fill: { color: C.white } });
    s.addText(st.n, { x: x + sw / 2 - 0.35, y: startY + 0.12, w: 0.7, h: 0.7, fontSize: 20, bold: true, color: st.color, align: "center", valign: "middle" });
    s.addText(st.title, { x: x + 0.06, y: startY + 0.95, w: sw - 0.12, h: 0.42, fontSize: 13, bold: true, color: C.white, align: "center" });
    s.addText(st.desc, { x: x + 0.08, y: startY + 1.4, w: sw - 0.16, h: 1.1, fontSize: 9.5, color: C.mint, align: "center", lineSpacingMultiple: 1.2 });
    if (i < steps.length - 1) {
      s.addText("\u25B6", { x: x + sw + 0.01, y: startY + 1.05, w: 0.14, h: 0.4, fontSize: 11, color: C.grayText, align: "center" });
    }
  });
}

// ═══════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "AI Paper Workshop - Day 2";
pres.author = "Alan Chen";

// ══════════════════════════════════════════════════════════
// Slide 25: Day 2 COVER
// ══════════════════════════════════════════════════════════
coverSlide(pres, {
  tag: "AI Paper Workshop 2026",
  title: "AI 研究進階\n從架構到投稿",
  subtitle: "8 個 AI 專家 Agent 各司其職，走完論文全流程",
  badges: [
    { text: "Day 2  L2D1", color: C.teal },
    { text: "8 Agents", color: C.goldDark },
    { text: "5 Commands", color: C.tealDark },
    { text: "24 Skills", color: C.navyLight },
  ],
  footerLeft: "Smart Manufacturing Research Application",
  footerRight: "cooperation.tw",
});

// ══════════════════════════════════════════════════════════
// Slide 26: 從 AI 助教 到 AI 研究團隊
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, '從「AI 助教」到「AI 研究團隊」', C.navy);
  // Left: Day 1
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 0.9, w: 4.2, h: 2.2, fill: { color: C.white }, shadow: shadow(0.1) });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 0.9, w: 4.2, h: 0.45, fill: { color: C.grayText } });
  s.addText("Day 1：你 + 1 個 AI 助教", { x: 0.3, y: 0.9, w: 4.2, h: 0.45, fontSize: 14, bold: true, color: C.white, align: "center", valign: "middle" });
  s.addText("Claude Chat\n對話式互動\n一對一 Prompt 交流\n手動驗證結果", {
    x: 0.5, y: 1.5, w: 3.8, h: 1.4, fontSize: 12, color: C.darkText, lineSpacingMultiple: 1.4,
  });
  // Arrow
  s.addText("\u27A1", { x: 4.55, y: 1.7, w: 0.5, h: 0.5, fontSize: 24, color: C.gold, align: "center" });
  // Right: Day 2
  s.addShape(pres.shapes.RECTANGLE, { x: 5.2, y: 0.9, w: 4.5, h: 2.2, fill: { color: C.white }, shadow: shadow(0.1) });
  s.addShape(pres.shapes.RECTANGLE, { x: 5.2, y: 0.9, w: 4.5, h: 0.45, fill: { color: C.teal } });
  s.addText("Day 2：你 + 8 個專家 Agent", { x: 5.2, y: 0.9, w: 4.5, h: 0.45, fontSize: 14, bold: true, color: C.white, align: "center", valign: "middle" });
  s.addText("Claude Code + Skills 系統\n自動化工作流程\nAgent 各司其職\nSkill 驅動品質保證", {
    x: 5.4, y: 1.5, w: 4.1, h: 1.4, fontSize: 12, color: C.darkText, lineSpacingMultiple: 1.4,
  });
  // 8 Agent cards
  const agents = [
    { name: "research-\norchestrator", role: "工作流協調", color: C.teal },
    { name: "literature-\nresearcher", role: "文獻分析", color: C.tealDark },
    { name: "paper-\nwriter", role: "論文撰寫", color: C.navy },
    { name: "citation-\nchecker", role: "引用驗證", color: C.navyLight },
    { name: "paper-\nreviewer", role: "論文審查", color: C.goldDark },
    { name: "data-\nvalidator", role: "數據驗證", color: C.tealDark },
    { name: "stats-\nvalidator", role: "統計分析", color: C.navy },
    { name: "submission-\nhelper", role: "投稿準備", color: C.teal },
  ];
  agents.forEach((a, i) => {
    const x = 0.3 + i * 1.2;
    const y = 3.4;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 1.08, h: 1.5, fill: { color: a.color }, rectRadius: 0.06, shadow: shadow(0.08) });
    s.addText(a.name, { x, y: y + 0.08, w: 1.08, h: 0.8, fontSize: 8, bold: true, color: C.white, align: "center", valign: "middle", lineSpacingMultiple: 1.15 });
    s.addText(a.role, { x, y: y + 0.95, w: 1.08, h: 0.4, fontSize: 8.5, color: C.mint, align: "center", valign: "middle" });
  });
})();

// ══════════════════════════════════════════════════════════
// Slide 27: 5 Commands
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "5 Commands：一鍵啟動 AI 工作流");
  const cmds = [
    { cmd: "/review-paper", desc: "論文全面審查\ncitation-checker\n→ data-validator\n→ paper-reviewer\n→ 七維度評分 + P0-P3", color: C.teal },
    { cmd: "/analyze-\nliterature", desc: "文獻分析\nliterature-researcher\n→ Gap 分析\n→ Related Work 建議", color: C.navy },
    { cmd: "/analyze-\nexperiment", desc: "實驗分析\ndata-validator\n→ stats-validator\n→ 統計分析報告", color: C.tealDark },
    { cmd: "/prepare-\nsubmission", desc: "投稿準備\npaper-reviewer\n→ submission-helper\n→ Cover Letter 草稿", color: C.goldDark },
    { cmd: "/respond-\nreviewers", desc: "審稿回覆\nsubmission-helper\n→ rebuttal-matrix\n→ 回覆信草稿", color: C.navyLight },
  ];
  cmds.forEach((c, i) => {
    const x = 0.3 + i * 1.94;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.9, w: 1.8, h: 3.6, fill: { color: C.white }, shadow: shadow(0.1) });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.9, w: 1.8, h: 0.7, fill: { color: c.color } });
    s.addText(c.cmd, { x, y: 0.92, w: 1.8, h: 0.66, fontSize: 11, bold: true, fontFace: "Consolas", color: C.gold, align: "center", valign: "middle", lineSpacingMultiple: 1.1 });
    s.addText(c.desc, { x: x + 0.08, y: 1.7, w: 1.64, h: 2.6, fontSize: 9.5, color: C.darkText, lineSpacingMultiple: 1.3 });
  });
  tipBox(s, 0.3, 4.7, 9.4, "一行指令，多個 Agent 協作 — 例如 /review-paper 自動調用 3 個 Agent 完成完整審查");
})();

// ══════════════════════════════════════════════════════════
// Slide 28: CLAUDE.md — AI 的工作手冊
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "CLAUDE.md：AI 的工作手冊");
  // Concept
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 0.9, w: 9.4, h: 0.5, fill: { color: C.lightBlue } });
  s.addText("概念：SOP 文件，讓 AI 嚴格遵守你的規則 — 每個專案一份，定義 AI 的「做事方式」", {
    x: 0.5, y: 0.9, w: 9.0, h: 0.5, fontSize: 11, color: C.navy, valign: "middle",
  });
  // 4 key blocks
  const blocks = [
    { title: "引用處理原則", desc: "最高優先級\n只用 .bib 中的引用\n絕不自行添加\n發現問題指出不修改", color: C.red },
    { title: "檔案操作原則", desc: "不刪除原始數據\n不覆蓋既有檔案\n使用版本號區分\n產出放指定目錄", color: C.orange },
    { title: "驗證原則", desc: "寫入後必須驗證\n不信任工具返回\n提供證據才能說完成\n承認失敗即時修正", color: C.teal },
    { title: "專案結構定義", desc: "01_literature/\n02_research/\n03_manuscripts/\n05_outputs/", color: C.navy },
  ];
  blocks.forEach((b, i) => {
    const x = 0.3 + i * 2.4;
    infoCard(s, pres, x, 1.6, 2.2, 2.3, b.title, b.desc, b.color);
  });
  codeBox(s, pres, 0.3, 4.1, 9.4, 1.1, "CLAUDE.md 核心片段", [
    '# 引用處理原則（最高優先級）',
    '1. **只使用** references.bib 中存在的引用',
    '2. **絕不** 自行推測或添加新引用',
    '3. 修改段落時，**保留** 原有引用不變',
  ].join("\n"));
})();

// ══════════════════════════════════════════════════════════
// Slide 29: 主編分析方法
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "主編分析方法：被忽略的投稿關鍵");
  processSteps(s, pres, [
    { n: "1", title: "Editorial Board", desc: "期刊官網找到\nEIC + Associate\nEditors 名單", color: C.teal },
    { n: "2", title: "Scholar 搜尋", desc: "Google Scholar\n查主編近 5 年\n發表 + h-index", color: C.navy },
    { n: "3", title: "Editorial 分析", desc: "閱讀 Editorial /\nGuest Editorial\n了解偏好方向", color: C.tealDark },
    { n: "4", title: "Topic Clustering", desc: "近 2 年收錄文章\n標題 AI 聚類\n找熱門主題", color: C.goldDark },
    { n: "5", title: "時機判斷", desc: "新主編=更開放\nSpecial Issue\n= 高契合度", color: C.navyLight },
  ], 0.95);
  infoCard(s, pres, 0.3, 3.9, 4.5, 1.2, "為什麼主編分析很重要？", "主編任期 3 年，直接影響收錄方向\n- 決定 desk-reject 還是送審\n- 影響審稿人選擇\n- 主編偏好 = 期刊近期趨勢", C.teal);
  infoCard(s, pres, 5.1, 3.9, 4.6, 1.2, "journal-fit Skill 支援", "自動分析期刊 Scope + 主編背景\n6 維度加權評分\nDesk-reject 風險評估\n案例：10 期刊 → 選定 SETA", C.navy);
})();

// ══════════════════════════════════════════════════════════
// Slide 30: Session 3 Divider
// ══════════════════════════════════════════════════════════
sectionDivider(pres, {
  dayLabel: "Session 3",
  title: "論文架構設計\n與實驗規劃",
  subtitle: "Phase 4-5 | IMRaD 架構 + QMD/YAML + IDE + 遠端 GPU",
});

// ══════════════════════════════════════════════════════════
// Slide 31: IMRaD 標準論文架構
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "IMRaD 標準論文架構");
  const sections = [
    { letter: "I", name: "Introduction", desc: "背景 → 問題 → 目的\n→ 貢獻聲明\n（漏斗式結構）", color: C.teal },
    { letter: "M", name: "Methods", desc: "問題定義 → 系統架構\n→ 演算法 → 物理約束\n（可重現）", color: C.navy },
    { letter: "R", name: "Results", desc: "設置 → 主結果\n→ Ablation → 統計\n→ 錯誤分析", color: C.tealDark },
    { letter: "aD", name: "Discussion", desc: "分析 → 邊界\n→ 限制 → 未來方向\n（誠實坦承）", color: C.goldDark },
  ];
  sections.forEach((sec, i) => {
    const x = 0.3 + i * 2.4;
    // Letter circle
    s.addShape(pres.shapes.OVAL, { x: x + 0.6, y: 0.95, w: 0.9, h: 0.9, fill: { color: sec.color } });
    s.addText(sec.letter, { x: x + 0.6, y: 0.95, w: 0.9, h: 0.9, fontSize: 28, bold: true, color: C.white, align: "center", valign: "middle" });
    s.addText(sec.name, { x, y: 1.95, w: 2.2, h: 0.35, fontSize: 14, bold: true, color: sec.color, align: "center" });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.35, w: 2.2, h: 1.5, fill: { color: C.white }, shadow: shadow(0.1) });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.35, w: 2.2, h: 0.06, fill: { color: sec.color } });
    s.addText(sec.desc, { x: x + 0.1, y: 2.5, w: 2.0, h: 1.2, fontSize: 10.5, color: C.darkText, lineSpacingMultiple: 1.25 });
  });
  // Evidence tracking
  infoCard(s, pres, 0.3, 4.1, 4.5, 1.0, "evidence-indexer Skill", "追溯鏈：Claim → Table/Figure → 數據源\n確保每個聲明都有實驗證據支撐", C.teal);
  infoCard(s, pres, 5.1, 4.1, 4.6, 1.0, "案例：NILM 論文配置", "5 張圖 + 11 張表\n圖：框架圖、F1 對比、Heatmap、收斂、案例\n表：數據集、結果、ablation、統計", C.navy);
})();

// ══════════════════════════════════════════════════════════
// Slide 32: MD → QMD 轉換
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "從 Markdown 到 QMD：無痛轉換");
  // Left: Markdown
  codeBox(s, pres, 0.3, 0.9, 4.3, 2.2, "Markdown 初稿 (.md)", [
    '# Introduction',
    '',
    'Non-intrusive load monitoring',
    '(NILM) is a critical technique...',
    '',
    '## Related Work',
    '',
    'Kelly & Knottenbelt (2015)',
    'proposed neural NILM...',
  ].join("\n"));
  // Arrow
  s.addText("+  YAML\n\u27A1", { x: 4.65, y: 1.7, w: 0.5, h: 0.6, fontSize: 14, bold: true, color: C.gold, align: "center" });
  // Right: QMD
  codeBox(s, pres, 5.2, 0.9, 4.5, 2.2, "Quarto 文件 (.qmd)", [
    '---',
    'title: "Training-Free NILM"',
    'bibliography: references.bib',
    'format: elsevier-pdf',
    '---',
    '',
    '# Introduction',
    'Non-intrusive load monitoring',
    '(NILM) is a critical ...',
    '[@kelly2015; @chen2026nilm]',
  ].join("\n"));
  // Comparison
  infoCard(s, pres, 0.3, 3.35, 4.3, 1.1, "轉換成本：5 分鐘", "1. 在頂部加 YAML 檔頭\n2. 引用改成 @citekey 格式\n3. 圖表加上 {#fig-label}\n4. 完成！quarto render → PDF", C.teal);
  infoCard(s, pres, 5.2, 3.35, 4.5, 1.1, "效果差異", "Markdown → 純文字（無法排版）\nQMD → 期刊格式 PDF + TeX\n同一份原始碼，多種輸出格式\n5 秒內得到完整排版論文", C.goldDark);
  tipBox(s, 0.3, 4.65, 9.4, "為什麼先 MD 再 QMD？— MD 寫作門檻低（人人會）→ 加 YAML 即為 QMD → quarto render → PDF");
})();

// ══════════════════════════════════════════════════════════
// Slide 33: YAML 檔頭詳解
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "YAML 檔頭詳解：期刊格式的靈魂");
  // Full YAML example
  codeBox(s, pres, 0.3, 0.9, 5.0, 3.4, "SETA / Elsevier 完整 YAML 配置", [
    'title: "Training-Free Industrial NILM"',
    'author:',
    '  - name: Chung-Kuang Chen',
    '    affiliations:',
    '      - name: NTUST',
    '        department: GIMT',
    'abstract: |',
    '  This paper proposes a training-free',
    '  industrial NILM framework...',
    'bibliography: references.bib',
    'csl: elsevier-vancouver-author-date.csl',
    'format:',
    '  elsevier-pdf:',
    '    keep-tex: true',
    '    journal:',
    '      name: "Sustainable Energy..."',
    '      cite-style: authoryear',
    '    classoption:',
    '      [authoryear, preprint, 12pt]',
    '    geometry: [margin=3cm, a4paper]',
  ].join("\n"));
  // Journal comparison table
  const journals = [
    ["期刊", "format", "classoption", "CSL"],
    ["Elsevier", "elsevier-pdf", "authoryear, preprint", "elsevier-vancouver"],
    ["IEEE", "ieee-pdf", "journal", "ieee.csl"],
    ["Springer", "springer-pdf", "—", "springer-basic"],
    ["MDPI", "mdpi-pdf", "—", "mdpi.csl"],
  ];
  // Manual table
  const tY = 0.9;
  journals.forEach((row, ri) => {
    const y = tY + ri * 0.42;
    row.forEach((cell, ci) => {
      const colX = [5.6, 6.8, 7.8, 8.8];
      const colW = [1.2, 1.0, 1.0, 1.1];
      const bg = ri === 0 ? C.navy : ri % 2 === 0 ? C.lightBlue : C.white;
      const fc = ri === 0 ? C.white : C.darkText;
      s.addShape(pres.shapes.RECTANGLE, { x: colX[ci], y, w: colW[ci], h: 0.38, fill: { color: bg } });
      s.addText(cell, { x: colX[ci], y, w: colW[ci], h: 0.38, fontSize: 8.5, bold: ri === 0, color: fc, align: "center", valign: "middle" });
    });
  });
  // Render command
  codeBox(s, pres, 5.6, 3.1, 4.1, 0.65, null, 'quarto render paper.qmd\n# → paper.pdf + paper.tex (keep-tex)');
  tipBox(s, 0.3, 4.55, 9.4, "轉投策略：只改 YAML format + CSL → quarto render → 立刻得到新期刊格式的 PDF");
})();

// ══════════════════════════════════════════════════════════
// Slide 34: AI 輔助實驗設計
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "AI 輔助實驗設計 + 三層執行環境");
  // 6 design elements
  const elems = [
    { title: "研究假設", desc: "清晰可驗證的\nNull/Alt hypothesis", color: C.teal },
    { title: "變數設計", desc: "獨立/依變/控制\n變數明確定義", color: C.navy },
    { title: "數據方案", desc: "數據集選擇\n分割策略 (train/test)", color: C.tealDark },
    { title: "評估指標", desc: "F1/Accuracy/MCC\n統計顯著性", color: C.goldDark },
    { title: "Ablation", desc: "逐一移除模組\n驗證每部分貢獻", color: C.navyLight },
    { title: "可重現性", desc: "seed=42\n參數配置文件化", color: C.teal },
  ];
  elems.forEach((e, i) => {
    const x = 0.3 + i * 1.58;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 0.9, w: 1.45, h: 1.4, fill: { color: e.color }, rectRadius: 0.06, shadow: shadow(0.08) });
    s.addText(e.title, { x, y: 0.95, w: 1.45, h: 0.35, fontSize: 11, bold: true, color: C.gold, align: "center" });
    s.addText(e.desc, { x: x + 0.06, y: 1.32, w: 1.33, h: 0.85, fontSize: 9, color: C.white, align: "center", lineSpacingMultiple: 1.2 });
  });
  // 3 environments
  const envs = [
    ["環境", "GPU", "用途", "費用"],
    ["本地 MacBook", "無", "開發/調試", "免費"],
    ["Google Colab", "T4/A100", "原型驗證", "免費~$10/月"],
    ["遠端 3090", "RTX 3090", "完整實驗", "電費"],
  ];
  envs.forEach((row, ri) => {
    const y = 2.6 + ri * 0.4;
    row.forEach((cell, ci) => {
      const colX = [0.3, 2.4, 4.5, 7.0];
      const colW = [2.1, 2.1, 2.5, 2.7];
      const bg = ri === 0 ? C.navy : ri % 2 === 0 ? C.lightBlue : C.white;
      const fc = ri === 0 ? C.white : C.darkText;
      s.addShape(pres.shapes.RECTANGLE, { x: colX[ci], y, w: colW[ci], h: 0.36, fill: { color: bg } });
      s.addText(cell, { x: colX[ci], y, w: colW[ci], h: 0.36, fontSize: 10, bold: ri === 0, color: fc, align: "center", valign: "middle" });
    });
  });
  // Skills
  tipBox(s, 0.3, 4.25, 9.4, "experiment-tracker + protocol-enforcer + ablation-min-proof — 三個 Skill 覆蓋實驗全流程");
  // IDE note
  s.addText("VS Code 配置：Python + Jupyter + Quarto + Remote-SSH + Claude Code CLI", {
    x: 0.3, y: 4.85, w: 9.4, h: 0.35, fontSize: 10, color: C.grayText, align: "center",
  });
})();

// ══════════════════════════════════════════════════════════
// Slide 35: Colab + 遠端 3090 實戰
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "Colab + 遠端 3090 實戰");
  // Left: Colab
  codeBox(s, pres, 0.3, 0.9, 4.5, 2.0, "Google Colab 快速上手", [
    '# 1. 掛載 Google Drive',
    'from google.colab import drive',
    'drive.mount("/content/drive")',
    '',
    '# 2. 安裝套件',
    '!pip install torch transformers',
    '',
    '# 3. 載入數據',
    'df = pd.read_csv("/content/drive/",',
    '                  "MyDrive/data/exp.csv")',
  ].join("\n"));
  // Right: 3090
  codeBox(s, pres, 5.2, 0.9, 4.5, 2.0, "遠端 3090 標準流程", [
    '# 1. SSH 連線',
    'ssh ac-3090',
    '',
    '# 2. 初始化環境',
    'source ~/miniconda3/etc/profile.d/',
    '       conda.sh',
    'conda activate gpu',
    '',
    '# 3. 持久化執行 + 無緩衝輸出',
    'PYTHONUNBUFFERED=1 nohup python \\',
    '  -u train.py > exp.log 2>&1 &',
  ].join("\n"));
  // GPU verification
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 3.1, w: 9.4, h: 0.6, fill: { color: "FEF2F2" } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 3.1, w: 0.08, h: 0.6, fill: { color: C.red } });
  s.addText("1 分鐘內必須確認：nvidia-smi → GPU 使用率 > 60%，記憶體 > 1GB — 否則立即停止檢查", {
    x: 0.55, y: 3.1, w: 9.0, h: 0.6, fontSize: 11, bold: true, color: C.red, valign: "middle",
  });
  // GPU troubleshooting
  const issues = [
    ["GPU < 10%", "模型在 CPU", "檢查 .to(device)"],
    ["GPU 20-40%", "DataLoader 瓶頸", "增加 num_workers"],
    ["GPU 40-60%", "Batch 太小", "增大 batch_size"],
  ];
  issues.forEach((row, i) => {
    const y = 3.9 + i * 0.38;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y, w: 3.0, h: 0.34, fill: { color: i % 2 === 0 ? C.white : C.lightBlue } });
    s.addText(row[0], { x: 0.4, y, w: 0.9, h: 0.34, fontSize: 10, bold: true, color: C.red, valign: "middle" });
    s.addText(row[1], { x: 1.4, y, w: 1.0, h: 0.34, fontSize: 10, color: C.darkText, valign: "middle" });
    s.addText(row[2], { x: 2.5, y, w: 0.8, h: 0.34, fontSize: 10, color: C.teal, valign: "middle" });
  });
  infoCard(s, pres, 3.5, 3.85, 6.2, 1.3, "gpu-monitor Skill", "觸發詞：「GPU 監控」「遠端執行」\n- 自動檢查 GPU 狀態\n- 處理遠端 Conda 環境配置\n- 確保 CUDA 正確掛載\n- 異常自動通知", C.teal);
})();

// ══════════════════════════════════════════════════════════
// Slide 36: Telegram Bot 實驗監控
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "Telegram Bot 實驗監控：三層系統");
  // 3 layers
  const layers = [
    { title: "Level 1 即時", time: "前 5 分鐘", items: "1 分鐘：檢查 GPU 使用率\n5 分鐘：檢查日誌輸出\n確認實驗正常啟動", color: C.teal },
    { title: "Level 2 定期", time: "每 15 分鐘", items: "檢查進程是否存在\n檢查 GPU 使用率\n檢查日誌更新時間", color: C.navy },
    { title: "Level 3 異常", time: "即時觸發", items: "進程消失 → 立即通知\n日誌 10min 未更新 → 警告\n錯誤訊息 → 即時通知", color: C.red },
  ];
  layers.forEach((l, i) => {
    const x = 0.3 + i * 3.2;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.9, w: 3.0, h: 2.8, fill: { color: C.white }, shadow: shadow(0.1) });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.9, w: 3.0, h: 0.55, fill: { color: l.color } });
    s.addText(l.title, { x, y: 0.9, w: 2.0, h: 0.55, fontSize: 14, bold: true, color: C.white, valign: "middle", margin: [0, 0, 0, 10] });
    s.addText(l.time, { x: x + 1.6, y: 0.9, w: 1.3, h: 0.55, fontSize: 10, color: C.gold, valign: "middle", align: "right", margin: [0, 10, 0, 0] });
    s.addText(l.items, { x: x + 0.15, y: 1.6, w: 2.7, h: 1.8, fontSize: 10.5, color: C.darkText, lineSpacingMultiple: 1.35 });
  });
  // TG commands
  infoCard(s, pres, 0.3, 4.0, 4.5, 1.1, "Telegram Bot 指令", "/check  → GPU + CPU + 記憶體\n/all    → 完整效能報告 (含溫度)\n/log    → 最近 50 行實驗日誌", C.teal);
  infoCard(s, pres, 5.1, 4.0, 4.6, 1.1, "自動通知範例", "實驗 OOM → 手機收到：\n「GPU 記憶體不足！建議：\n減小 batch_size 或啟用 gradient checkpointing」", C.goldDark);
})();

// ══════════════════════════════════════════════════════════
// Slide 37: 數據彙整 + 可重現性
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "數據彙整策略 + 可重現性設計");
  // Left: Reproducibility
  infoCard(s, pres, 0.3, 0.9, 4.5, 2.2, "可重現性 4 要素", [
    "1. 隨機種子固定：seed=42",
    "   所有隨機操作用同一 seed",
    "",
    "2. 參數配置文件化：config.yaml",
    "   lr, batch_size, epochs 全記錄",
    "",
    "3. 結果 JSON 可序列化",
    "   NumpyEncoder 處理 numpy 型別",
    "",
    "4. metric-audit Skill",
    "   確保指標定義跨實驗一致",
  ].join("\n"), C.teal);
  // Right: Data flow
  infoCard(s, pres, 5.1, 0.9, 4.6, 2.2, "結果 → 論文的數字流", [
    "實驗執行",
    "  ↓",
    "results/*.json ← 原始數據",
    "  ↓",
    "EXPERIMENT_RESULTS.md ← 唯一真相",
    "  ↓",
    "paper.qmd ← 手動提取",
    "  ↓",
    "grep '(舊數字)' → 驗證一致性",
  ].join("\n"), C.navy);
  // Triangle verification
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 3.35, w: 9.4, h: 0.06, fill: { color: C.teal } });
  const tri = ["Text", "Table", "Figure"];
  tri.forEach((t, i) => {
    const x = 1.5 + i * 3.0;
    s.addShape(pres.shapes.OVAL, { x, y: 3.6, w: 1.5, h: 0.6, fill: { color: [C.teal, C.navy, C.goldDark][i] } });
    s.addText(t, { x, y: 3.6, w: 1.5, h: 0.6, fontSize: 14, bold: true, color: C.white, align: "center", valign: "middle" });
    if (i < 2) s.addText("\u2194", { x: x + 1.5, y: 3.6, w: 1.5, h: 0.6, fontSize: 18, color: C.grayText, align: "center", valign: "middle" });
  });
  s.addText("數據一致性三角驗證：Text \u2194 Table \u2194 Figure — figure-table-checker + evidence-indexer Skill 自動掃描", {
    x: 0.3, y: 4.35, w: 9.4, h: 0.4, fontSize: 10.5, color: C.darkText, align: "center",
  });
  tipBox(s, 0.3, 4.85, 9.4, "案例：發現 F1=0.820 (文字) vs 0.8488 (表格) 不一致 → P0 問題 → 修正前不能投稿");
})();

// ══════════════════════════════════════════════════════════
// Slide 38: Session 4 Divider
// ══════════════════════════════════════════════════════════
sectionDivider(pres, {
  dayLabel: "Session 4",
  title: "QMD + BibTeX\n論文撰寫系統",
  subtitle: "Phase 8 | 論文撰寫 + 轉投策略 + SVG 向量圖 + 統計驗證",
});

// ══════════════════════════════════════════════════════════
// Slide 39: BibTeX 引用管理 (進階)
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "BibTeX 引用管理 (進階)");
  // DOI → BibTeX flow
  processSteps(s, pres, [
    { n: "1", title: "DOI 輸入", desc: "已驗證的 DOI\n來自 Day 1\nCrossRef 確認", color: C.teal },
    { n: "2", title: "BibTeX 生成", desc: "CrossRef API\n自動產出格式化\nBibTeX 條目", color: C.navy },
    { n: "3", title: "品質檢查", desc: "bib-manager Skill\n重複偵測 + 格式\n+ 幽靈引用", color: C.tealDark },
    { n: "4", title: "論文引用", desc: "@citekey 格式\nquarto render\n自動排版", color: C.goldDark },
  ], 0.95);
  // Dual check
  infoCard(s, pres, 0.3, 3.85, 4.5, 1.3, "bib-manager + citation-checker", "雙重防呆：\n- bib-manager：格式 + 重複 + 一致性\n- citation-checker：引用存在 + 準確 + 完整\n三層驗證：存在性 → 準確性 → 完整性", C.teal);
  infoCard(s, pres, 5.1, 3.85, 4.6, 1.3, "引用格式速查", "單引用：@chen2026nilm\n多引用：[@chen2026nilm; @kelly2015]\n行內：@chen2026nilm 提出了...\n括號：根據 [@kelly2015] 的結果\nCSL 切換：改 .csl 檔即可換格式", C.navy);
})();

// ══════════════════════════════════════════════════════════
// Slide 40: AI 輔助學術寫作
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "AI 輔助學術寫作：各章節策略");
  const chapters = [
    { ch: "Introduction", strategy: "倒金字塔結構\n廣→窄→本文\n最後一段 = 貢獻聲明\n\"The main contributions...\"", color: C.teal },
    { ch: "Related Work", strategy: "從 Obsidian 文獻矩陣\n→ 主題分組段落\n每段結尾指出 Gap\n→ 銜接本文方法", color: C.navy },
    { ch: "Methodology", strategy: "圖表先行策略：\n先畫框架圖\nAI 根據圖寫文字\n公式 + 偽代碼", color: C.tealDark },
    { ch: "Results", strategy: "數據表 → AI 統計分析\n→ 自動產出段落\n\"Table X shows that...\"\n含 effect size", color: C.goldDark },
    { ch: "Discussion", strategy: "限制性坦承：\n\"While effective, our\napproach has limitations\"\n+ 未來展望", color: C.navyLight },
  ];
  chapters.forEach((c, i) => {
    const x = 0.3 + i * 1.94;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.9, w: 1.8, h: 3.3, fill: { color: C.white }, shadow: shadow(0.1) });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.9, w: 1.8, h: 0.55, fill: { color: c.color } });
    s.addText(c.ch, { x, y: 0.9, w: 1.8, h: 0.55, fontSize: 12, bold: true, color: C.white, align: "center", valign: "middle" });
    s.addText(c.strategy, { x: x + 0.08, y: 1.55, w: 1.64, h: 2.5, fontSize: 9.5, color: C.darkText, lineSpacingMultiple: 1.3 });
  });
  tipBox(s, 0.3, 4.45, 9.4, "paper-writer Agent + academic-writing Skill — AI 撰寫初稿，人工修改潤色，確保學術風格");
})();

// ══════════════════════════════════════════════════════════
// Slide 41: 轉投策略
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "轉投策略：切中熱點與主編偏好");
  processSteps(s, pres, [
    { n: "1", title: "Topic 分析", desc: "抓取目標期刊\n近 100 篇標題\nAI topic clustering", color: C.teal },
    { n: "2", title: "主編偏好", desc: "Google Scholar\n+ Editorial 分析\n研究方向對齊", color: C.navy },
    { n: "3", title: "調整 Title", desc: "對齊期刊\n熱門關鍵詞\n提高匹配度", color: C.tealDark },
    { n: "4", title: "調整內容", desc: "Abstract + Intro\n引用該期刊\n近期文章", color: C.goldDark },
    { n: "5", title: "格式轉換", desc: "改 YAML + CSL\nquarto render\n→ 新格式 PDF", color: C.navyLight },
  ], 0.95);
  // Case study
  infoCard(s, pres, 0.3, 3.85, 9.4, 1.3, "案例：Energy & Buildings → SETA 的轉投策略", [
    "Step 1: SETA 近 100 篇標題分析 → 「sustainable」「assessment」「renewable」高頻",
    "Step 2: 主編 Prof. X 研究方向 → 能源系統評估、永續技術",
    "Step 3: 原 Title 加入 \"sustainable\" + \"assessment\" 關鍵詞",
    "Step 4: Introduction 第一段引用 SETA 近期 3 篇文章 → 展示 relevance",
    "Step 5: YAML format 從 energy-buildings → elsevier-pdf + SETA 配置 → 5 秒切換完成",
  ].join("\n"), C.teal);
})();

// ══════════════════════════════════════════════════════════
// Slide 42: SVG + QMD→TeX
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "SVG 向量圖 + QMD → TeX 快速轉換");
  // Left: SVG
  infoCard(s, pres, 0.3, 0.9, 4.5, 1.6, "為什麼用 SVG？", "1. 無限放大不失真（期刊要求 300+ DPI）\n2. 可用 Inkscape 後編輯文字/顏色\n3. 體積小（比 PNG 小 5-10 倍）\n4. 主流期刊都接受 SVG/PDF 格式", C.teal);
  codeBox(s, pres, 0.3, 2.7, 4.5, 1.6, "Python 三格式輸出", [
    'import matplotlib.pyplot as plt',
    '',
    '# 同時輸出 3 種格式',
    "fig.savefig('fig.svg', format='svg',",
    "            bbox_inches='tight')",
    "fig.savefig('fig.pdf', format='pdf',",
    "            bbox_inches='tight')",
    "fig.savefig('fig.png', format='png',",
    "            dpi=300, bbox_inches='tight')",
  ].join("\n"));
  // Right: QMD→TeX
  infoCard(s, pres, 5.1, 0.9, 4.6, 1.6, "QMD → TeX 快速轉換", "quarto render paper.qmd --keep-tex\n→ 同時得到 .pdf + .tex\n\n.tex 可直接：\n- 提交 Overleaf 共同編輯\n- 上傳期刊投稿系統\n- 5 秒內完成格式轉換", C.goldDark);
  codeBox(s, pres, 5.1, 2.7, 4.6, 1.6, "QMD 圖片引用語法", [
    '# 基本引用',
    '![Framework](fig.pdf){#fig-framework',
    '  width="100%"}',
    '',
    '# 文中引用',
    'As shown in @fig-framework, our',
    'proposed method consists of...',
    '',
    '# Inkscape 後處理',
    '# SVG → PDF/EPS (特殊期刊要求)',
  ].join("\n"));
  tipBox(s, 0.3, 4.55, 9.4, "完整圖表工作流：Python 生成 SVG → Inkscape 微調 → QMD 引用 → quarto render → 期刊格式 PDF");
})();

// ══════════════════════════════════════════════════════════
// Slide 43: Skill 驅動統計驗證
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "Skill 驅動的自動化統計驗證");
  // Flow
  const flow = [
    { label: "/analyze-\nexperiment", color: C.teal },
    { label: "data-\nvalidator", color: C.navy },
    { label: "stats-\nvalidator", color: C.tealDark },
    { label: "statistical-\nvalidation", color: C.goldDark },
    { label: "論文用\n文本輸出", color: C.navyLight },
  ];
  flow.forEach((f, i) => {
    const x = 0.3 + i * 1.95;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 0.9, w: 1.8, h: 0.7, fill: { color: f.color }, rectRadius: 0.08, shadow: shadow(0.08) });
    s.addText(f.label, { x, y: 0.9, w: 1.8, h: 0.7, fontSize: 10.5, bold: true, color: C.white, align: "center", valign: "middle", lineSpacingMultiple: 1.1 });
    if (i < flow.length - 1) s.addText("\u25B8", { x: x + 1.8, y: 0.9, w: 0.15, h: 0.7, fontSize: 12, color: C.grayText, align: "center", valign: "middle" });
  });
  // Details
  infoCard(s, pres, 0.3, 1.85, 4.5, 1.7, "data-validator 品質檢查", [
    "- 數據完整性 (missing values)",
    "- 過擬合風險 (train/test gap)",
    "- 分佈一致性 (KS test)",
    "- split-leakage-audit Skill：",
    "  時間/實體洩漏檢測",
    "",
    "P0-P3 問題分級自動標記",
  ].join("\n"), C.teal);
  infoCard(s, pres, 5.1, 1.85, 4.6, 1.7, "stats-validator 統計分析", [
    "- Bootstrap 信賴區間 (95% CI)",
    "- 效果量 (Cohen's d)",
    "- 功效分析 (Power > 0.8)",
    "- 方法選擇：",
    "  t-test / Mann-Whitney /",
    "  Wilcoxon / McNemar",
    "- 論文用文本自動生成",
  ].join("\n"), C.navy);
  // Case
  tipBox(s, 0.3, 3.8, 9.4, "案例：/analyze-experiment results.json → 發現 F1 差異 p=0.003 (顯著) + Cohen's d=1.2 (大效果量)");
  // P0-P3
  const levels = [
    { label: "P0 致命", desc: "數據不一致、統計錯誤", color: C.red },
    { label: "P1 嚴重", desc: "方法論漏洞", color: C.orange },
    { label: "P2 重要", desc: "寫作/引用問題", color: C.goldDark },
    { label: "P3 次要", desc: "格式/風格建議", color: C.grayText },
  ];
  levels.forEach((l, i) => {
    const x = 0.3 + i * 2.4;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 4.45, w: 2.2, h: 0.55, fill: { color: l.color, transparency: 20 }, rectRadius: 0.06 });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 4.45, w: 0.06, h: 0.55, fill: { color: l.color } });
    s.addText(l.label, { x: x + 0.12, y: 4.45, w: 0.8, h: 0.55, fontSize: 10, bold: true, color: l.color, valign: "middle" });
    s.addText(l.desc, { x: x + 0.95, y: 4.45, w: 1.15, h: 0.55, fontSize: 9, color: C.darkText, valign: "middle" });
  });
})();

// ══════════════════════════════════════════════════════════
// Slide 44: Claude Code 深度體驗
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "Claude Code 深度體驗 + Skill 自動化");
  // Skills trigger
  infoCard(s, pres, 0.3, 0.9, 4.5, 1.4, "Skills 觸發機制", '說「統計」→ statistical-validation\n說「引用」→ bib-manager\n說「投稿」→ journal-submission\n說「審查」→ paper-review-skill\n24 個 Skill 語義自動匹配', C.teal);
  infoCard(s, pres, 5.1, 0.9, 4.6, 1.4, "Agents 分工", "唯讀：citation-checker, paper-reviewer\n→ 安全不改檔\n讀寫：paper-writer, submission-helper\n→ 可編輯論文\n執行：data-validator, stats-validator\n→ 可跑腳本驗證", C.navy);
  // 3 Demos
  codeBox(s, pres, 0.3, 2.5, 3.0, 2.0, "Demo 1: 論文審查", [
    '/review-paper paper.qmd "SETA"',
    '',
    '→ citation-checker (引用)',
    '→ data-validator (數據)',
    '→ paper-reviewer (審查)',
    '',
    '輸出：七維度評分',
    '     + P0-P3 問題清單',
  ].join("\n"));
  codeBox(s, pres, 3.5, 2.5, 3.0, 2.0, "Demo 2: 實驗分析", [
    '/analyze-experiment results.json',
    '',
    '→ data-validator (品質)',
    '→ stats-validator (統計)',
    '',
    '輸出：Bootstrap CI',
    '     + 效果量',
    '     + 論文用文本',
  ].join("\n"));
  codeBox(s, pres, 6.7, 2.5, 3.0, 2.0, "Demo 3: 投稿準備", [
    '/prepare-submission "SETA"',
    '',
    '→ paper-reviewer (最終審)',
    '→ submission-helper (準備)',
    '',
    '輸出：Cover Letter 草稿',
    '     + 10 項素材清單',
    '     + Reviewer 建議',
  ].join("\n"));
  tipBox(s, 0.3, 4.7, 9.4, "結業帶走：research-workspace.zip — 包含完整 24 Skills + 8 Agents + 5 Commands + CLAUDE.md 範本");
})();

// ══════════════════════════════════════════════════════════
// Slide 45: Session 5 Divider
// ══════════════════════════════════════════════════════════
sectionDivider(pres, {
  dayLabel: "Session 5",
  title: "多維度品質保證\n與投稿策略",
  subtitle: "Phase 9-11 | 七維度評分 + 平行審查 + Cover Letter + 投稿",
});

// ══════════════════════════════════════════════════════════
// Slide 46: 七維度論文分析框架
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "七維度論文分析框架");
  const dims = [
    { name: "結構\n完整性", color: C.teal },
    { name: "方法論\n嚴謹性", color: C.navy },
    { name: "實驗\n設計", color: C.tealDark },
    { name: "數據\n可信度", color: C.goldDark },
    { name: "寫作\n清晰度", color: C.navyLight },
    { name: "引用\n完整性", color: C.teal },
    { name: "創新\n貢獻", color: C.goldDark },
  ];
  dims.forEach((d, i) => {
    const x = 0.3 + i * 1.37;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 0.9, w: 1.25, h: 1.8, fill: { color: d.color }, rectRadius: 0.06, shadow: shadow(0.08) });
    // Score circle
    s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: 1.0, w: 0.75, h: 0.75, fill: { color: C.white, transparency: 20 } });
    s.addText(String(Math.floor(70 + Math.random() * 25)), { x: x + 0.25, y: 1.0, w: 0.75, h: 0.75, fontSize: 18, bold: true, color: C.white, align: "center", valign: "middle" });
    s.addText(d.name, { x, y: 1.85, w: 1.25, h: 0.7, fontSize: 10.5, bold: true, color: C.white, align: "center", valign: "middle", lineSpacingMultiple: 1.15 });
  });
  // P0-P3 system
  infoCard(s, pres, 0.3, 3.0, 4.5, 2.1, "P0-P3 品質管控系統", [
    "P0 致命 — 必修，否則 desk-reject",
    "  例：數據不一致、統計方法錯誤",
    "",
    "P1 嚴重 — 必修，影響審稿結果",
    "  例：方法論漏洞、引用錯誤",
    "",
    "P2 重要 — 建議修改",
    "  例：寫作不清晰、圖表品質",
    "",
    "P3 次要 — 時間允許就改",
    "  例：格式微調、風格建議",
  ].join("\n"), C.teal);
  infoCard(s, pres, 5.1, 3.0, 4.6, 2.1, "mvp-gatekeeper Skill", [
    "「能不能投稿？」一鍵檢查",
    "",
    "8 項通用門檻：",
    "1. 所有 P0 問題已修復？",
    "2. 統計顯著性驗證通過？",
    "3. 圖表數據一致？",
    "4. 引用全部驗證？",
    "5. 格式符合期刊要求？",
    "6-8. ...",
    "",
    "案例：2P0 + 3P1 → 修復後通過",
  ].join("\n"), C.navy);
})();

// ══════════════════════════════════════════════════════════
// Slide 47: 平行審查 Claude × ChatGPT × Gemini
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "平行審查：Claude x ChatGPT x Gemini");
  // 3 AI cards
  const ais = [
    { name: "Claude Code", strength: "系統化 + Skill 生態系", focus: "七維度評分\nP0-P3 分級\n引用驗證\n數據一致性", tool: "paper-review-skill\ncitation-checker\nfigure-table-checker", color: C.teal },
    { name: "ChatGPT (GPT-4o)", strength: "結構/寫作流暢度", focus: "段落邏輯\n語法修正\n可讀性\n論述連貫", tool: "Custom GPT\n或 Prompt 模板", color: C.navy },
    { name: "Gemini (2.5 Pro)", strength: "事實查核/長文檢索", focus: "引用事實核對\n數據聲明驗證\n最新文獻覆蓋", tool: "NotebookLM\nDeep Research", color: C.goldDark },
  ];
  ais.forEach((a, i) => {
    const x = 0.3 + i * 3.2;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.9, w: 3.0, h: 3.0, fill: { color: C.white }, shadow: shadow(0.1) });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.9, w: 3.0, h: 0.5, fill: { color: a.color } });
    s.addText(a.name, { x, y: 0.9, w: 3.0, h: 0.5, fontSize: 13, bold: true, color: C.white, align: "center", valign: "middle" });
    s.addText("強項：" + a.strength, { x: x + 0.1, y: 1.5, w: 2.8, h: 0.3, fontSize: 10, bold: true, color: a.color });
    s.addText("審查重點：\n" + a.focus, { x: x + 0.1, y: 1.85, w: 2.8, h: 1.1, fontSize: 10, color: C.darkText, lineSpacingMultiple: 1.2 });
    s.addText("工具：\n" + a.tool, { x: x + 0.1, y: 3.0, w: 2.8, h: 0.7, fontSize: 9, color: C.grayText, lineSpacingMultiple: 1.15 });
  });
  // Integration step
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 4.1, w: 9.4, h: 0.5, fill: { color: C.lightBlue } });
  s.addText("Step 4 整合（人工）：三份報告合併 → 去重 → 按 P0-P3 排序 → 修改優先級 — 三者共識 = 高信度問題", {
    x: 0.5, y: 4.1, w: 9.0, h: 0.5, fontSize: 11, bold: true, color: C.navy, valign: "middle",
  });
  tipBox(s, 0.3, 4.8, 9.4, "案例：Claude 發現數據不一致(P0)、ChatGPT 發現邏輯跳躍(P1)、Gemini 發現引用年份錯(P1)");
})();

// ══════════════════════════════════════════════════════════
// Slide 48: 引用驗證與比對
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "三層引用驗證 + 圖表交叉引用");
  // 3 layers
  const layers = [
    { n: "L1", title: "存在性", desc: "DOI 有效\n作者名正確\n年份正確\n→ CrossRef API", color: C.teal },
    { n: "L2", title: "準確性", desc: "引用主張 vs 原文\n是否正確引述\n避免斷章取義\n→ 人工 + AI", color: C.navy },
    { n: "L3", title: "完整性", desc: "所有 .bib 都被引用\n所有引用都在 .bib\n無幽靈/遺漏引用\n→ bib-manager", color: C.goldDark },
  ];
  layers.forEach((l, i) => {
    const x = 0.3 + i * 3.2;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.9, w: 3.0, h: 2.0, fill: { color: C.white }, shadow: shadow(0.1) });
    s.addShape(pres.shapes.OVAL, { x: x + 1.1, y: 0.95, w: 0.7, h: 0.7, fill: { color: l.color } });
    s.addText(l.n, { x: x + 1.1, y: 0.95, w: 0.7, h: 0.7, fontSize: 16, bold: true, color: C.white, align: "center", valign: "middle" });
    s.addText(l.title, { x, y: 1.7, w: 3.0, h: 0.3, fontSize: 13, bold: true, color: l.color, align: "center" });
    s.addText(l.desc, { x: x + 0.15, y: 2.05, w: 2.7, h: 0.75, fontSize: 10, color: C.darkText, align: "center", lineSpacingMultiple: 1.2 });
  });
  // figure-table-checker
  infoCard(s, pres, 0.3, 3.15, 4.5, 1.5, "figure-table-checker Skill", [
    "自動掃描：",
    "- 圖表編號連續性 (Fig.1, Fig.2...)",
    "- 交叉引用完整性 (每張圖都被引用)",
    "- 數字一致性 (文字 vs 表格 vs 圖)",
    "- 圖片解析度檢查 (≥300 DPI)",
  ].join("\n"), C.teal);
  infoCard(s, pres, 5.1, 3.15, 4.6, 1.5, "evidence-indexer Skill", [
    "證據追溯鏈：",
    "Claim: 'F1 improved by 15%'",
    "  → Table 3, Row 2",
    "  → results/exp_results.json",
    "  → experiment_log_20260115.md",
    "確保每個聲明都有數據支撐",
  ].join("\n"), C.navy);
  tipBox(s, 0.3, 4.85, 9.4, "citation-checker Agent：唯讀權限，安全不改檔，逐筆比對 43 篇引用");
})();

// ══════════════════════════════════════════════════════════
// Slide 49: Reviewer 預測
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "Reviewer 預測與應對策略");
  const qas = [
    { q: "Q1: Why not use more recent transformer-based methods as baselines?", a: "我們的定位是 training-free，與 supervised 方法屬不同範式。但已加入 Transformer baseline 作為參考。", color: C.teal },
    { q: "Q2: The sample size seems limited. How generalizable are the results?", a: "跨 3 個數據集、9 類設備驗證。Bootstrap CI 證明結果穩定性。表 X 展示跨數據集一致性。", color: C.navy },
    { q: "Q3: What are the computational costs compared to traditional methods?", a: "表 Y 已提供推理時間比較。LLM 推理成本約 $0.01/設備，遠低於標註成本 ($5K-50K)。", color: C.tealDark },
    { q: "Q4: How do you handle devices not in the LLM's training data?", a: "Discussion 已坦承此限制。提出 RAG + few-shot 作為未來方向。Supplementary 含完整設備清單。", color: C.goldDark },
  ];
  qas.forEach((qa, i) => {
    const y = 0.9 + i * 1.05;
    // Q
    s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y, w: 5.0, h: 0.85, fill: { color: qa.color, transparency: 10 } });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y, w: 0.06, h: 0.85, fill: { color: qa.color } });
    s.addText(qa.q, { x: 0.5, y, w: 4.7, h: 0.85, fontSize: 9.5, color: C.darkText, valign: "middle", lineSpacingMultiple: 1.15 });
    // A
    s.addShape(pres.shapes.RECTANGLE, { x: 5.5, y, w: 4.2, h: 0.85, fill: { color: C.white }, shadow: shadow(0.06) });
    s.addText(qa.a, { x: 5.65, y, w: 3.9, h: 0.85, fontSize: 9, color: C.darkText, valign: "middle", lineSpacingMultiple: 1.15 });
  });
  tipBox(s, 0.3, 5.1, 9.4, "rebuttal-matrix Skill — 追蹤每個 reviewer comment 的回覆狀態 + 修改位置");
})();

// ══════════════════════════════════════════════════════════
// Slide 50: 投稿全流程
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "投稿全流程：Cover Letter → Rebuttal");
  // Left: Cover Letter
  infoCard(s, pres, 0.3, 0.9, 4.5, 2.2, "Cover Letter 5 段式", [
    "P1: 投稿聲明（期刊名 + 論文標題）",
    "P2: 研究背景 + 問題意義",
    "P3: 核心貢獻（3 點）",
    "P4: 與期刊 Scope 的關聯性",
    "   引用該期刊近期 2-3 篇文章",
    "P5: 作者聲明 + 聯繫方式",
    "",
    "submission-helper Agent 自動生成",
  ].join("\n"), C.teal);
  // Right: 10 items
  infoCard(s, pres, 5.1, 0.9, 4.6, 2.2, "投稿素材 10 項清單", [
    " 1. 論文 PDF（期刊格式）",
    " 2. 論文 .tex 源碼",
    " 3. Cover Letter",
    " 4. 圖表高解析度 (SVG/PDF, 300+ DPI)",
    " 5. Supplementary Material",
    " 6. Author Statement / CRediT",
    " 7. Highlights (3-5 bullets)",
    " 8. Graphical Abstract (800x400px)",
    " 9. Suggested Reviewers (3-5 人)",
    "10. Data Availability Statement",
  ].join("\n"), C.navy);
  // submission-bundle
  infoCard(s, pres, 0.3, 3.35, 9.4, 1.0, "submission-bundle Skill — 一鍵打包 + 完整性檢查", [
    "/prepare-submission \"SETA\" → paper-reviewer (最終審) → submission-helper (打包) → 輸出：Cover Letter + 10 項清單 + Reviewer 建議",
    "自動檢查：所有檔案存在 | 圖表解析度 ≥300 DPI | .bib 引用完整 | YAML 格式正確",
  ].join("\n"), C.teal);
  tipBox(s, 0.3, 4.55, 9.4, "Suggested Reviewers 訣竅：從 references.bib 選 — 引用了誰的論文，誰就熟悉你的領域");
})();

// ══════════════════════════════════════════════════════════
// Slide 51: 期刊選擇與投稿策略
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "期刊選擇與投稿策略");
  // 6 dimensions radar concept
  const dims = [
    { name: "Scope\n契合度", weight: "35%", color: C.teal },
    { name: "Impact\nFactor", weight: "15%", color: C.navy },
    { name: "主編\n偏好", weight: "20%", color: C.goldDark },
    { name: "近期\n收錄", weight: "15%", color: C.tealDark },
    { name: "審稿\n週期", weight: "10%", color: C.navyLight },
    { name: "OA/\nAPC", weight: "5%", color: C.grayText },
  ];
  dims.forEach((d, i) => {
    const x = 0.3 + i * 1.6;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 0.9, w: 1.45, h: 1.3, fill: { color: d.color }, rectRadius: 0.06 });
    s.addText(d.name, { x, y: 0.95, w: 1.45, h: 0.7, fontSize: 11, bold: true, color: C.white, align: "center", valign: "middle", lineSpacingMultiple: 1.1 });
    s.addText(d.weight, { x, y: 1.65, w: 1.45, h: 0.4, fontSize: 16, bold: true, color: C.gold, align: "center" });
  });
  // Case: scoring table
  const scores = [
    ["期刊", "Scope", "IF", "主編", "收錄", "審稿", "加權分"],
    ["Applied Energy", "90", "85", "80", "75", "70", "91"],
    ["IEEE TII", "85", "90", "80", "80", "75", "89"],
    ["SETA (選定)", "95", "70", "85", "90", "80", "87"],
    ["Energy & Buildings", "80", "85", "75", "70", "65", "78"],
  ];
  scores.forEach((row, ri) => {
    const y = 2.5 + ri * 0.38;
    row.forEach((cell, ci) => {
      const colX = [0.3, 2.5, 3.6, 4.7, 5.8, 6.9, 8.2];
      const colW = [2.2, 1.1, 1.1, 1.1, 1.1, 1.3, 1.2];
      const bg = ri === 0 ? C.navy : ri === 3 ? C.lightBlue : C.white;
      const fc = ri === 0 ? C.white : ri === 3 ? C.teal : C.darkText;
      s.addShape(pres.shapes.RECTANGLE, { x: colX[ci], y, w: colW[ci], h: 0.34, fill: { color: bg } });
      s.addText(cell, { x: colX[ci], y, w: colW[ci], h: 0.34, fontSize: ri === 0 ? 9.5 : 10, bold: ri === 0 || ri === 3, color: fc, align: ci === 0 ? "left" : "center", valign: "middle", margin: ci === 0 ? [0, 0, 0, 8] : 0 });
    });
  });
  tipBox(s, 0.3, 4.45, 9.4, "journal-fit Skill：輸入研究主題 → 6 維度加權評分 → 期刊排名 + desk-reject 風險 + 審稿週期預估");
})();

// ══════════════════════════════════════════════════════════
// Slide 52: 實作練習 2
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "Day 2 實作練習 & Checklist");
  infoCard(s, pres, 0.3, 0.9, 4.5, 2.4, "實作任務清單", [
    "[ ] 1. 建立 QMD 論文骨架",
    "     含完整 YAML 檔頭",
    "[ ] 2. 設定 bibliography + csl",
    "[ ] 3. 寫出 Abstract 初稿 (200 字)",
    "[ ] 4. 加入 3 個引用",
    "     quarto render 驗證格式",
    "[ ] 5. (進階) 產出 SVG 圖",
    "     嵌入 QMD",
    "[ ] 6. (進階) 用 /review-paper",
    "     審查自己的論文",
  ].join("\n"), C.teal);
  infoCard(s, pres, 5.1, 0.9, 4.6, 2.4, "今日核心技能 (12 項)", [
    " 1. IMRaD 架構設計",
    " 2. MD → QMD 轉換 + YAML",
    " 3. 期刊格式配置",
    " 4. 遠端 GPU 實驗執行",
    " 5. TG Bot 實驗監控",
    " 6. 可重現性設計 (seed=42)",
    " 7. 數據一致性三角驗證",
    " 8. SVG 向量圖製作",
    " 9. 轉投策略",
    "10. 平行審查 (3 AI)",
    "11. P0-P3 品質管控",
    "12. Cover Letter 撰寫",
  ].join("\n"), C.navy);
  tipBox(s, 0.3, 3.55, 9.4, "實作時間 15 分鐘 — 建立 QMD 骨架 + Abstract + 3 引用 + quarto render 產出 PDF");
  // Deliverables
  infoCard(s, pres, 0.3, 4.15, 9.4, 1.0, "結業帶走", "research-workspace.zip (24 Skills + 8 Agents + 5 Commands) | CLAUDE.md 範本 | QMD 論文模板 (4 種期刊) | references.bib 範例 | 統計分析腳本 | 七維度審查報告範例", C.goldDark);
})();

// ══════════════════════════════════════════════════════════
// Slide 53: 系統部署
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "系統部署：帶走你的 AI 研究團隊");
  processSteps(s, pres, [
    { n: "1", title: "下載安裝", desc: "research-workspace.zip\n解壓到專案目錄\n3 分鐘完成", color: C.teal },
    { n: "2", title: "客製化", desc: "修改 CLAUDE.md\n設定研究主題\n調整引用規則", color: C.navy },
    { n: "3", title: "Skills 擴充", desc: "新增專屬 Skill\n修改觸發詞\n加入新 Agent", color: C.tealDark },
    { n: "4", title: "遠端設定", desc: "TG Bot (可選)\n遠端 GPU 配置\nSSH 自動化", color: C.goldDark },
  ], 0.95);
  // What's included
  infoCard(s, pres, 0.3, 3.85, 4.5, 1.3, "research-workspace.zip 內容", [
    ".claude/skills/    → 24 個 Skills",
    ".claude/agents/    → 8 個 Agents",
    ".claude/commands/  → 5 個 Commands",
    "CLAUDE.md          → 範本 (可客製)",
    "templates/         → QMD + YAML 模板",
    "scripts/           → Python + GAS 腳本",
  ].join("\n"), C.teal);
  infoCard(s, pres, 5.1, 3.85, 4.6, 1.3, "部署後的效果", [
    "你說「審查論文」→ 自動啟動審查流程",
    "你說「分析文獻」→ 自動 Gap 分析",
    "你說「準備投稿」→ 自動生成 Cover Letter",
    "",
    "AI 參與度：70-75%",
    "你負責：決策 + 審核 + 學術判斷",
  ].join("\n"), C.navy);
})();

// ══════════════════════════════════════════════════════════
// Slide 54: 完整工作流回顧
// ══════════════════════════════════════════════════════════
(() => {
  const s = contentSlide(pres, "完整 AI 論文研究工作流程", C.navy);
  // Compact phase overview
  const phases = [
    { n: "P1", label: "概念探索", tool: "Claude Chat", day: "D1" },
    { n: "P2", label: "文獻調研", tool: "CrossRef+API", day: "D1" },
    { n: "P3", label: "研究定位", tool: "journal-fit", day: "D1" },
    { n: "P4", label: "論文架構", tool: "IMRaD+QMD", day: "D2" },
    { n: "P5", label: "實驗設計", tool: "exp-tracker", day: "D2" },
    { n: "P6", label: "實驗執行", tool: "GPU+TGBot", day: "D2" },
    { n: "P7", label: "數據分析", tool: "stats-valid", day: "D2" },
    { n: "P8", label: "論文撰寫", tool: "paper-writer", day: "D2" },
    { n: "P9", label: "品質審查", tool: "3-AI review", day: "D2" },
    { n: "P10", label: "投稿準備", tool: "submission", day: "D2" },
    { n: "P11", label: "審稿回覆", tool: "rebuttal", day: "D2" },
  ];
  const pw = 0.78, gap = 0.07;
  phases.forEach((p, i) => {
    const x = 0.2 + i * (pw + gap);
    const bgC = p.day === "D1" ? C.teal : C.navyLight;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 0.9, w: pw, h: 1.6, fill: { color: bgC }, rectRadius: 0.05 });
    s.addText(p.n, { x, y: 0.92, w: pw, h: 0.3, fontSize: 9, bold: true, color: C.gold, align: "center" });
    s.addText(p.label, { x, y: 1.2, w: pw, h: 0.5, fontSize: 9, color: C.white, align: "center", valign: "middle" });
    s.addText(p.tool, { x, y: 1.7, w: pw, h: 0.55, fontSize: 7.5, color: C.mint, align: "center" });
  });
  // Learning path
  const paths = [
    { time: "本週", action: "安裝 research-workspace\n建立第一份 QMD\n用 API 驗證 10 篇引用", color: C.teal },
    { time: "1 個月", action: "完成論文骨架 + Related Work\n跑完第一輪實驗\n用 /review-paper 自審", color: C.navy },
    { time: "3 個月", action: "論文初稿完成\n平行審查 (3 AI)\n投稿目標期刊", color: C.goldDark },
  ];
  paths.forEach((p, i) => {
    const x = 0.3 + i * 3.2;
    infoCard(s, pres, x, 2.85, 3.0, 1.6, p.time, p.action, p.color);
  });
  tipBox(s, 0.3, 4.7, 9.4, "AI 參與度 70-75% | 你的角色：決策者 + 審核者 + 學術判斷 | 11 Phase 完整覆蓋");
})();

// ══════════════════════════════════════════════════════════
// Slide 55: CLOSING
// ══════════════════════════════════════════════════════════
(() => {
  const s = pres.addSlide();
  s.background = { color: C.navy };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.08, fill: { color: C.gold } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0.08, w: 0.12, h: 5.545, fill: { color: C.teal } });
  s.addShape(pres.shapes.OVAL, { x: 7.2, y: -0.5, w: 3.5, h: 3.5, fill: { color: C.teal, transparency: 85 } });
  s.addShape(pres.shapes.OVAL, { x: 7.8, y: 0.5, w: 2.5, h: 2.5, fill: { color: C.gold, transparency: 80 } });
  // Thanks
  s.addText("謝謝大家", { x: 0.5, y: 1.0, w: 7, h: 1.2, fontSize: 52, bold: true, color: C.white });
  s.addText("AI 不會取代研究者，\n但善用 AI 的研究者會超越不用的。", {
    x: 0.5, y: 2.4, w: 7, h: 1.0, fontSize: 20, color: C.gold, lineSpacingMultiple: 1.3,
  });
  // 3 takeaways
  s.addText("核心理念：", { x: 0.5, y: 3.6, w: 2, h: 0.35, fontSize: 13, bold: true, color: C.teal });
  const ideas = [
    "流程導向，工具服務流程",
    "內建品質保證，不只教工具",
    "帶走完整系統，持續進化",
  ];
  ideas.forEach((idea, i) => {
    s.addText((i + 1) + ". " + idea, { x: 0.5, y: 3.95 + i * 0.35, w: 6, h: 0.35, fontSize: 12, color: C.white });
  });
  // Footer
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.2, w: 10, h: 0.425, fill: { color: C.teal, transparency: 60 } });
  s.addText("cooperation.tw | AI Paper Workshop 2026", {
    x: 0.4, y: 5.2, w: 9.2, h: 0.425, fontSize: 10, color: C.white, valign: "middle", align: "center",
  });
})();

// ═══════════════════════════════════════════════════════════
// OUTPUT
// ═══════════════════════════════════════════════════════════
const outDir = "/Users/user/Desktop/NILM+LLM/NILM_LLM_SETA/05_outputs/2026-03-06_AI_Paper_Workshop";
pres.writeFile({ fileName: `${outDir}/Day2_AI研究進階.pptx` })
  .then(() => console.log("Done! Day2_AI研究進階.pptx generated."))
  .catch(console.error);
