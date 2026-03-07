const pptxgen = require("pptxgenjs");

const makeShadow = (opacity = 0.12) => ({
  type: "outer", color: "000000",
  blur: 6, offset: 3, angle: 135, opacity,
});

// ─── UNIFIED BRAND CONSTANTS (shared across ALL themes) ────
const BRAND = {
  secondary:  "0F9D8A",  // Emerald AI Green (unified)
  secLight:   "12B89F",
  secDark:    "0A7A6B",
  accent:     "FFC857",  // Highlight Yellow (unified)
  accDark:    "E6A820",
  white:      "FFFFFF",
  offwhite:   "F5F7FA",  // Background (unified)
  lightTint:  "E8F4F2",  // Tip box
  darkText:   "1A1A1A",  // Text (unified)
  grayText:   "5A6B7A",
  slate:      "2C3E50",
  mint:       "D4F0EB",
  orange:     "E07A3A",
};

// ─── 5 THEME DEFINITIONS ──────────────────────────────────
const themes = [
  {
    id: "paper",
    name: "AI x \u8ad6\u6587\u5de5\u4f5c\u574a",
    nameEn: "AI x Paper Workshop",
    primary:    "0B3C5D",  // Deep Academic Blue
    priLight:   "134B6E",
    priName:    "Deep Academic Blue",
    priHex:     "#0B3C5D",
    style:      "Nature / Science / Elsevier",
    subtitle:   "\u5f9e\u6982\u5ff5\u63a2\u7d22\u5230\u8ad6\u6587\u6295\u7a3f\u7684\u5b8c\u6574 AI \u5354\u4f5c\u6d41\u7a0b",
    tags: ["2 Days", "24 Skills", "8 Agents", "4 APIs"],
    cards: [
      { title: "\u6587\u737b\u8abf\u7814", items: "CrossRef API \u9a57\u8b49\nSemantic Scholar \u5206\u6790\nObsidian \u77e5\u8b58\u5716\u8b5c" },
      { title: "\u54c1\u8cea\u5be9\u67e5", items: "\u4e03\u7dad\u5ea6\u8a55\u5206\u6846\u67b6\nP0-P3 \u554f\u984c\u5206\u7d1a\nClaude\u00d7ChatGPT\u00d7Gemini" },
      { title: "\u6295\u7a3f\u6e96\u5099", items: "Cover Letter \u64b0\u5beb\n10 \u9805\u7d20\u6750\u6e05\u55ae\nRebuttal Matrix" },
    ],
    tip: "\u6240\u6709\u5f15\u7528\u5fc5\u9808\u7d93 API \u591a\u91cd\u9a57\u8b49\uff0c\u7d55\u4e0d\u76f2\u4fe1 AI \u7522\u51fa\u7684 DOI",
  },
  {
    id: "sustainability",
    name: "AI x \u6c38\u7e8c\u5de5\u4f5c\u574a",
    nameEn: "AI x Sustainability Workshop",
    primary:    "2D6A4F",  // Forest Sustainability Green (aligned w/ S100)
    priLight:   "3D8B6A",
    priName:    "Forest Sustainability Green",
    priHex:     "#2D6A4F",
    style:      "Climate Tech / UNEP / IPCC",
    subtitle:   "AI \u8ce6\u80fd ESG\u3001\u6de8\u96f6\u8f49\u578b\u8207\u80fd\u6e90\u7ba1\u7406",
    tags: ["2 Days", "ESG AI", "Net Zero", "CBAM"],
    cards: [
      { title: "\u78b3\u76e4\u67e5\u8207 AI", items: "\u7bc4\u7587 1/2/3 \u81ea\u52d5\u5316\nGHG Protocol \u5c0d\u63a5\nAI \u6578\u64da\u6e05\u6d17" },
      { title: "\u6de8\u96f6\u8def\u5f91\u898f\u5283", items: "SBTi \u76ee\u6a19\u8a2d\u5b9a\nAI \u60c5\u5883\u6a21\u64ec\n\u6e1b\u78b3\u512a\u5148\u5e8f" },
      { title: "ESG \u5831\u544a\u64b0\u5beb", items: "GRI/SASB/TCFD \u6846\u67b6\nAI \u8f14\u52a9\u62ab\u9732\n\u91cd\u5927\u6027\u5206\u6790" },
    ],
    tip: "\u78b3\u6392\u653e\u4fc2\u6578\u5fc5\u9808\u4f86\u81ea\u5b98\u65b9\u8cc7\u6599\u5eab\uff0cAI \u50c5\u8f14\u52a9\u8a08\u7b97\u8207\u5831\u544a\u751f\u6210",
  },
  {
    id: "general",
    name: "AI \u901a\u7528\u5de5\u4f5c\u574a",
    nameEn: "AI General Workshop",
    primary:    "1A2744",  // AI Core Blue (aligned w/ AI100)
    priLight:   "243556",
    priName:    "AI Core Blue",
    priHex:     "#1A2744",
    style:      "OpenAI / Google AI / Anthropic",
    subtitle:   "AI \u57fa\u790e\u3001\u5de5\u5177\u61c9\u7528\u8207 AI \u601d\u7dad\u57f9\u990a",
    tags: ["1 Day", "Prompt", "Agent", "MCP"],
    cards: [
      { title: "Prompt \u5de5\u7a0b", items: "Chain of Thought\nFew-shot Learning\n\u7d50\u69cb\u5316\u8f38\u51fa" },
      { title: "AI Agent \u5be6\u4f5c", items: "Claude Code CLI\nMCP \u5de5\u5177\u93c8\nMulti-Agent \u5354\u4f5c" },
      { title: "AI \u5de5\u4f5c\u6d41", items: "\u81ea\u52d5\u5316\u5834\u666f\u8a2d\u8a08\nAPI \u4e32\u63a5\u5be6\u4f5c\n\u6548\u7387\u8a55\u4f30\u6846\u67b6" },
    ],
    tip: "AI \u662f\u5354\u4f5c\u5925\u4f34\uff0c\u4e0d\u662f\u66ff\u4ee3\u65b9\u6848\u2014\u2014\u4eba\u985e\u5224\u65b7\u529b\u59cb\u7d42\u662f\u6700\u7d42\u6aa2\u6838\u9ede",
  },
  {
    id: "manufacturing",
    name: "AI x \u667a\u6167\u88fd\u9020\u5de5\u4f5c\u574a",
    nameEn: "AI x Smart Manufacturing",
    primary:    "374151",  // Industrial Graphite
    priLight:   "4B5563",
    priName:    "Industrial Graphite",
    priHex:     "#374151",
    style:      "Siemens / Bosch / Tesla Factory",
    subtitle:   "AI + Industry 4.0\u3001\u667a\u6167\u5de5\u5ee0\u8207\u751f\u7522\u512a\u5316",
    tags: ["2 Days", "Industry 4.0", "Digital Twin", "PHM"],
    cards: [
      { title: "\u9810\u6e2c\u6027\u7dad\u8b77", items: "\u632f\u52d5\u5206\u6790 AI\n\u6545\u969c\u9810\u6e2c\u6a21\u578b\nPHM \u7cfb\u7d71\u67b6\u69cb" },
      { title: "\u88fd\u7a0b\u512a\u5316", items: "SPC + AI \u7570\u5e38\u5075\u6e2c\n\u826f\u7387\u9810\u6e2c\u6a21\u578b\n\u53c3\u6578\u81ea\u52d5\u8abf\u6574" },
      { title: "Digital Twin", items: "\u865b\u5be6\u6574\u5408\u67b6\u69cb\nAI \u6a21\u64ec\u8207\u9a57\u8b49\n\u5373\u6642\u76e3\u63a7\u5100\u8868\u677f" },
    ],
    tip: "\u5de5\u5ee0\u6578\u64da\u5fc5\u9808\u7d93\u904e\u53bb\u8b58\u5225\u5316\u3001\u6b0a\u9650\u63a7\u5236\u5f8c\u624d\u80fd\u9935\u5165 AI \u6a21\u578b",
  },
  {
    id: "finance",
    name: "AI x \u7406\u8ca1\u5de5\u4f5c\u574a",
    nameEn: "AI x Finance Workshop",
    primary:    "0B3C5D",  // Finance Navy
    priLight:   "134B6E",
    priName:    "Finance Navy",
    priHex:     "#0B3C5D",
    style:      "Bloomberg / Goldman Sachs",
    subtitle:   "AI + \u6295\u8cc7\u5206\u6790\u3001FinTech \u8207\u98a8\u96aa\u7ba1\u7406",
    tags: ["1 Day", "FinTech", "Risk AI", "Quant"],
    cards: [
      { title: "\u667a\u80fd\u6295\u8cc7\u5206\u6790", items: "AI \u8cc7\u7522\u914d\u7f6e\n\u60c5\u5831\u7db2\u722a\u53d6\u5206\u6790\n\u591a\u56e0\u5b50\u6a21\u578b" },
      { title: "\u98a8\u96aa\u8a55\u4f30", items: "VaR/CVaR \u8a08\u7b97\nAI \u58d3\u529b\u6e2c\u8a66\n\u7570\u5e38\u4ea4\u6613\u5075\u6e2c" },
      { title: "FinTech \u5be6\u4f5c", items: "\u81ea\u52d5\u5316\u5831\u544a\u751f\u6210\n\u667a\u80fd\u5ba2\u670d\u6a5f\u5668\u4eba\nAPI \u4e32\u63a5\u91d1\u878d\u6578\u64da" },
    ],
    tip: "\u6295\u8cc7\u5efa\u8b70\u50c5\u4f9b\u53c3\u8003\uff0cAI \u7121\u6cd5\u66ff\u4ee3\u5c08\u696d\u8ca1\u52d9\u9867\u554f\u7684\u5224\u65b7",
  },
];

