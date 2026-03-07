/**
 * AI Paper Workshop — Day 1: AI 研究基礎 (L1D2)
 * 24 slides: Cover → S1 Concepts → S2 Literature → Automation → Review
 * Brand: AI x 論文 (#0B3C5D navy)
 *
 * Run: NODE_PATH=$(npm root -g) node gen_day1.js
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
  // Gold top line
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.08, fill: { color: C.gold } });
  // Teal left bar
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0.08, w: 0.12, h: 5.545, fill: { color: C.teal } });
  // Decorative circles
  s.addShape(pres.shapes.OVAL, { x: 7.2, y: -0.5, w: 3.5, h: 3.5, fill: { color: C.teal, transparency: 85 } });
  s.addShape(pres.shapes.OVAL, { x: 7.8, y: 0.5, w: 2.5, h: 2.5, fill: { color: C.gold, transparency: 80 } });
  // Tag badge
  if (tag) {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 0.7, w: 2.4, h: 0.4, fill: { color: C.teal }, rectRadius: 0.06 });
    s.addText(tag, { x: 0.5, y: 0.7, w: 2.4, h: 0.4, fontSize: 12, bold: true, color: C.white, align: "center", valign: "middle" });
  }
  // Title
  s.addText(title, { x: 0.5, y: 1.3, w: 7.5, h: 1.8, fontSize: 44, bold: true, color: C.white, lineSpacingMultiple: 1.1 });
  // Subtitle
  s.addText(subtitle, { x: 0.5, y: 3.2, w: 7.5, h: 0.6, fontSize: 17, color: C.gold });
  // Badges
  if (badges) {
    badges.forEach((b, i) => {
      const bx = 0.5 + i * 1.6;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: bx, y: 4.0, w: 1.4, h: 0.34, fill: { color: b.color }, rectRadius: 0.06 });
      s.addText(b.text, { x: bx, y: 4.0, w: 1.4, h: 0.34, fontSize: 10, bold: true, color: C.white, align: "center", valign: "middle" });
    });
  }
  // Footer bar
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.2, w: 10, h: 0.425, fill: { color: C.teal, transparency: 60 } });
  if (footerLeft) s.addText(footerLeft, { x: 0.4, y: 5.2, w: 5, h: 0.425, fontSize: 10, color: C.white, valign: "middle" });
  if (footerRight) s.addText(footerRight, { x: 5, y: 5.2, w: 4.6, h: 0.425, fontSize: 10, color: C.white, valign: "middle", align: "right" });
  return s;
}

function sectionDivider(pres, { dayLabel, title, subtitle: sub }) {
  const s = pres.addSlide();
  s.background = { color: C.navy };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.12, h: 5.625, fill: { color: C.teal } });
  // Day badge
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 0.4, w: 1.6, h: 0.55, fill: { color: C.teal }, rectRadius: 0.08 });
  s.addText(dayLabel, { x: 0.5, y: 0.4, w: 1.6, h: 0.55, fontSize: 14, bold: true, color: C.white, align: "center", valign: "middle" });
  // Title
  s.addText(title, { x: 0.5, y: 1.2, w: 9, h: 1.5, fontSize: 42, bold: true, color: C.white });
  // Subtitle
  if (sub) s.addText(sub, { x: 0.5, y: 2.8, w: 9, h: 0.7, fontSize: 18, color: C.teal });
  // Bottom bar
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
    // Number circle
    s.addShape(pres.shapes.OVAL, { x: x + sw / 2 - 0.35, y: startY + 0.12, w: 0.7, h: 0.7, fill: { color: C.white } });
    s.addText(st.n, { x: x + sw / 2 - 0.35, y: startY + 0.12, w: 0.7, h: 0.7, fontSize: 20, bold: true, color: st.color, align: "center", valign: "middle" });
    // Title
    s.addText(st.title, { x: x + 0.06, y: startY + 0.95, w: sw - 0.12, h: 0.42, fontSize: 13, bold: true, color: C.white, align: "center" });
    // Desc
    s.addText(st.desc, { x: x + 0.08, y: startY + 1.4, w: sw - 0.16, h: 1.1, fontSize: 9.5, color: C.mint, align: "center", lineSpacingMultiple: 1.2 });
    // Arrow
    if (i < steps.length - 1) {
      s.addText("\u25B6", { x: x + sw + 0.01, y: startY + 1.05, w: 0.14, h: 0.4, fontSize: 11, color: C.grayText, align: "center" });
    }
  });
}

function tableSlide(s, headers, rows, opts = {}) {
  const startY = opts.y || 1.0;
  const colW = opts.colW || headers.map(() => 9.4 / headers.length);
  const tableRows = [
    headers.map(h => ({ text: h, options: { fontSize: 11, bold: true, color: C.white, fill: { color: C.navy }, align: "center", valign: "middle" } })),
    ...rows.map((row, ri) =>
      row.map((cell, ci) => ({
        text: cell,
        options: { fontSize: 10, color: C.darkText, fill: { color: ri % 2 === 0 ? C.white : C.lightBlue }, valign: "middle", align: ci === 0 ? "left" : "center" },
      }))
    ),
  ];
  s.addTable(tableRows, { x: 0.3, y: startY, w: 9.4, colW, border: { type: "solid", pt: 0.5, color: "D0D5DD" } });
}

// ═══════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "AI Paper Workshop - Day 1";
pres.author = "Alan Chen";

// ──────────────────────────────────────────────────────────
// Slide 1: COVER
// ──────────────────────────────────────────────────────────
coverSlide(pres, {
  tag: "AI Paper Workshop 2026",
  title: "AI 學術研究\n全流程工作坊",
  subtitle: "從概念探索到論文投稿的完整 AI 協作工作流程",
  badges: [
    { text: "Day 1  L1D2", color: C.teal },
    { text: "Day 2  L2D1", color: C.navyLight },
    { text: "24 Skills", color: C.goldDark },
    { text: "8 Agents", color: C.tealDark },
  ],
  footerLeft: "Smart Manufacturing Research Application",
  footerRight: "cooperation.tw",
});

// ──────────────────────────────────────────────────────────
// Slide 2: 完整 AI 研究工作流程總覽
// ──────────────────────────────────────────────────────────
(() => {
  const s = contentSlide(pres, "完整 AI 研究工作流程總覽", C.navy);
  // 11 Phase flow
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
    const bgC = i < 3 ? C.teal : C.navyLight;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.0, w: pw, h: 1.1, fill: { color: bgC }, rectRadius: 0.06, shadow: shadow(0.1) });
    s.addText(p.n, { x, y: 1.02, w: pw, h: 0.3, fontSize: 10, bold: true, color: C.gold, align: "center" });
    s.addText(p.label, { x, y: 1.3, w: pw, h: 0.7, fontSize: 10, color: C.white, align: "center", valign: "middle", lineSpacingMultiple: 1.1 });
    if (i < phases.length - 1) {
      s.addText("\u25B8", { x: x + pw, y: 1.35, w: gap, h: 0.4, fontSize: 9, color: C.grayText, align: "center" });
    }
  });
  // Day coverage
  s.addShape(pres.shapes.RECTANGLE, { x: 0.25, y: 2.3, w: 2.52, h: 0.3, fill: { color: C.teal, transparency: 20 } });
  s.addText("Day 1 範圍", { x: 0.25, y: 2.3, w: 2.52, h: 0.3, fontSize: 10, bold: true, color: C.teal, align: "center", valign: "middle" });
  s.addShape(pres.shapes.RECTANGLE, { x: 2.94, y: 2.3, w: 6.81, h: 0.3, fill: { color: C.navyLight, transparency: 20 } });
  s.addText("Day 2 範圍", { x: 2.94, y: 2.3, w: 6.81, h: 0.3, fontSize: 10, bold: true, color: C.navy, align: "center", valign: "middle" });
  // Key tools row
  const tools = [
    "Claude Chat\nExtended Thinking",
    "CrossRef API\nSemantic Scholar\nOpenAlex API",
    "innovation-\npositioning\njournal-fit",
    "IMRaD\nQMD + YAML",
    "experiment-\ntracker",
    "GPU Monitor\nTG Bot",
    "stats-validator\nevidence-indexer",
    "paper-writer\nacademic-writing",
    "paper-review\nmvp-gatekeeper",
    "submission-\nbundle",
    "rebuttal-\nmatrix",
  ];
  tools.forEach((t, i) => {
    const x = startX + i * (pw + gap);
    s.addText(t, { x, y: 2.8, w: pw, h: 0.9, fontSize: 7, color: C.grayText, align: "center", valign: "top", lineSpacingMultiple: 1.1 });
  });
  // Bottom stats
  tipBox(s, 0.25, 4.2, 9.5, "AI 參與度 70-75%  |  24 Skills + 8 Agents + 5 Commands + 5 APIs  |  真實案例：NILM+LLM 論文 (SETA)");
})();

// ──────────────────────────────────────────────────────────
// Slide 3: 兩天課程議程
// ──────────────────────────────────────────────────────────
(() => {
  const s = contentSlide(pres, "兩天課程議程規劃");
  // Day 1 column
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.3, y: 0.9, w: 4.5, h: 0.4, fill: { color: C.teal }, rectRadius: 0.06 });
  s.addText("Day 1 | AI 研究基礎 (L1D2)", { x: 0.3, y: 0.9, w: 4.5, h: 0.4, fontSize: 13, bold: true, color: C.white, align: "center", valign: "middle" });
  const d1 = [
    ["09:00-09:30", "開場：AI 正在重塑學術研究"],
    ["09:30-10:45", "S1：AI 概念探索與研究方向"],
    ["11:00-12:00", "S2 前半：文獻查找 + API 驗證"],
    ["13:00-14:30", "S2 後半：文獻系統化 + Research Gap"],
    ["14:45-16:00", "自動化工具入門 + 實作"],
    ["16:00-17:00", "Day 1 回顧與明日預告"],
  ];
  d1.forEach((r, i) => {
    const y = 1.42 + i * 0.55;
    const bg = i % 2 === 0 ? C.white : C.lightBlue;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y, w: 4.5, h: 0.5, fill: { color: bg } });
    s.addText(r[0], { x: 0.4, y, w: 1.4, h: 0.5, fontSize: 10, bold: true, color: C.teal, valign: "middle" });
    s.addText(r[1], { x: 1.85, y, w: 2.9, h: 0.5, fontSize: 10, color: C.darkText, valign: "middle" });
  });

  // Day 2 column
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.2, y: 0.9, w: 4.5, h: 0.4, fill: { color: C.navyLight }, rectRadius: 0.06 });
  s.addText("Day 2 | AI 研究進階 (L2D1)", { x: 5.2, y: 0.9, w: 4.5, h: 0.4, fontSize: 13, bold: true, color: C.white, align: "center", valign: "middle" });
  const d2 = [
    ["09:00-09:20", "Day 1 回顧 + 中階概念導入"],
    ["09:20-10:45", "S3：論文架構 + 實驗規劃"],
    ["11:00-12:00", "數據彙整 + 可重現性設計"],
    ["13:00-14:15", "S4：QMD + BibTeX 論文撰寫"],
    ["14:15-14:45", "Claude Code 自動化工作流"],
    ["15:00-16:30", "S5：品質保證 + 投稿策略"],
    ["16:30-17:30", "總結與下一步"],
  ];
  d2.forEach((r, i) => {
    const y = 1.42 + i * 0.5;
    const bg = i % 2 === 0 ? C.white : C.lightBlue;
    s.addShape(pres.shapes.RECTANGLE, { x: 5.2, y, w: 4.5, h: 0.46, fill: { color: bg } });
    s.addText(r[0], { x: 5.3, y, w: 1.4, h: 0.46, fontSize: 10, bold: true, color: C.navyLight, valign: "middle" });
    s.addText(r[1], { x: 6.75, y, w: 2.9, h: 0.46, fontSize: 10, color: C.darkText, valign: "middle" });
  });

  tipBox(s, 0.3, 4.85, 9.4, "講述 46% | Demo 27% | 實作 27%  —  完整走過 11 個 Phase，結業帶走 research-workspace.zip");
})();

// ──────────────────────────────────────────────────────────
// Slide 4: Day 1 Section Divider
// ──────────────────────────────────────────────────────────
sectionDivider(pres, {
  dayLabel: "Day 1",
  title: "AI 研究基礎\n從概念到文獻",
  subtitle: "L1D2 初階進階 | AI 是「聰明的助教」",
});

// ──────────────────────────────────────────────────────────
// Slide 5: 為什麼需要 AI 輔助學術研究？
// ──────────────────────────────────────────────────────────
(() => {
  const s = contentSlide(pres, "為什麼需要 AI 輔助學術研究？");
  // Pain points vs Solutions (3 pairs)
  const pairs = [
    { pain: "文獻海量\n每年 300 萬篇新論文，\n人工篩選耗時耗力", sol: "AI 文獻篩選\nAPI 驗證 + 語義比對\n30 秒評估一篇論文" },
    { pain: "寫作瓶頸\n英文非母語，學術風格\n難掌握，改稿反覆", sol: "AI 寫作助手\n學術風格指導 + 潤稿\n結構化撰寫流程" },
    { pain: "品質不一\n引用錯誤、數據不一致\n投稿被 desk reject", sol: "AI 品質審查\n七維度評分 + P0-P3 分級\n多 AI 平行審查" },
  ];
  pairs.forEach((p, i) => {
    const y = 1.0 + i * 1.35;
    // Pain card (orange accent)
    infoCard(s, pres, 0.3, y, 4.2, 1.15, ["痛點 " + (i + 1)][0], p.pain, C.orange);
    // Arrow
    s.addText("\u27A1", { x: 4.55, y: y + 0.3, w: 0.5, h: 0.4, fontSize: 18, color: C.teal, align: "center" });
    // Solution card (teal accent)
    infoCard(s, pres, 5.1, y, 4.6, 1.15, ["AI 解方 " + (i + 1)][0], p.sol, C.teal);
  });
})();

// ──────────────────────────────────────────────────────────
// Slide 6: Session 1 Divider — AI 概念探索
// ──────────────────────────────────────────────────────────
sectionDivider(pres, {
  dayLabel: "Session 1",
  title: "AI 概念探索\n與研究方向確定",
  subtitle: "Phase 1 | 75 分鐘 | Prompt 工程 + 多輪對話 + 方向確認",
});

// ──────────────────────────────────────────────────────────
// Slide 7: CARE 框架 — 研究 Prompt 工程
// ──────────────────────────────────────────────────────────
(() => {
  const s = contentSlide(pres, "研究 Prompt 工程：CARE 框架");
  // CARE 4 cards
  const care = [
    { letter: "C", word: "Context", desc: "提供研究背景\n「我在研究工業 NILM，\n使用 CNN 方法...」", color: C.teal },
    { letter: "A", word: "Action", desc: "明確任務指令\n「請分析 2020-2025 年\n該領域的 research gap」", color: C.navy },
    { letter: "R", word: "Role", desc: "指定 AI 角色\n「你是 Energy & Buildings\n的資深審稿人」", color: C.goldDark },
    { letter: "E", word: "Example", desc: "給出範例格式\n「請用表格列出：\n論文/方法/數據集/F1」", color: C.tealDark },
  ];
  care.forEach((c, i) => {
    const x = 0.3 + i * 2.4;
    // Letter circle
    s.addShape(pres.shapes.OVAL, { x: x + 0.65, y: 0.95, w: 0.9, h: 0.9, fill: { color: c.color } });
    s.addText(c.letter, { x: x + 0.65, y: 0.95, w: 0.9, h: 0.9, fontSize: 32, bold: true, color: C.white, align: "center", valign: "middle" });
    // Word
    s.addText(c.word, { x, y: 1.95, w: 2.2, h: 0.35, fontSize: 14, bold: true, color: c.color, align: "center" });
    // Description card
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.35, w: 2.2, h: 1.5, fill: { color: C.white }, shadow: shadow(0.1) });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.35, w: 2.2, h: 0.06, fill: { color: c.color } });
    s.addText(c.desc, { x: x + 0.1, y: 2.45, w: 2.0, h: 1.3, fontSize: 10, color: C.darkText, lineSpacingMultiple: 1.25 });
  });
  tipBox(s, 0.3, 4.1, 9.4, "5 套研究專用模板：領域掃描 | Research Gap | 可行性分析 | 創新性定位 | 研究問題精煉");
})();

// ──────────────────────────────────────────────────────────
// Slide 8: 多輪對話策略
// ──────────────────────────────────────────────────────────
(() => {
  const s = contentSlide(pres, "多輪對話策略：漸進式縮焦法");
  // 5-round funnel
  const rounds = [
    { r: "Round 1", q: "「智慧製造有哪些 AI 應用方向？」", w: 9.0, color: C.teal },
    { r: "Round 2", q: "「NILM 目前有哪些深度學習方法？」", w: 7.6, color: C.tealDark },
    { r: "Round 3", q: "「低採樣率 NILM 有什麼尚未解決的問題？」", w: 6.2, color: C.navy },
    { r: "Round 4", q: "「Training-free NILM 可行嗎？有沒有相關研究？」", w: 4.8, color: C.navyLight },
    { r: "Round 5", q: "「LLM + NILM 作為 training-free 方案的創新性？」", w: 3.4, color: C.goldDark },
  ];
  rounds.forEach((rd, i) => {
    const y = 0.95 + i * 0.72;
    const x = (10 - rd.w) / 2;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: rd.w, h: 0.6, fill: { color: rd.color }, rectRadius: 0.08, shadow: shadow(0.08) });
    s.addText(rd.r, { x: x + 0.15, y, w: 1.2, h: 0.6, fontSize: 11, bold: true, color: C.gold, valign: "middle" });
    s.addText(rd.q, { x: x + 1.4, y, w: rd.w - 1.6, h: 0.6, fontSize: 11, color: C.white, valign: "middle" });
  });
  // Extended Thinking box
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 4.65, w: 9.4, h: 0.55, fill: { color: C.lightBlue } });
  s.addText("Extended Thinking 指令：think (標準) | think hard (深度) | ultrathink (極限)  ——  複雜問題用更深的推理", {
    x: 0.45, y: 4.65, w: 9.1, h: 0.55, fontSize: 10.5, color: C.navy, valign: "middle",
  });
})();

// ──────────────────────────────────────────────────────────
// Slide 9: 真實案例 — NILM+LLM 概念探索歷程
// ──────────────────────────────────────────────────────────
(() => {
  const s = contentSlide(pres, "真實案例：NILM+LLM 的概念探索歷程");
  // Timeline
  const steps = [
    { label: "Week 1", desc: "領域掃描\n工業能源管理\nAI 應用全景", color: C.teal },
    { label: "Week 2", desc: "聚焦 NILM\n非侵入式負載\n識別技術", color: C.tealDark },
    { label: "Week 3", desc: "發現 Gap\n低採樣率場景\n缺乏解方", color: C.navy },
    { label: "Week 4", desc: "創新假設\nLLM 知識遷移\n取代 training", color: C.navyLight },
    { label: "Week 5", desc: "三大貢獻\n確立論文定位\n鎖定期刊", color: C.goldDark },
  ];
  processSteps(s, pres, steps.map((st, i) => ({ n: String(i + 1), title: st.label, desc: st.desc, color: st.color })), 1.0);
  // 3 contributions
  infoCard(s, pres, 0.3, 3.85, 3.0, 1.0, "C1: Training-Free", "首次提出 LLM 驅動的\n免訓練 NILM 框架", C.teal);
  infoCard(s, pres, 3.5, 3.85, 3.0, 1.0, "C2: Prompt Engineering", "設計工業設備專用的\n結構化 Prompt 範本", C.navy);
  infoCard(s, pres, 6.7, 3.85, 3.0, 1.0, "C3: Multi-Dataset", "跨三個數據集驗證\n9 類設備 F1=0.85", C.goldDark);
})();

// ──────────────────────────────────────────────────────────
// Slide 10: Session 2 Divider — 文獻調研
// ──────────────────────────────────────────────────────────
sectionDivider(pres, {
  dayLabel: "Session 2",
  title: "AI 輔助文獻調研\n核心環節",
  subtitle: "Phase 2-3 | 文獻正確性是本課程的核心",
});

// ──────────────────────────────────────────────────────────
// Slide 11: 種子 DOI 生成
// ──────────────────────────────────────────────────────────
(() => {
  const s = contentSlide(pres, "種子 DOI 生成：用 AI 產出候選文獻清單");
  // Left: Prompt example
  codeBox(s, pres, 0.3, 0.9, 4.5, 2.4, "Prompt 範例", [
    '你是 NILM (Non-Intrusive Load Monitoring)',
    '領域的資深研究者。',
    '',
    '請列出以下三個方向近 5 年最重要的',
    '20 篇論文，包含 DOI：',
    '1. 深度學習 NILM 方法',
    '2. 低採樣率 NILM',
    '3. LLM 在能源領域的應用',
  ].join("\n"));
  // Right: AI output example
  codeBox(s, pres, 5.2, 0.9, 4.5, 2.4, "AI 產出範例", [
    '1. Kelly & Knottenbelt (2015)',
    '   DOI: 10.1145/2821650.2821672',
    '   Neural NILM: Deep Neural Networks',
    '',
    '2. Zhang et al. (2018)',
    '   DOI: 10.1109/TSG.2017.2743342',
    '   Sequence-to-Point Learning...',
    '',
    '3. [更多候選文獻...]',
  ].join("\n"));
  // Warning box
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 3.5, w: 9.4, h: 0.7, fill: { color: "FEF2F2" } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 3.5, w: 0.08, h: 0.7, fill: { color: C.red } });
  s.addText("AI 產出的 DOI 不能直接信任！必須經過 API 驗證。AI 可能產出：不存在的 DOI、錯誤的作者/年份、虛構的論文。", {
    x: 0.55, y: 3.5, w: 9.0, h: 0.7, fontSize: 11, bold: true, color: C.red, valign: "middle",
  });
  tipBox(s, 0.3, 4.4, 9.4, "三層搜索策略：Google Scholar → ArXiv/IEEE Xplore → Citation Graph (forward + backward)");
})();

// ──────────────────────────────────────────────────────────
// Slide 12: 多重 API 驗證流程
// ──────────────────────────────────────────────────────────
(() => {
  const s = contentSlide(pres, "多重 API 驗證流程（文獻正確性的核心）");
  processSteps(s, pres, [
    { n: "1", title: "CrossRef API", desc: "DOI 存在性驗證\n正式 metadata\n(title/author/year)", color: C.teal },
    { n: "2", title: "Semantic Scholar", desc: "Abstract 擷取\n引用數統計\n領域分類", color: C.navy },
    { n: "3", title: "OpenAlex API", desc: "OA 狀態查詢\n機構資訊\nConcepts 標籤", color: C.tealDark },
    { n: "4", title: "AI 語義比對", desc: "Abstract 相關性\n1-5 分評分\n標記引用位置", color: C.goldDark },
  ], 0.95);
  // Bottom flow
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 3.8, w: 9.4, h: 0.06, fill: { color: C.teal } });
  const flow = ["AI 產出 DOI", "CrossRef 驗證", "Semantic Scholar", "OpenAlex", "AI 評分", "Zotero 匯入"];
  flow.forEach((f, i) => {
    const x = 0.3 + i * 1.57;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 4.05, w: 1.4, h: 0.4, fill: { color: i === 0 ? C.orange : i === flow.length - 1 ? C.teal : C.white }, rectRadius: 0.06, shadow: shadow(0.08) });
    s.addText(f, { x, y: 4.05, w: 1.4, h: 0.4, fontSize: 9, bold: true, color: i === 0 || i === flow.length - 1 ? C.white : C.darkText, align: "center", valign: "middle" });
    if (i < flow.length - 1) s.addText("\u25B8", { x: x + 1.4, y: 4.05, w: 0.17, h: 0.4, fontSize: 10, color: C.grayText, align: "center", valign: "middle" });
  });
  tipBox(s, 0.3, 4.65, 9.4, "案例：NILM+LLM 論文 43 篇引用全部經 CrossRef 驗證，發現 2 篇 AI 虛構 DOI");
})();

// ──────────────────────────────────────────────────────────
// Slide 13: API 實戰示範
// ──────────────────────────────────────────────────────────
(() => {
  const s = contentSlide(pres, "API 實戰示範：curl 一行驗證 DOI");
  // 3 code boxes
  codeBox(s, pres, 0.3, 0.9, 3.1, 2.5, "CrossRef API", [
    'curl "https://api.crossref.org/',
    '  works/10.1016/j.seta.2020.100921"',
    '',
    '# Response:',
    '{',
    '  "title": "Industrial NILM...",',
    '  "author": [{"given":"..."}],',
    '  "published": {"date-parts":',
    '    [[2020,12]]}',
    '}',
  ].join("\n"));
  codeBox(s, pres, 3.6, 0.9, 3.1, 2.5, "Semantic Scholar", [
    'curl "https://api.semantic',
    '  scholar.org/graph/v1/paper/',
    '  DOI:10.1016/j.seta.2020...',
    '  ?fields=abstract,',
    '  citationCount"',
    '',
    '# Response:',
    '{ "abstract": "This paper...",',
    '  "citationCount": 42 }',
  ].join("\n"));
  codeBox(s, pres, 6.9, 0.9, 2.8, 2.5, "OpenAlex", [
    'curl "https://api.openalex',
    '  .org/works/',
    '  doi:10.1016/..."',
    '',
    '# Response:',
    '{ "is_oa": true,',
    '  "concepts": [',
    '    {"display_name":',
    '     "NILM"}',
    '  ] }',
  ].join("\n"));
  // Python batch script
  codeBox(s, pres, 0.3, 3.6, 9.4, 1.1, "Python 批次驗證腳本 (概念)", [
    'import requests',
    'for doi in seed_dois:',
    '    r = requests.get(f"https://api.crossref.org/works/{doi}")',
    '    if r.status_code == 200: verified.append(doi)  # DOI exists',
    '    else: rejected.append(doi)                      # DOI invalid!',
  ].join("\n"));
  tipBox(s, 0.3, 4.85, 9.4, "免費、無需 API Key、每秒可查 50 次 — 驗證 100 篇文獻只需 2 秒");
})();

// ──────────────────────────────────────────────────────────
// Slide 14: 批次匯入 Zotero
// ──────────────────────────────────────────────────────────
(() => {
  const s = contentSlide(pres, "批次匯入 Zotero：四種方法");
  const methods = [
    { title: "Magic Wand", desc: "在 Zotero 工具列貼上 DOI 清單\n自動取得完整 metadata\n最簡單、適合少量", icon: "1" },
    { title: "Zotero Connector", desc: "瀏覽器擴充套件\n在 Google Scholar 頁面\n一鍵批次儲存", icon: "2" },
    { title: "BibTeX 匯入", desc: "匯入 references.bib\n保留所有欄位\n適合已有 BibTeX 的情況", icon: "3" },
    { title: "Zotero API", desc: "程式化匯入 (pyzotero)\n大量文獻自動化\n適合 50+ 篇的情境", icon: "4" },
  ];
  methods.forEach((m, i) => {
    const x = 0.3 + i * 2.4;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.95, w: 2.2, h: 2.8, fill: { color: C.white }, shadow: shadow(0.1) });
    // Number
    s.addShape(pres.shapes.OVAL, { x: x + 0.8, y: 1.05, w: 0.6, h: 0.6, fill: { color: C.teal } });
    s.addText(m.icon, { x: x + 0.8, y: 1.05, w: 0.6, h: 0.6, fontSize: 18, bold: true, color: C.white, align: "center", valign: "middle" });
    // Title
    s.addText(m.title, { x, y: 1.75, w: 2.2, h: 0.35, fontSize: 13, bold: true, color: C.navy, align: "center" });
    // Desc
    s.addText(m.desc, { x: x + 0.1, y: 2.15, w: 2.0, h: 1.4, fontSize: 10, color: C.darkText, align: "center", lineSpacingMultiple: 1.25 });
  });
  tipBox(s, 0.3, 4.0, 9.4, "推薦組合：API 驗證 DOI → BibTeX 匯出 → Zotero 匯入 → 自動抓 PDF + metadata");
  // Bottom note
  s.addText("Zotero 是免費、開源的文獻管理工具，支援 Word/Google Docs/LaTeX/QMD 引用插入", {
    x: 0.3, y: 4.55, w: 9.4, h: 0.4, fontSize: 9.5, color: C.grayText, align: "center", valign: "middle",
  });
})();

// ──────────────────────────────────────────────────────────
// Slide 15: 文獻整理系統
// ──────────────────────────────────────────────────────────
(() => {
  const s = contentSlide(pres, "文獻整理系統：AI 筆記轉換工作流");
  processSteps(s, pres, [
    { n: "1", title: "PDF 取得", desc: "Zotero 自動下載\n或手動上傳\n建立文獻庫", color: C.teal },
    { n: "2", title: "AI 結構化摘要", desc: "Claude 閱讀 PDF\n擷取核心貢獻\n方法/數據/結果", color: C.navy },
    { n: "3", title: "Obsidian 筆記卡", desc: "YAML frontmatter\n雙向連結 [[link]]\n標記引用位置", color: C.tealDark },
    { n: "4", title: "知識圖譜", desc: "Graph View 視覺化\n主題聚類分析\n發現研究缺口", color: C.goldDark },
  ], 0.95);
  // AI demo
  infoCard(s, pres, 0.3, 3.8, 4.5, 1.3, "AI 30 秒評估一篇論文", "五維度快速評估：\n1. 相關性 (與我研究的關聯)\n2. 新穎性 (方法是否新穎)\n3. 影響力 (引用數 + 期刊等級)\n4. 可比較性 (能否做 baseline)\n5. 引用價值 (放在哪個章節)", C.teal);
  infoCard(s, pres, 5.1, 3.8, 4.6, 1.3, "literature-synthesis Skill", "自動觸發：\n- 文獻分類矩陣建立\n- Research Gap 識別\n- Related Work 段落撰寫建議\n- /analyze-literature command", C.navy);
})();

// ──────────────────────────────────────────────────────────
// Slide 16: Obsidian 文獻筆記卡 + 知識圖譜
// ──────────────────────────────────────────────────────────
(() => {
  const s = contentSlide(pres, "文獻筆記卡 + Obsidian 知識圖譜");
  // Left: note card example
  codeBox(s, pres, 0.3, 0.9, 4.5, 3.6, "Obsidian 筆記卡範例", [
    '---',
    'tags: [NILM, training-free]',
    'doi: "10.1016/j.seta.2020.100921"',
    'year: 2021',
    'relevance: 4/5',
    'cite_in: [Introduction, Related Work]',
    '---',
    '',
    '# Eskander2021 - Industrial NILM',
    '',
    '## Core Contribution',
    '-> 首篇工業 NILM 綜述...',
    '',
    '## Link to My Research',
    '-> 支撐 C1 -> [[Research_Gap]]',
    '',
    '## Related Papers',
    '-> [[Hart1992]] [[Kelly2015]]',
  ].join("\n"));
  // Right: Graph View concept
  s.addShape(pres.shapes.RECTANGLE, { x: 5.1, y: 0.9, w: 4.6, h: 3.6, fill: { color: C.slate }, shadow: shadow() });
  s.addText("Obsidian Graph View", { x: 5.1, y: 0.95, w: 4.6, h: 0.35, fontSize: 13, bold: true, color: C.gold, align: "center" });
  // Simulated nodes
  const nodes = [
    { x: 6.4, y: 1.6, r: 0.3, label: "Hart\n1992", color: C.teal },
    { x: 7.8, y: 1.5, r: 0.35, label: "Kelly\n2015", color: C.teal },
    { x: 6.0, y: 2.5, r: 0.25, label: "Zhang\n2018", color: C.tealDark },
    { x: 7.2, y: 2.6, r: 0.4, label: "My\nResearch", color: C.gold },
    { x: 8.5, y: 2.4, r: 0.28, label: "Esk.\n2021", color: C.tealDark },
    { x: 6.8, y: 3.4, r: 0.22, label: "LLM\nNILM", color: C.goldDark },
    { x: 8.2, y: 3.3, r: 0.25, label: "GPT\nEnergy", color: C.navyLight },
  ];
  nodes.forEach(n => {
    s.addShape(pres.shapes.OVAL, { x: n.x, y: n.y, w: n.r * 2, h: n.r * 2, fill: { color: n.color, transparency: 30 } });
    s.addText(n.label, { x: n.x, y: n.y, w: n.r * 2, h: n.r * 2, fontSize: 7, bold: true, color: C.white, align: "center", valign: "middle" });
  });
  // Legend
  const legend = [
    { label: "節點 = 文獻卡", color: C.teal },
    { label: "連線 = [[雙向連結]]", color: C.white },
    { label: "聚類 = 主題群", color: C.tealDark },
    { label: "孤立 = 可能遺漏", color: C.grayText },
  ];
  legend.forEach((l, i) => {
    s.addShape(pres.shapes.OVAL, { x: 5.3, y: 3.85 + i * 0.28, w: 0.18, h: 0.18, fill: { color: l.color } });
    s.addText(l.label, { x: 5.55, y: 3.82 + i * 0.28, w: 2.5, h: 0.24, fontSize: 8.5, color: C.white });
  });
})();

// ──────────────────────────────────────────────────────────
// Slide 17: Abstract 捕捉技術
// ──────────────────────────────────────────────────────────
(() => {
  const s = contentSlide(pres, "Abstract 捕捉技術：5 維度快速評估");
  const dims = [
    { name: "相關性", desc: "與我研究主題的\n直接關聯程度", weight: "30%", color: C.teal },
    { name: "新穎性", desc: "方法或觀點的\n原創性與新穎度", weight: "20%", color: C.navy },
    { name: "影響力", desc: "引用數、期刊等級\nH-index", weight: "20%", color: C.tealDark },
    { name: "可比較性", desc: "能否作為 baseline\n或 benchmark 使用", weight: "15%", color: C.goldDark },
    { name: "引用價值", desc: "適合放在論文的\n哪個章節引用", weight: "15%", color: C.navyLight },
  ];
  dims.forEach((d, i) => {
    const x = 0.3 + i * 1.92;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.95, w: 1.8, h: 2.8, fill: { color: C.white }, shadow: shadow(0.1) });
    // Top bar
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.95, w: 1.8, h: 0.5, fill: { color: d.color } });
    s.addText(d.name, { x, y: 0.95, w: 1.8, h: 0.5, fontSize: 14, bold: true, color: C.white, align: "center", valign: "middle" });
    // Weight
    s.addText(d.weight, { x, y: 1.55, w: 1.8, h: 0.35, fontSize: 20, bold: true, color: d.color, align: "center" });
    // Desc
    s.addText(d.desc, { x: x + 0.1, y: 2.0, w: 1.6, h: 1.0, fontSize: 10.5, color: C.darkText, align: "center", lineSpacingMultiple: 1.3 });
    // Score bar
    s.addShape(pres.shapes.RECTANGLE, { x: x + 0.15, y: 3.1, w: 1.5, h: 0.25, fill: { color: C.lightBlue } });
    s.addShape(pres.shapes.RECTANGLE, { x: x + 0.15, y: 3.1, w: 1.5 * (0.5 + Math.random() * 0.5), h: 0.25, fill: { color: d.color, transparency: 40 } });
    s.addText("1   2   3   4   5", { x: x + 0.15, y: 3.1, w: 1.5, h: 0.25, fontSize: 8, color: C.grayText, align: "center", valign: "middle" });
  });
  tipBox(s, 0.3, 4.05, 9.4, "Claude 閱讀 PDF → 30 秒產出結構化摘要 + 5 維度評分 → 快速決定 keep / skip / deeper read");
})();

// ──────────────────────────────────────────────────────────
// Slide 18: BibTeX 引用管理 + bib-manager
// ──────────────────────────────────────────────────────────
(() => {
  const s = contentSlide(pres, "BibTeX 引用管理 + bib-manager Skill");
  // Left: BibTeX example
  codeBox(s, pres, 0.3, 0.9, 4.5, 2.3, "references.bib 範例", [
    '@article{chen2026nilm,',
    '  title  = {Training-Free Industrial',
    '            NILM via LLM},',
    '  author = {Chen, Chung-Kuang and',
    '            Wu, Chia-Hung},',
    '  journal= {Sustainable Energy ...',
    '            and Assessments},',
    '  year   = {2026},',
    '  doi    = {10.1016/j.seta...}',
    '}',
  ].join("\n"));
  // Right: bib-manager features
  infoCard(s, pres, 5.1, 0.9, 4.6, 2.3, "bib-manager Skill 防呆機制", [
    "1. 重複條目偵測 — 相同 DOI 或 title",
    "2. 格式一致性 — field 命名、縮排",
    "3. 幽靈引用警告 — .bib 有但論文沒引用",
    "4. 遺漏引用 — 論文用了但 .bib 沒有",
    "5. CrossRef 交叉驗證 — 比對年份/作者",
    "",
    "案例：43 篇引用，發現 3 個格式問題",
  ].join("\n"), C.teal);
  // Bottom golden rule
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 3.45, w: 9.4, h: 0.65, fill: { color: "FFF7E6" } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 3.45, w: 0.08, h: 0.65, fill: { color: C.gold } });
  s.addText("黃金規則：絕不添加 references.bib 中不存在的引用 — AI 要引用，必須先驗證 DOI、新增到 .bib、再引用", {
    x: 0.55, y: 3.45, w: 9.0, h: 0.65, fontSize: 11, bold: true, color: C.goldDark, valign: "middle",
  });
  // Citation format
  infoCard(s, pres, 0.3, 4.3, 4.5, 0.9, "QMD 引用格式", "單引用：@chen2026nilm\n多引用：[@chen2026nilm; @kelly2015]", C.navy);
  infoCard(s, pres, 5.1, 4.3, 4.6, 0.9, "CSL 樣式切換", "Elsevier: elsevier-vancouver-author-date\nIEEE: ieee.csl  |  APA: apa.csl", C.tealDark);
})();

// ──────────────────────────────────────────────────────────
// Slide 19: Research Gap 識別
// ──────────────────────────────────────────────────────────
(() => {
  const s = contentSlide(pres, "Research Gap 識別 + Literature Synthesis");
  // 3-layer gap method
  const layers = [
    { label: "現有方法", desc: "CNN/RNN/Transformer 需要大量標註數據\n監督式學習為主流，佔 NILM 研究 85%", w: 9.0, color: C.teal },
    { label: "已知限制", desc: "工業場景標註成本高（$5K-50K/設備）\n低採樣率 (1Hz) 資訊量不足、模型泛化差", w: 7.0, color: C.navy },
    { label: "研究機會", desc: "Training-free NILM: 利用 LLM 世界知識取代訓練\n= 本論文的核心貢獻", w: 5.0, color: C.goldDark },
  ];
  layers.forEach((l, i) => {
    const x = (10 - l.w) / 2;
    const y = 0.95 + i * 1.05;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: l.w, h: 0.85, fill: { color: l.color }, rectRadius: 0.08, shadow: shadow(0.1) });
    s.addText(l.label, { x: x + 0.2, y, w: 1.5, h: 0.85, fontSize: 13, bold: true, color: C.gold, valign: "middle" });
    s.addText(l.desc, { x: x + 1.8, y, w: l.w - 2.0, h: 0.85, fontSize: 10.5, color: C.white, valign: "middle", lineSpacingMultiple: 1.2 });
  });
  // literature-synthesis skill
  infoCard(s, pres, 0.3, 4.15, 4.5, 1.0, "literature-synthesis Skill", "自動觸發詞：「文獻回顧」「research gap」\n- 建立文獻分類矩陣 (方法 x 數據集 x 指標)\n- 識別 Gap → 生成 Related Work 結構", C.teal);
  infoCard(s, pres, 5.1, 4.15, 4.6, 1.0, "/analyze-literature Command", "一鍵啟動文獻分析工作流：\n- 輸入主題關鍵詞\n- 輸出 Gap 分析 + 文獻矩陣 + 建議結構", C.navy);
})();

// ──────────────────────────────────────────────────────────
// Slide 20: 創新性定位 + 期刊匹配
// ──────────────────────────────────────────────────────────
(() => {
  const s = contentSlide(pres, "創新性定位 + 期刊匹配 (Phase 3)");
  // Left: Innovation positioning
  infoCard(s, pres, 0.3, 0.9, 4.5, 1.6, "innovation-positioning Skill 三層框架", [
    "Layer 1: 技術創新 — 新方法/新架構",
    "Layer 2: 應用創新 — 新場景/新數據",
    "Layer 3: 整合創新 — 跨域結合 (LLM+NILM)",
    "",
    '避免陷阱：',
    '"Inspired by..." / "We improve..." →',
    '容易被定位為「應用研究」',
  ].join("\n"), C.teal);
  // Right: Journal matching 6 dimensions
  const s2data = [
    ["維度", "權重", "內容"],
    ["Scope 契合度", "35%", "Aims & Scope 重疊"],
    ["Impact Factor", "15%", "JCR + CiteScore"],
    ["主編研究偏好", "20%", "主編領域、發表傾向"],
    ["近期收錄主題", "15%", "近 2 年 topic clustering"],
    ["審稿週期", "10%", "First Decision 時間"],
    ["OA / APC", "5%", "費用與 OA 選項"],
  ];
  tableSlide(s, s2data[0], s2data.slice(1), { y: 0.9, colW: [1.5, 0.7, 2.3] });
  // Move table to right side
  // Actually let's use a different approach - add table manually positioned
  // Case study
  tipBox(s, 0.3, 3.8, 9.4, "案例：10 期刊加權評分 → Applied Energy (91) > IEEE TII (89) → 最終選擇 SETA (Scope 最佳匹配)");
  // journal-fit skill
  infoCard(s, pres, 0.3, 4.4, 4.5, 0.8, "journal-fit Skill", "輸入研究主題 → 輸出期刊推薦 + 加權評分\n含 desk-reject 風險評估", C.navy);
  infoCard(s, pres, 5.1, 4.4, 4.6, 0.8, "主編分析 (關鍵新增)", "Google Scholar 查主編 + Editorial 分析\n新主編上任 → 更開放 | Special Issue → 高契合", C.goldDark);
})();

// ──────────────────────────────────────────────────────────
// Slide 21: 自動化工具入門 — Google Apps Script
// ──────────────────────────────────────────────────────────
(() => {
  const s = contentSlide(pres, "自動化工具入門：Google Apps Script");
  // 3 use cases
  infoCard(s, pres, 0.3, 0.9, 3.0, 2.5, "批次 PDF 分析", [
    "Google Drive 上傳 PDF",
    "↓",
    "Apps Script 觸發",
    "↓",
    "Claude API 擷取摘要",
    "↓",
    "Google Sheet 彙整結果",
  ].join("\n"), C.teal);
  infoCard(s, pres, 3.5, 0.9, 3.0, 2.5, "文獻追蹤通知", [
    "設定排程 (每週一次)",
    "↓",
    "Semantic Scholar API",
    "查詢新引用",
    "↓",
    "Email / Telegram 通知",
    "新的引用你的論文！",
  ].join("\n"), C.navy);
  infoCard(s, pres, 6.7, 0.9, 3.0, 2.5, "引用格式轉換", [
    "Google Sheet 文獻清單",
    "↓",
    "CrossRef API 取 metadata",
    "↓",
    "自動生成 BibTeX",
    "↓",
    "匯出 references.bib",
  ].join("\n"), C.goldDark);
  tipBox(s, 0.3, 3.6, 9.4, "Google Apps Script = Google 版的巨集，可串接所有 Google 服務 + 外部 API — 免費、無需伺服器");
  // Quick start
  codeBox(s, pres, 0.3, 4.2, 9.4, 1.0, "GAS 快速上手 (5 行搞定)", [
    'function analyzePDF() {',
    '  const file = DriveApp.getFileById("FILE_ID");',
    '  const response = UrlFetchApp.fetch("https://api.anthropic.com/v1/messages", options);',
    '  SpreadsheetApp.getActive().getSheetByName("Results").appendRow([file.getName(), JSON.parse(response)]);',
    '}',
  ].join("\n"));
})();

// ──────────────────────────────────────────────────────────
// Slide 22: Claude Code 初體驗
// ──────────────────────────────────────────────────────────
(() => {
  const s = contentSlide(pres, "Claude Code 初體驗");
  // 3 concept cards
  infoCard(s, pres, 0.3, 0.9, 3.0, 1.8, 'CLAUDE.md = "AI 的工作手冊"', [
    "定義 AI 的行為規範：",
    "- 引用處理原則（最高優先）",
    "- 檔案操作原則",
    "- 驗證原則",
    "- 專案目錄結構",
  ].join("\n"), C.teal);
  infoCard(s, pres, 3.5, 0.9, 3.0, 1.8, "Skills / Agents / Commands", [
    "Skills (24 個)：專業知識庫",
    "→ 自動觸發，無需記指令",
    "",
    "Agents (8 個)：AI 專家團隊",
    "→ 各有獨立 context + 權限",
    "",
    "Commands (5 個)：一鍵工作流",
  ].join("\n"), C.navy);
  infoCard(s, pres, 6.7, 0.9, 3.0, 1.8, "CLI 基本操作", [
    "安裝：",
    "npm i -g @anthropic-ai/claude-code",
    "",
    "啟動：",
    "cd ~/research-project",
    "claude",
    "",
    "→ 即可在專案中對話",
  ].join("\n"), C.goldDark);
  // Demo
  codeBox(s, pres, 0.3, 2.9, 9.4, 1.5, "Demo：用 Claude Code 批次驗證 DOI", [
    '$ claude',
    '> 請幫我驗證 seed_dois.txt 中所有 DOI 的正確性，',
    '  使用 CrossRef API 檢查每個 DOI 是否存在，',
    '  並比對 AI 產出的作者/年份是否與 CrossRef 回傳的一致。',
    '  將結果整理成表格：DOI | 狀態 | AI作者 | 實際作者 | 匹配',
    '',
    '→ Claude Code 自動寫 Python 腳本 → 執行 → 回報結果',
  ].join("\n"));
  tipBox(s, 0.3, 4.6, 9.4, "Day 2 將深入 Claude Code：CLAUDE.md 撰寫 + Skills 系統 + Agents 協作 + Commands 工作流");
})();

// ──────────────────────────────────────────────────────────
// Slide 23: Day 1 實作練習 & 回顧
// ──────────────────────────────────────────────────────────
(() => {
  const s = contentSlide(pres, "Day 1 實作練習 & 回顧");
  // Left: Checklist
  infoCard(s, pres, 0.3, 0.9, 4.5, 3.0, "實作任務清單 (30 分鐘)", [
    "[ ] 1. 用 CARE 框架寫 3 個研究 Prompt",
    "[ ] 2. 與 AI 進行 5 輪漸進式對話",
    "[ ] 3. 用 AI 產出 10 個種子 DOI",
    "[ ] 4. 用 CrossRef API 驗證至少 3 個 DOI",
    "[ ] 5. 建立 3 篇 Obsidian 文獻筆記卡",
    "[ ] 6. 建立 references.bib (5+ 篇驗證引用)",
    "",
    "(進階) Semantic Scholar API 取 Abstract",
    "(進階) OpenAlex API 查 OA 狀態",
  ].join("\n"), C.teal);
  // Right: Skills covered
  infoCard(s, pres, 5.1, 0.9, 4.6, 3.0, "今日核心技能 (10 項)", [
    "1.  CARE Prompt 框架",
    "2.  漸進式縮焦法",
    "3.  Extended Thinking 指令",
    "4.  種子 DOI 生成",
    "5.  CrossRef API 驗證",
    "6.  Semantic Scholar / OpenAlex API",
    "7.  Zotero 批次匯入",
    "8.  Obsidian 筆記卡 + Graph View",
    "9.  BibTeX 引用管理",
    "10. Research Gap 識別",
  ].join("\n"), C.navy);
  // Homework
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 4.1, w: 9.4, h: 0.65, fill: { color: C.lightBlue } });
  s.addText("回家作業 (可選)：擴充文獻到 20 篇 | 完成 Research Gap 分析初稿 | 寫一份 1 頁研究方向說明", {
    x: 0.5, y: 4.1, w: 9.0, h: 0.65, fontSize: 11, color: C.navy, valign: "middle",
  });
  tipBox(s, 0.3, 4.95, 9.4, "Day 2 預告：IMRaD 架構 → QMD 撰寫 → 統計驗證 → 平行審查 → 投稿策略 → 帶走整套系統");
})();

// ──────────────────────────────────────────────────────────
// Slide 24: Day 1→2 過渡 — AI 工具生態系預覽
// ──────────────────────────────────────────────────────────
(() => {
  const s = pres.addSlide();
  s.background = { color: C.navy };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.12, h: 5.625, fill: { color: C.teal } });
  // Title
  s.addText("明天，你將擁有\n一個完整的 AI 研究團隊", { x: 0.5, y: 0.3, w: 9, h: 1.2, fontSize: 36, bold: true, color: C.white, lineSpacingMultiple: 1.15 });
  // 4 category boxes
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
  // Footer
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.2, w: 10, h: 0.425, fill: { color: C.teal, transparency: 70 } });
  s.addText("Day 2：從 AI 助教 升級為 AI 研究團隊 — 讓 8 個專家 Agent 各司其職", {
    x: 0.4, y: 5.2, w: 9.2, h: 0.425, fontSize: 11, color: C.white, valign: "middle", align: "center",
  });
})();

// ═══════════════════════════════════════════════════════════
// OUTPUT
// ═══════════════════════════════════════════════════════════
const outDir = "/Users/user/Desktop/NILM+LLM/NILM_LLM_SETA/05_outputs/2026-03-06_AI_Paper_Workshop";
pres.writeFile({ fileName: `${outDir}/Day1_AI研究基礎.pptx` })
  .then(() => console.log("Done! Day1_AI研究基礎.pptx generated."))
  .catch(console.error);