// ─── THEME-SPECIFIC PALETTE (for reference display) ───────
const themeSpecificPalettes = {
  paper:          { sec: "0F9D8A", secName: "Emerald AI Green",       acc: "FFC857", accName: "Highlight Yellow" },
  sustainability: { sec: "0F9D8A", secName: "Emerald AI Green",       acc: "FFC857", accName: "Energy Highlight Yellow" },
  general:        { sec: "7C3AED", secName: "AI Neural Purple",       acc: "06B6D4", accName: "Data Cyan" },
  manufacturing:  { sec: "2563EB", secName: "Robotics Blue",          acc: "F59E0B", accName: "Safety Orange" },
  finance:        { sec: "10B981", secName: "Profit Green",           acc: "D4AF37", accName: "Gold Insight" },
};

// ═══════════════════════════════════════════════════════════
// SLIDE BUILDERS
// ═══════════════════════════════════════════════════════════

function buildOverviewSlide(pres) {
  const s = pres.addSlide();
  s.background = { color: BRAND.offwhite };

  // Title bar
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 10, h: 0.7,
    fill: { color: BRAND.slate },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 10, h: 0.06, fill: { color: BRAND.accent },
  });
  s.addText("AI Workshop Brand System  |  \u54c1\u724c\u8996\u89ba\u9ad4\u7cfb\u7e3d\u89bd", {
    x: 0.4, y: 0.06, w: 9.2, h: 0.64,
    fontSize: 20, bold: true, color: BRAND.white,
    fontFace: "Calibri", valign: "middle",
  });

  // Strategy description
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.25, y: 0.9, w: 9.5, h: 0.55,
    fill: { color: BRAND.lightTint },
  });
  s.addText("\u7b56\u7565\uff1a\u53ea\u63db Primary Color\uff0c\u5176\u4ed6\u4fdd\u6301\u7d71\u4e00 \u2014 Secondary: Emerald AI Green  |  Accent: Highlight Yellow  |  Background + Text \u56fa\u5b9a", {
    x: 0.4, y: 0.9, w: 9.2, h: 0.55,
    fontSize: 11, color: BRAND.slate, valign: "middle", fontFace: "Calibri",
  });

  // 5 theme cards
  const cardW = 1.75;
  const cardH = 3.1;
  const startX = 0.25;
  const gap = 0.19;
  const cardY = 1.65;

  themes.forEach((t, i) => {
    const cx = startX + i * (cardW + gap);

    // Card bg
    s.addShape(pres.shapes.RECTANGLE, {
      x: cx, y: cardY, w: cardW, h: cardH,
      fill: { color: BRAND.white }, shadow: makeShadow(0.1),
    });
    // Primary color header
    s.addShape(pres.shapes.RECTANGLE, {
      x: cx, y: cardY, w: cardW, h: 0.85,
      fill: { color: t.primary },
    });
    // Gold top accent
    s.addShape(pres.shapes.RECTANGLE, {
      x: cx, y: cardY, w: cardW, h: 0.04,
      fill: { color: BRAND.accent },
    });
    // Theme name (Chinese)
    s.addText(t.name, {
      x: cx, y: cardY + 0.12, w: cardW, h: 0.35,
      fontSize: 11, bold: true, color: BRAND.white,
      align: "center", valign: "middle", fontFace: "Calibri",
    });
    // Theme name (English)
    s.addText(t.nameEn, {
      x: cx, y: cardY + 0.45, w: cardW, h: 0.3,
      fontSize: 7.5, color: BRAND.mint,
      align: "center", valign: "middle", fontFace: "Calibri",
    });

    // Primary color swatch
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: cx + 0.15, y: cardY + 1.0, w: cardW - 0.3, h: 0.35,
      fill: { color: t.primary }, rectRadius: 0.04,
    });
    s.addText(`${t.priHex}  ${t.priName}`, {
      x: cx + 0.15, y: cardY + 1.0, w: cardW - 0.3, h: 0.35,
      fontSize: 6.5, color: BRAND.white,
      align: "center", valign: "middle", fontFace: "Calibri",
    });

    // Secondary swatch (unified)
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: cx + 0.15, y: cardY + 1.45, w: cardW - 0.3, h: 0.28,
      fill: { color: BRAND.secondary }, rectRadius: 0.04,
    });
    s.addText("#0F9D8A  Emerald AI Green", {
      x: cx + 0.15, y: cardY + 1.45, w: cardW - 0.3, h: 0.28,
      fontSize: 6, color: BRAND.white,
      align: "center", valign: "middle", fontFace: "Calibri",
    });

    // Accent swatch (unified)
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: cx + 0.15, y: cardY + 1.83, w: cardW - 0.3, h: 0.28,
      fill: { color: BRAND.accent }, rectRadius: 0.04,
    });
    s.addText("#FFC857  Highlight Yellow", {
      x: cx + 0.15, y: cardY + 1.83, w: cardW - 0.3, h: 0.28,
      fontSize: 6, color: BRAND.slate,
      align: "center", valign: "middle", fontFace: "Calibri",
    });

    // Style reference
    s.addText(t.style, {
      x: cx + 0.1, y: cardY + 2.25, w: cardW - 0.2, h: 0.25,
      fontSize: 7, color: BRAND.grayText,
      align: "center", valign: "middle", fontFace: "Calibri", italic: true,
    });

    // Tags
    const tagStr = t.tags.join("  |  ");
    s.addText(tagStr, {
      x: cx + 0.05, y: cardY + 2.55, w: cardW - 0.1, h: 0.4,
      fontSize: 6.5, color: BRAND.secondary,
      align: "center", valign: "middle", fontFace: "Calibri",
    });
  });

  // Bottom nav
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 5.15, w: 10, h: 0.475,
    fill: { color: BRAND.slate },
  });
  // Unified palette strip
  const swatchColors = ["0B3C5D", "2D6A4F", "1A2744", "374151", "0F9D8A", "FFC857", "F5F7FA"];
  swatchColors.forEach((c, i) => {
    s.addShape(pres.shapes.OVAL, {
      x: 0.4 + i * 0.42, y: 5.33, w: 0.22, h: 0.22,
      fill: { color: c },
      line: { color: "FFFFFF", width: 1 },
    });
  });
  s.addText("AI Workshop Brand System  |  Primary \u8b8a\u5316 \u00d7 \u7d71\u4e00\u54c1\u724c\u611f", {
    x: 3.6, y: 5.15, w: 6.1, h: 0.475,
    fontSize: 9, color: BRAND.white, valign: "middle", fontFace: "Calibri",
  });
}

// ─── Individual Theme Sample Slide ────────────────────────
function buildThemeSample(pres, theme) {
  const pri = theme.primary;
  const priL = theme.priLight;
  const sec = BRAND.secondary;
  const acc = BRAND.accent;

  const s = pres.addSlide();
  s.background = { color: pri };

  // Top gold line (brand mark)
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 10, h: 0.08, fill: { color: acc },
  });
  // Left teal bar
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0.08, w: 0.12, h: 2.7, fill: { color: sec },
  });
  // Decorative circles
  s.addShape(pres.shapes.OVAL, {
    x: 7.2, y: -0.3, w: 3.2, h: 3.2,
    fill: { color: sec, transparency: 88 },
  });
  s.addShape(pres.shapes.OVAL, {
    x: 7.8, y: 0.4, w: 2.2, h: 2.2,
    fill: { color: acc, transparency: 85 },
  });

  // Title
  s.addText(theme.name, {
    x: 0.4, y: 0.25, w: 7, h: 0.8,
    fontSize: 30, bold: true, color: BRAND.white, fontFace: "Calibri",
  });
  // Subtitle
  s.addText(theme.subtitle, {
    x: 0.4, y: 1.05, w: 7, h: 0.4,
    fontSize: 13, color: acc, fontFace: "Calibri",
  });

  // Badge tags
  theme.tags.forEach((t, i) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 0.4 + i * 1.55, y: 1.55, w: 1.35, h: 0.32,
      fill: { color: acc }, rectRadius: 0.06,
    });
    s.addText(t, {
      x: 0.4 + i * 1.55, y: 1.55, w: 1.35, h: 0.32,
      fontSize: 10, bold: true, color: pri,
      align: "center", valign: "middle", margin: 0,
    });
  });

  // Transition accent
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 2.58, w: 10, h: 0.2,
    fill: { color: sec, transparency: 60 },
  });

  // ── CONTENT AREA ──
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 2.78, w: 10, h: 2.845,
    fill: { color: BRAND.offwhite },
  });
  // Title bar (secondary)
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 2.78, w: 10, h: 0.52,
    fill: { color: sec },
  });
  s.addText(`${theme.nameEn}  |  \u5167\u5bb9\u7bc4\u4f8b`, {
    x: 0.4, y: 2.78, w: 9.2, h: 0.52,
    fontSize: 16, bold: true, color: BRAND.white,
    valign: "middle", fontFace: "Calibri", margin: 0,
  });

  // 3 Info Cards
  const cardColors = [sec, BRAND.accDark, pri];
  const cardTitleColors = [BRAND.secDark, BRAND.accDark, pri];
  theme.cards.forEach((card, i) => {
    const cx = 0.25 + i * 3.25;
    // Card bg
    s.addShape(pres.shapes.RECTANGLE, {
      x: cx, y: 3.5, w: 3.0, h: 1.2,
      fill: { color: BRAND.white }, shadow: makeShadow(0.1),
    });
    // Left accent bar
    s.addShape(pres.shapes.RECTANGLE, {
      x: cx, y: 3.5, w: 0.07, h: 1.2,
      fill: { color: cardColors[i] },
    });
    // Card title
    s.addText(card.title, {
      x: cx + 0.15, y: 3.55, w: 2.7, h: 0.28,
      fontSize: 12, bold: true, color: cardTitleColors[i], margin: 0,
    });
    // Card content
    s.addText(card.items, {
      x: cx + 0.15, y: 3.85, w: 2.7, h: 0.75,
      fontSize: 10, color: BRAND.darkText, margin: 0, lineSpacingMultiple: 1.25,
    });
  });

  // Tip box
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.25, y: 4.9, w: 9.5, h: 0.42,
    fill: { color: BRAND.lightTint },
  });
  s.addText(`\u2728 \u63d0\u793a\uff1a${theme.tip}`, {
    x: 0.4, y: 4.9, w: 9.2, h: 0.42,
    fontSize: 11, color: pri, valign: "middle", margin: 0,
  });

  // Bottom nav
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 5.4, w: 10, h: 0.225,
    fill: { color: pri },
  });
  s.addShape(pres.shapes.OVAL, {
    x: 0.3, y: 5.46, w: 0.1, h: 0.1,
    fill: { color: acc },
  });

  // Palette reference in nav
  const sp = themeSpecificPalettes[theme.id];
  s.addText(
    `${theme.priHex}  ${theme.priName}  |  #0F9D8A  Emerald AI Green  |  #FFC857  Highlight Yellow  |  \u7368\u7acb\u914d\u8272: #${sp.sec} ${sp.secName} + #${sp.acc} ${sp.accName}`,
    {
      x: 0.55, y: 5.4, w: 9.15, h: 0.225,
      fontSize: 7.5, color: BRAND.white, valign: "middle", margin: 0, fontFace: "Calibri",
    }
  );
}

// ─── Strategy Summary Slide ──────────────────────────────
function buildStrategySummary(pres) {
  const s = pres.addSlide();
  s.background = { color: BRAND.slate };

  // Gold top line
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 10, h: 0.08, fill: { color: BRAND.accent },
  });
  // Teal left bar
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0.08, w: 0.12, h: 5.545, fill: { color: BRAND.secondary },
  });

  s.addText("\u570b\u969b\u7814\u7a76\u71df\u7b49\u7d1a\u54c1\u724c\u7b56\u7565", {
    x: 0.4, y: 0.25, w: 9, h: 0.7,
    fontSize: 32, bold: true, color: BRAND.white, fontFace: "Calibri",
  });
  s.addText("International Research Camp Brand Strategy", {
    x: 0.4, y: 0.9, w: 9, h: 0.4,
    fontSize: 15, color: BRAND.accent, fontFace: "Calibri",
  });

  // Strategy box
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.4, y: 1.5, w: 9.2, h: 3.6,
    fill: { color: BRAND.white, transparency: 8 },
  });

  // Rule: Only swap Primary
  const rules = [
    { label: "\u7d71\u4e00\u5143\u7d20", value: "Secondary + Accent + Background + Text", color: BRAND.secondary },
    { label: "\u8b8a\u5316\u5143\u7d20", value: "\u50c5 Primary Color\uff08\u4e3b\u984c\u8b58\u5225\uff09", color: BRAND.accent },
  ];
  rules.forEach((r, i) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 0.65, y: 1.7 + i * 0.55, w: 1.6, h: 0.38,
      fill: { color: r.color }, rectRadius: 0.06,
    });
    s.addText(r.label, {
      x: 0.65, y: 1.7 + i * 0.55, w: 1.6, h: 0.38,
      fontSize: 10, bold: true, color: BRAND.slate,
      align: "center", valign: "middle", fontFace: "Calibri",
    });
    s.addText(r.value, {
      x: 2.4, y: 1.7 + i * 0.55, w: 7, h: 0.38,
      fontSize: 11, color: BRAND.white, valign: "middle", fontFace: "Calibri",
    });
  });

  // Benefits
  const benefits = [
    "\u98a8\u683c\u4e00\u81f4 \u2014 \u6240\u6709\u8ab2\u7a0b\u770b\u8d77\u4f86\u662f\u540c\u4e00\u54c1\u724c",
    "\u4e3b\u984c\u660e\u78ba \u2014 \u6bcf\u9580\u8ab2\u7a0b\u90fd\u6709\u7368\u7acb\u8fa8\u8b58\u5ea6",
    "\u88fd\u4f5c\u5feb\u901f \u2014 \u53ea\u63db Primary\uff0c\u7c21\u5831\u7522\u51fa\u901f\u5ea6\u6975\u5feb",
    "\u54c1\u724c\u6e05\u6670 \u2014 \u5c08\u696d\u5ea6\u5f37\uff0c\u9069\u5408\u570b\u969b\u7814\u7a76\u71df\u7b49\u7d1a",
  ];
  benefits.forEach((b, i) => {
    s.addShape(pres.shapes.OVAL, {
      x: 0.75, y: 2.98 + i * 0.45, w: 0.14, h: 0.14,
      fill: { color: BRAND.accent },
    });
    s.addText(b, {
      x: 1.05, y: 2.9 + i * 0.45, w: 8.3, h: 0.35,
      fontSize: 12, color: BRAND.white, valign: "middle", fontFace: "Calibri",
    });
  });

  // Color strip at bottom
  const primaries = [
    { color: "0B3C5D", label: "\u8ad6\u6587" },
    { color: "2D6A4F", label: "\u6c38\u7e8c" },
    { color: "1A2744", label: "\u901a\u7528" },
    { color: "374151", label: "\u88fd\u9020" },
    { color: "0B3C5D", label: "\u7406\u8ca1" },
  ];
  const stripY = 4.65;
  const stripW = 1.6;
  const stripGap = 0.25;
  const stripStartX = (10 - (primaries.length * stripW + (primaries.length - 1) * stripGap)) / 2;

  primaries.forEach((p, i) => {
    const sx = stripStartX + i * (stripW + stripGap);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: sx, y: stripY, w: stripW, h: 0.55,
      fill: { color: p.color }, rectRadius: 0.06,
    });
    s.addText(p.label, {
      x: sx, y: stripY, w: stripW, h: 0.55,
      fontSize: 12, bold: true, color: BRAND.white,
      align: "center", valign: "middle", fontFace: "Calibri",
    });
  });

  // Bottom bar
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 5.4, w: 10, h: 0.225,
    fill: { color: "111827" },
  });
  s.addText("AI Workshop Brand System  |  \u7d71\u4e00\u54c1\u724c x \u4e3b\u984c\u5dee\u7570 = \u570b\u969b\u7814\u7a76\u71df\u7b49\u7d1a", {
    x: 0.4, y: 5.4, w: 9.2, h: 0.225,
    fontSize: 9, color: BRAND.white, valign: "middle", fontFace: "Calibri",
  });
}

// ─── Comparison Slide: Unified vs Theme-Specific ─────────
function buildComparisonSlide(pres) {
  const s = pres.addSlide();
  s.background = { color: BRAND.offwhite };

  // Title bar
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 10, h: 0.6,
    fill: { color: BRAND.secondary },
  });
  s.addText("\u7d71\u4e00\u54c1\u724c vs \u4e3b\u984c\u5c08\u5c6c\u914d\u8272\u5c0d\u7167", {
    x: 0.4, y: 0, w: 9.2, h: 0.6,
    fontSize: 18, bold: true, color: BRAND.white,
    valign: "middle", fontFace: "Calibri",
  });

  // Table header
  const colX = [0.3, 2.0, 3.7, 5.2, 6.8, 8.3];
  const colW = [1.5, 1.5, 1.3, 1.4, 1.3, 1.5];
  const headers = ["\u8ab2\u7a0b", "Primary", "Secondary\n(\u7d71\u4e00)", "Accent\n(\u7d71\u4e00)", "Secondary\n(\u5c08\u5c6c)", "Accent\n(\u5c08\u5c6c)"];
  const hY = 0.85;

  headers.forEach((h, i) => {
    s.addShape(pres.shapes.RECTANGLE, {
      x: colX[i], y: hY, w: colW[i], h: 0.45,
      fill: { color: BRAND.slate },
    });
    s.addText(h, {
      x: colX[i], y: hY, w: colW[i], h: 0.45,
      fontSize: 8.5, bold: true, color: BRAND.white,
      align: "center", valign: "middle", fontFace: "Calibri",
    });
  });

  // Table rows
  themes.forEach((t, i) => {
    const ry = hY + 0.45 + i * 0.75;
    const sp = themeSpecificPalettes[t.id];
    const rowBg = i % 2 === 0 ? BRAND.white : BRAND.offwhite;

    // Row background
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.3, y: ry, w: 9.5, h: 0.75,
      fill: { color: rowBg },
    });

    // Course name
    s.addText(`${t.name}\n${t.nameEn}`, {
      x: colX[0], y: ry, w: colW[0], h: 0.75,
      fontSize: 8, color: BRAND.darkText,
      align: "center", valign: "middle", fontFace: "Calibri",
    });

    // Primary swatch
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: colX[1] + 0.15, y: ry + 0.1, w: colW[1] - 0.3, h: 0.32,
      fill: { color: t.primary }, rectRadius: 0.04,
    });
    s.addText(`#${t.primary}`, {
      x: colX[1], y: ry + 0.1, w: colW[1], h: 0.32,
      fontSize: 7.5, color: BRAND.white, align: "center", valign: "middle",
    });
    s.addText(t.priName, {
      x: colX[1], y: ry + 0.45, w: colW[1], h: 0.25,
      fontSize: 6.5, color: BRAND.grayText, align: "center", valign: "middle",
    });

    // Unified secondary
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: colX[2] + 0.1, y: ry + 0.15, w: colW[2] - 0.2, h: 0.28,
      fill: { color: BRAND.secondary }, rectRadius: 0.04,
    });
    s.addText("#0F9D8A", {
      x: colX[2], y: ry + 0.15, w: colW[2], h: 0.28,
      fontSize: 7, color: BRAND.white, align: "center", valign: "middle",
    });

    // Unified accent
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: colX[3] + 0.1, y: ry + 0.15, w: colW[3] - 0.2, h: 0.28,
      fill: { color: BRAND.accent }, rectRadius: 0.04,
    });
    s.addText("#FFC857", {
      x: colX[3], y: ry + 0.15, w: colW[3], h: 0.28,
      fontSize: 7, color: BRAND.slate, align: "center", valign: "middle",
    });

    // Theme-specific secondary
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: colX[4] + 0.1, y: ry + 0.15, w: colW[4] - 0.2, h: 0.28,
      fill: { color: sp.sec }, rectRadius: 0.04,
    });
    s.addText(`#${sp.sec}`, {
      x: colX[4], y: ry + 0.15, w: colW[4], h: 0.28,
      fontSize: 7, color: BRAND.white, align: "center", valign: "middle",
    });

    // Theme-specific accent
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: colX[5] + 0.1, y: ry + 0.15, w: colW[5] - 0.2, h: 0.28,
      fill: { color: sp.acc }, rectRadius: 0.04,
    });
    s.addText(`#${sp.acc}`, {
      x: colX[5], y: ry + 0.15, w: colW[5], h: 0.28,
      fontSize: 7, color: sp.acc === "D4AF37" || sp.acc === "F59E0B" || sp.acc === "FFC857" ? BRAND.slate : BRAND.white,
      align: "center", valign: "middle",
    });
  });

  // Bottom note
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.3, y: 5.0, w: 9.4, h: 0.35,
    fill: { color: BRAND.lightTint },
  });
  s.addText("\u5efa\u8b70\u63a1\u7528\u300c\u7d71\u4e00\u54c1\u724c\u300d\u6b04\uff08Secondary + Accent \u56fa\u5b9a\uff09\uff0c\u5c08\u5c6c\u914d\u8272\u53ef\u4f5c\u70ba\u5404\u8ab2\u7a0b\u7684\u9032\u968e\u5ef6\u4f38\u8272", {
    x: 0.45, y: 5.0, w: 9.1, h: 0.35,
    fontSize: 9.5, color: BRAND.slate, valign: "middle", fontFace: "Calibri",
  });

  // Bottom nav
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 5.4, w: 10, h: 0.225,
    fill: { color: BRAND.slate },
  });
  s.addText("AI Workshop Brand System  |  Color Comparison Reference", {
    x: 0.4, y: 5.4, w: 9.2, h: 0.225,
    fontSize: 9, color: BRAND.white, valign: "middle", fontFace: "Calibri",
  });
}

// ─── Website Color Analysis Slide ─────────────────────────
function buildWebsiteAnalysis(pres) {
  const s = pres.addSlide();
  s.background = { color: BRAND.offwhite };

  // Title bar
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 10, h: 0.6,
    fill: { color: BRAND.slate },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 10, h: 0.05, fill: { color: BRAND.accent },
  });
  s.addText("\u7db2\u7ad9\u914d\u8272\u5206\u6790  |  cooperation.tw \u00d7 AI100 \u00d7 S100", {
    x: 0.4, y: 0.05, w: 9.2, h: 0.55,
    fontSize: 18, bold: true, color: BRAND.white,
    valign: "middle", fontFace: "Calibri",
  });

  // 3 website cards
  const sites = [
    {
      name: "cooperation.tw",
      desc: "\u6bcd\u54c1\u724c\u5b98\u7db2",
      style: "Dark Mode \u79d1\u6280\u611f",
      colors: [
        { hex: "0C0F14", label: "bg", textColor: BRAND.white },
        { hex: "12161E", label: "bg2", textColor: BRAND.white },
        { hex: "4A9EFF", label: "blue", textColor: BRAND.white },
        { hex: "9B7AFF", label: "purple", textColor: BRAND.white },
        { hex: "F0F2F5", label: "text", textColor: BRAND.slate },
      ],
    },
    {
      name: "AI 100 \u8b1b",
      desc: "AI \u901a\u8b58\u8ab2\u7a0b",
      style: "Dark Mode \u8cc7\u8a0a\u5bc6\u96c6",
      colors: [
        { hex: "0F172A", label: "bg", textColor: BRAND.white },
        { hex: "1E293B", label: "card", textColor: BRAND.white },
        { hex: "06B6D4", label: "cyan", textColor: BRAND.white },
        { hex: "8B5CF6", label: "purple", textColor: BRAND.white },
        { hex: "F59E0B", label: "amber", textColor: BRAND.slate },
      ],
    },
    {
      name: "S100 \u6c38\u7e8c 100 \u8b1b",
      desc: "ESG \u6c38\u7e8c\u8ab2\u7a0b",
      style: "Light Mode \u81ea\u7136\u6e05\u65b0",
      colors: [
        { hex: "1B4332", label: "deep", textColor: BRAND.white },
        { hex: "2D6A4F", label: "green", textColor: BRAND.white },
        { hex: "1B4965", label: "blue", textColor: BRAND.white },
        { hex: "F9A825", label: "gold", textColor: BRAND.slate },
        { hex: "F0F7F4", label: "bg", textColor: BRAND.grayText },
      ],
    },
  ];

  sites.forEach((site, si) => {
    const cx = 0.25 + si * 3.25;
    const cy = 0.82;

    // Card
    s.addShape(pres.shapes.RECTANGLE, {
      x: cx, y: cy, w: 3.0, h: 2.65,
      fill: { color: BRAND.white }, shadow: makeShadow(0.1),
    });
    // Left accent
    s.addShape(pres.shapes.RECTANGLE, {
      x: cx, y: cy, w: 0.06, h: 2.65,
      fill: { color: site.colors[2].hex },
    });
    // Site name
    s.addText(site.name, {
      x: cx + 0.15, y: cy + 0.08, w: 2.7, h: 0.3,
      fontSize: 12, bold: true, color: BRAND.darkText, fontFace: "Calibri",
    });
    s.addText(`${site.desc}  |  ${site.style}`, {
      x: cx + 0.15, y: cy + 0.35, w: 2.7, h: 0.22,
      fontSize: 8, color: BRAND.grayText, fontFace: "Calibri",
    });
    // Color swatches
    site.colors.forEach((c, ci) => {
      const sy = cy + 0.7 + ci * 0.38;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
        x: cx + 0.15, y: sy, w: 2.7, h: 0.3,
        fill: { color: c.hex }, rectRadius: 0.04,
      });
      s.addText(`#${c.hex}  ${c.label}`, {
        x: cx + 0.15, y: sy, w: 2.7, h: 0.3,
        fontSize: 8, color: c.textColor,
        align: "center", valign: "middle", fontFace: "Calibri",
      });
    });
  });

  // Key findings section
  const findY = 3.7;
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.25, y: findY, w: 9.5, h: 0.4,
    fill: { color: BRAND.secondary },
  });
  s.addText("\u95dc\u9375\u767c\u73fe", {
    x: 0.4, y: findY, w: 9.2, h: 0.4,
    fontSize: 14, bold: true, color: BRAND.white,
    valign: "middle", fontFace: "Calibri",
  });

  const findings = [
    "cooperation.tw \u8207 AI100 \u90fd\u63a1\u7528 Dark Mode\uff0c\u5171\u4eab Blue + Purple \u96d9\u8272\u7cfb\u7d71",
    "S100 \u7368\u7acb\u63a1\u7528 Light Mode\uff0c\u68ee\u6797\u7da0 #2D6A4F \u70ba\u4e3b\u8272\uff0c\u8207\u300cAI x \u6c38\u7e8c\u300d\u5de5\u4f5c\u574a\u9ad8\u5ea6\u4e00\u81f4",
    "AI100 \u7684 Cyan #06B6D4 \u8207 Amber #F59E0B \u2192 Workshop \u7684 Teal #0F9D8A \u8207 Gold #FFC857 \u540c\u8272\u57df",
  ];
  findings.forEach((f, i) => {
    s.addShape(pres.shapes.OVAL, {
      x: 0.4, y: findY + 0.55 + i * 0.32, w: 0.1, h: 0.1,
      fill: { color: BRAND.accent },
    });
    s.addText(f, {
      x: 0.6, y: findY + 0.48 + i * 0.32, w: 9, h: 0.28,
      fontSize: 9, color: BRAND.darkText, valign: "middle", fontFace: "Calibri",
    });
  });

  // Bottom nav
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 5.4, w: 10, h: 0.225,
    fill: { color: BRAND.slate },
  });
  s.addText("Website Color Extraction  |  cooperation.tw \u00d7 ai100 \u00d7 sustainability-100", {
    x: 0.4, y: 5.4, w: 9.2, h: 0.225,
    fontSize: 9, color: BRAND.white, valign: "middle", fontFace: "Calibri",
  });
}

// ─── Website ↔ Workshop Alignment Slide ──────────────────
function buildAlignmentSlide(pres) {
  const s = pres.addSlide();
  s.background = { color: BRAND.offwhite };

  // Title bar
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 10, h: 0.6,
    fill: { color: BRAND.slate },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 10, h: 0.05, fill: { color: BRAND.accent },
  });
  s.addText("\u7db2\u7ad9 \u2194 \u7c21\u5831\u54c1\u724c\u5c0d\u9f4a  |  \u5fae\u8abf\u5f8c\u7d50\u679c", {
    x: 0.4, y: 0.05, w: 9.2, h: 0.55,
    fontSize: 18, bold: true, color: BRAND.white,
    valign: "middle", fontFace: "Calibri",
  });

  // Alignment table
  const rows = [
    {
      site: "cooperation.tw",   siteColor: "0C0F14",
      arrow: "\u2194",
      ws: "AI x \u8ad6\u6587", wsColor: "0B3C5D",
      note: "\u6df1\u8272\u57df\u5171\u9cf4\uff0c\u8ad6\u6587\u504f\u85cd\u3001\u5b98\u7db2\u504f\u9ed1",
    },
    {
      site: "AI100",            siteColor: "0F172A",
      arrow: "\u2248",
      ws: "AI \u901a\u7528",     wsColor: "1A2744",
      note: "\u5fae\u8abf\u5f8c #1A2744 \u8207 AI100 #0F172A \u540c\u8272\u57df",
    },
    {
      site: "S100",             siteColor: "2D6A4F",
      arrow: "=",
      ws: "AI x \u6c38\u7e8c",  wsColor: "2D6A4F",
      note: "\u5b8c\u7f8e\u5c0d\u9f4a\uff01\u5fae\u8abf\u5f8c #2D6A4F \u5b8c\u5168\u4e00\u81f4",
    },
    {
      site: "(\u7121\u5c0d\u61c9\u7db2\u7ad9)",  siteColor: "6B7280",
      arrow: "\u2014",
      ws: "AI x \u88fd\u9020",  wsColor: "374151",
      note: "Industrial Graphite \u7368\u7acb\u8b58\u5225\u8272",
    },
    {
      site: "(\u7121\u5c0d\u61c9\u7db2\u7ad9)",  siteColor: "6B7280",
      arrow: "\u2014",
      ws: "AI x \u7406\u8ca1",  wsColor: "0B3C5D",
      note: "\u8207\u8ad6\u6587\u5171\u7528 Finance Navy",
    },
  ];

  const tblY = 0.85;
  // Header
  const hdrCols = [
    { x: 0.3, w: 1.6, text: "\u7db2\u7ad9" },
    { x: 1.9, w: 1.5, text: "\u7db2\u7ad9\u4e3b\u8272" },
    { x: 3.4, w: 0.5, text: "" },
    { x: 3.9, w: 1.4, text: "Workshop" },
    { x: 5.3, w: 1.5, text: "Workshop \u4e3b\u8272" },
    { x: 6.8, w: 3.0, text: "\u5c0d\u9f4a\u8aaa\u660e" },
  ];
  hdrCols.forEach((h) => {
    s.addShape(pres.shapes.RECTANGLE, {
      x: h.x, y: tblY, w: h.w, h: 0.4,
      fill: { color: BRAND.slate },
    });
    if (h.text) {
      s.addText(h.text, {
        x: h.x, y: tblY, w: h.w, h: 0.4,
        fontSize: 9, bold: true, color: BRAND.white,
        align: "center", valign: "middle", fontFace: "Calibri",
      });
    }
  });

  rows.forEach((r, i) => {
    const ry = tblY + 0.4 + i * 0.6;
    const bg = i % 2 === 0 ? BRAND.white : BRAND.offwhite;

    // Row bg
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.3, y: ry, w: 9.5, h: 0.6,
      fill: { color: bg },
    });

    // Site name
    s.addText(r.site, {
      x: 0.3, y: ry, w: 1.6, h: 0.6,
      fontSize: 9, color: BRAND.darkText,
      align: "center", valign: "middle", fontFace: "Calibri",
    });

    // Site color swatch
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 2.05, y: ry + 0.1, w: 1.2, h: 0.25,
      fill: { color: r.siteColor }, rectRadius: 0.04,
    });
    s.addText(`#${r.siteColor}`, {
      x: 2.05, y: ry + 0.1, w: 1.2, h: 0.25,
      fontSize: 7, color: BRAND.white,
      align: "center", valign: "middle",
    });

    // Arrow
    s.addText(r.arrow, {
      x: 3.4, y: ry, w: 0.5, h: 0.6,
      fontSize: 14, bold: true, color: BRAND.secondary,
      align: "center", valign: "middle",
    });

    // Workshop name
    s.addText(r.ws, {
      x: 3.9, y: ry, w: 1.4, h: 0.6,
      fontSize: 9, color: BRAND.darkText,
      align: "center", valign: "middle", fontFace: "Calibri",
    });

    // Workshop color swatch
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 5.45, y: ry + 0.1, w: 1.2, h: 0.25,
      fill: { color: r.wsColor }, rectRadius: 0.04,
    });
    s.addText(`#${r.wsColor}`, {
      x: 5.45, y: ry + 0.1, w: 1.2, h: 0.25,
      fontSize: 7, color: BRAND.white,
      align: "center", valign: "middle",
    });

    // Note
    s.addText(r.note, {
      x: 6.8, y: ry, w: 3.0, h: 0.6,
      fontSize: 8, color: BRAND.grayText,
      valign: "middle", fontFace: "Calibri",
    });
  });

  // Shared color domain section
  const shY = 4.2;
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.25, y: shY, w: 9.5, h: 0.4,
    fill: { color: BRAND.secondary },
  });
  s.addText("\u5171\u4eab\u8272\u57df\uff1a\u7db2\u7ad9 \u2194 Workshop \u7684\u6a4b\u63a5\u8272", {
    x: 0.4, y: shY, w: 9.2, h: 0.4,
    fontSize: 13, bold: true, color: BRAND.white,
    valign: "middle", fontFace: "Calibri",
  });

  // Shared color pairs
  const pairs = [
    { domain: "Cyan / Teal", site: "06B6D4", sLabel: "AI100 Cyan", ws: "0F9D8A", wLabel: "Workshop Teal" },
    { domain: "Amber / Gold", site: "F59E0B", sLabel: "AI100 Amber", ws: "FFC857", wLabel: "Workshop Gold" },
    { domain: "Forest Green", site: "2D6A4F", sLabel: "S100 Green",  ws: "2D6A4F", wLabel: "\u6c38\u7e8c Primary" },
    { domain: "Deep Dark",   site: "0F172A", sLabel: "AI100 Deep",  ws: "1A2744", wLabel: "\u901a\u7528 Primary" },
  ];

  pairs.forEach((p, i) => {
    const px = 0.35 + i * 2.38;
    const py = shY + 0.55;

    // Domain label
    s.addText(p.domain, {
      x: px, y: py, w: 2.2, h: 0.22,
      fontSize: 8, bold: true, color: BRAND.darkText,
      align: "center", fontFace: "Calibri",
    });

    // Site swatch
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: px, y: py + 0.25, w: 1.0, h: 0.28,
      fill: { color: p.site }, rectRadius: 0.04,
    });
    s.addText(p.sLabel, {
      x: px, y: py + 0.25, w: 1.0, h: 0.28,
      fontSize: 6.5, color: p.site === "F59E0B" ? BRAND.slate : BRAND.white,
      align: "center", valign: "middle",
    });

    // Arrow
    s.addText("\u2192", {
      x: px + 1.0, y: py + 0.25, w: 0.2, h: 0.28,
      fontSize: 10, color: BRAND.grayText, align: "center", valign: "middle",
    });

    // Workshop swatch
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: px + 1.2, y: py + 0.25, w: 1.0, h: 0.28,
      fill: { color: p.ws }, rectRadius: 0.04,
    });
    s.addText(p.wLabel, {
      x: px + 1.2, y: py + 0.25, w: 1.0, h: 0.28,
      fontSize: 6.5, color: p.ws === "FFC857" ? BRAND.slate : BRAND.white,
      align: "center", valign: "middle",
    });
  });

  // Bottom nav
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 5.4, w: 10, h: 0.225,
    fill: { color: BRAND.slate },
  });
  s.addText("Website \u2194 Workshop Alignment  |  \u5fae\u8abf\u5f8c\u7d50\u679c\uff1aAI \u901a\u7528 #1A2744 + AI \u6c38\u7e8c #2D6A4F", {
    x: 0.4, y: 5.4, w: 9.2, h: 0.225,
    fontSize: 9, color: BRAND.white, valign: "middle", fontFace: "Calibri",
  });
}

// ─── Two-Layer Architecture Slide ────────────────────────
function buildArchitectureSlide(pres) {
  const s = pres.addSlide();
  s.background = { color: "0C0F14" };  // cooperation.tw bg

  // Gold top line
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 10, h: 0.08, fill: { color: BRAND.accent },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0.08, w: 0.12, h: 5.545, fill: { color: BRAND.secondary },
  });

  s.addText("\u5169\u5c64\u54c1\u724c\u67b6\u69cb", {
    x: 0.4, y: 0.25, w: 9, h: 0.7,
    fontSize: 32, bold: true, color: BRAND.white, fontFace: "Calibri",
  });
  s.addText("Layer 1: \u7db2\u7ad9 (Dark Mode)  \u00d7  Layer 2: \u7c21\u5831/\u6559\u6750 (Light/Dark \u6df7\u5408)", {
    x: 0.4, y: 0.9, w: 9, h: 0.4,
    fontSize: 14, color: BRAND.accent, fontFace: "Calibri",
  });

  // Layer 1: Website
  const l1Y = 1.55;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.4, y: l1Y, w: 4.3, h: 2.8,
    fill: { color: "12161E" }, rectRadius: 0.1,
    line: { color: "4A9EFF", width: 1.5 },
  });
  s.addText("Layer 1: \u7db2\u7ad9\u54c1\u724c", {
    x: 0.6, y: l1Y + 0.1, w: 3.9, h: 0.35,
    fontSize: 13, bold: true, color: "4A9EFF", fontFace: "Calibri",
  });
  s.addText("Dark Mode \u79d1\u6280\u611f", {
    x: 0.6, y: l1Y + 0.4, w: 3.9, h: 0.25,
    fontSize: 9, color: "8A9BB0", fontFace: "Calibri",
  });

  // Website items
  const webItems = [
    { name: "cooperation.tw", color: "0C0F14", accent: "4A9EFF" },
    { name: "AI 100 \u8b1b",     color: "0F172A", accent: "06B6D4" },
    { name: "S100 \u6c38\u7e8c",   color: "2D6A4F", accent: "F9A825" },
  ];
  webItems.forEach((w, i) => {
    const wy = l1Y + 0.8 + i * 0.6;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 0.7, y: wy, w: 3.8, h: 0.45,
      fill: { color: w.color }, rectRadius: 0.06,
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.7, y: wy, w: 0.06, h: 0.45,
      fill: { color: w.accent },
    });
    s.addText(w.name, {
      x: 0.9, y: wy, w: 2.0, h: 0.45,
      fontSize: 10, bold: true, color: BRAND.white,
      valign: "middle", fontFace: "Calibri",
    });
    s.addText(`#${w.color}`, {
      x: 3.2, y: wy, w: 1.2, h: 0.45,
      fontSize: 8, color: "8A9BB0",
      align: "right", valign: "middle", fontFace: "Calibri",
    });
  });

  // Arrow between layers
  s.addText("\u2194", {
    x: 4.7, y: 2.5, w: 0.6, h: 0.5,
    fontSize: 24, bold: true, color: BRAND.accent,
    align: "center", valign: "middle",
  });
  s.addText("\u5171\u4eab\u8272\u57df", {
    x: 4.55, y: 3.0, w: 0.9, h: 0.3,
    fontSize: 8, color: BRAND.grayText, align: "center", fontFace: "Calibri",
  });

  // Layer 2: Workshop
  const l2Y = 1.55;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 5.3, y: l2Y, w: 4.3, h: 2.8,
    fill: { color: BRAND.offwhite }, rectRadius: 0.1,
    line: { color: BRAND.secondary, width: 1.5 },
  });
  s.addText("Layer 2: \u7c21\u5831/\u6559\u6750\u54c1\u724c", {
    x: 5.5, y: l2Y + 0.1, w: 3.9, h: 0.35,
    fontSize: 13, bold: true, color: BRAND.secondary, fontFace: "Calibri",
  });
  s.addText("\u53ea\u63db Primary\uff0c\u5176\u4ed6\u7d71\u4e00", {
    x: 5.5, y: l2Y + 0.4, w: 3.9, h: 0.25,
    fontSize: 9, color: BRAND.grayText, fontFace: "Calibri",
  });

  const wsItems = [
    { name: "AI x \u8ad6\u6587",  color: "0B3C5D" },
    { name: "AI x \u6c38\u7e8c",  color: "2D6A4F" },
    { name: "AI \u901a\u7528",    color: "1A2744" },
    { name: "AI x \u88fd\u9020",  color: "374151" },
    { name: "AI x \u7406\u8ca1",  color: "0B3C5D" },
  ];
  wsItems.forEach((w, i) => {
    const wy = l2Y + 0.75 + i * 0.38;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 5.6, y: wy, w: 3.8, h: 0.3,
      fill: { color: w.color }, rectRadius: 0.04,
    });
    s.addText(w.name, {
      x: 5.75, y: wy, w: 1.8, h: 0.3,
      fontSize: 9, bold: true, color: BRAND.white,
      valign: "middle", fontFace: "Calibri",
    });
    s.addText(`#${w.color}`, {
      x: 8.0, y: wy, w: 1.3, h: 0.3,
      fontSize: 7.5, color: BRAND.mint,
      align: "right", valign: "middle", fontFace: "Calibri",
    });
  });

  // Bottom unified strip
  const bY = 4.65;
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.4, y: bY, w: 9.2, h: 0.45,
    fill: { color: "181D28" },
  });
  s.addText("\u7d71\u4e00\u5143\u7d20\uff1a", {
    x: 0.55, y: bY, w: 1.0, h: 0.45,
    fontSize: 9, bold: true, color: BRAND.white, valign: "middle", fontFace: "Calibri",
  });
  const unifiedSwatches = [
    { color: BRAND.secondary, label: "Secondary #0F9D8A" },
    { color: BRAND.accent, label: "Accent #FFC857", textColor: BRAND.slate },
    { color: BRAND.offwhite, label: "BG #F5F7FA", textColor: BRAND.grayText },
    { color: BRAND.darkText, label: "Text #1A1A1A" },
  ];
  unifiedSwatches.forEach((u, i) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 1.65 + i * 2.0, y: bY + 0.08, w: 1.8, h: 0.28,
      fill: { color: u.color }, rectRadius: 0.04,
    });
    s.addText(u.label, {
      x: 1.65 + i * 2.0, y: bY + 0.08, w: 1.8, h: 0.28,
      fontSize: 7.5, color: u.textColor || BRAND.white,
      align: "center", valign: "middle", fontFace: "Calibri",
    });
  });

  // Bottom nav
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 5.4, w: 10, h: 0.225,
    fill: { color: "0C0F14" },
  });
  s.addShape(pres.shapes.OVAL, {
    x: 0.3, y: 5.46, w: 0.1, h: 0.1,
    fill: { color: BRAND.accent },
  });
  s.addText("Two-Layer Brand Architecture  |  cooperation.tw \u00d7 AI Workshop System", {
    x: 0.55, y: 5.4, w: 9.15, h: 0.225,
    fontSize: 9, color: BRAND.white, valign: "middle", fontFace: "Calibri",
  });
}

// ═══════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════
async function main() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = "AI Workshop Brand System";

  // Slide 1: Overview (with adjusted primaries)
  buildOverviewSlide(pres);

  // Slides 2-6: Individual theme samples
  themes.forEach((t) => buildThemeSample(pres, t));

  // Slide 7: Strategy summary
  buildStrategySummary(pres);

  // Slide 8: Comparison table
  buildComparisonSlide(pres);

  // Slide 9: Website color analysis
  buildWebsiteAnalysis(pres);

  // Slide 10: Website ↔ Workshop alignment
  buildAlignmentSlide(pres);

  // Slide 11: Two-layer architecture
  buildArchitectureSlide(pres);

  const outPath = "/Users/user/Desktop/NILM+LLM/NILM_LLM_SETA/05_outputs/2026-03-06_AI_Paper_Workshop/Color_Brand_Sample.pptx";
  await pres.writeFile({ fileName: outPath });
  console.log("Done! " + outPath);
}

main().catch(console.error);
