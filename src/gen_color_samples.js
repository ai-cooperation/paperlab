const pptxgen = require("pptxgenjs");

const makeShadow = (opacity = 0.15) => ({
  type: "outer", color: "000000",
  blur: 6, offset: 3, angle: 135, opacity,
});

// ─── THREE COLOR SCHEMES ─────────────────────────────────

const schemeA = {
  name: "A: Deep Blue Academic (Nature/Science)",
  navy:      "1A365D",
  teal:      "2B6CB0",
  cyan:      "4299E1",
  white:     "FFFFFF",
  offwhite:  "F7FAFC",
  lightBlue: "EBF4FF",
  darkText:  "1A202C",
  grayText:  "718096",
  slate:     "2D3748",
  mint:      "C3DAFE",
  gold:      "C05621",
  green:     "2F855A",
  purple:    "553C9A",
  orange:    "C05621",
};

const schemeB = {
  name: "B: Warm Gray Humanities (Springer/Wiley)",
  navy:      "2D3748",
  teal:      "4A5568",
  cyan:      "718096",
  white:     "FFFFFF",
  offwhite:  "FAF5EF",
  lightBlue: "F0E6D8",
  darkText:  "1A202C",
  grayText:  "718096",
  slate:     "4A5568",
  mint:      "E2E8F0",
  gold:      "9B2C2C",
  green:     "2C7A7B",
  purple:    "6B46C1",
  orange:    "9B2C2C",
};

const schemeC = {
  name: "C: Emerald Research (Elsevier/IEEE)",
  navy:      "1B4332",
  teal:      "2D6A4F",
  cyan:      "40916C",
  white:     "FFFFFF",
  offwhite:  "F0FDF4",
  lightBlue: "D1FAE5",
  darkText:  "1A202C",
  grayText:  "6B7280",
  slate:     "1E3A5F",
  mint:      "A7F3D0",
  gold:      "C2410C",
  green:     "059669",
  purple:    "1E3A5F",
  orange:    "C2410C",
};

function buildSampleSlide(pres, C) {
  // ── COVER-STYLE TOP HALF ──
  const s = pres.addSlide();
  s.background = { color: C.navy };

  // Top accent line
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 10, h: 0.08, fill: { color: C.cyan },
  });
  // Left accent bar
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0.08, w: 0.12, h: 2.7, fill: { color: C.teal },
  });
  // Decorative circles
  s.addShape(pres.shapes.OVAL, {
    x: 7.2, y: -0.3, w: 3.2, h: 3.2,
    fill: { color: C.teal, transparency: 85 },
  });
  s.addShape(pres.shapes.OVAL, {
    x: 7.8, y: 0.4, w: 2.2, h: 2.2,
    fill: { color: C.cyan, transparency: 80 },
  });
  // Title
  s.addText("AI \u5b78\u8853\u7814\u7a76\u5168\u6d41\u7a0b\u5de5\u4f5c\u574a", {
    x: 0.4, y: 0.25, w: 7, h: 0.8,
    fontSize: 30, bold: true, color: C.white, fontFace: "Calibri",
  });
  // Subtitle
  s.addText("\u5f9e\u6982\u5ff5\u63a2\u7d22\u5230\u8ad6\u6587\u6295\u7a3f\u7684\u5b8c\u6574 AI \u5354\u4f5c\u6d41\u7a0b", {
    x: 0.4, y: 1.05, w: 7, h: 0.4,
    fontSize: 13, color: C.cyan, fontFace: "Calibri",
  });
  // Badge tags
  const tags = ["2 Days", "24 Skills", "8 Agents", "4 APIs"];
  tags.forEach((t, i) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 0.4 + i * 1.55, y: 1.55, w: 1.35, h: 0.32,
      fill: { color: C.teal }, rectRadius: 0.06,
    });
    s.addText(t, {
      x: 0.4 + i * 1.55, y: 1.55, w: 1.35, h: 0.32,
      fontSize: 10, bold: true, color: C.white,
      align: "center", valign: "middle", margin: 0,
    });
  });
  // Bottom accent on dark section
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 2.58, w: 10, h: 0.2,
    fill: { color: C.teal, transparency: 60 },
  });

  // ── CONTENT-STYLE BOTTOM HALF ──
  // Light background area
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 2.78, w: 10, h: 2.845,
    fill: { color: C.offwhite },
  });
  // Title bar
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 2.78, w: 10, h: 0.52,
    fill: { color: C.teal },
  });
  s.addText("\u5167\u5bb9\u9801\u7bc4\u4f8b\uff1a\u5361\u7247 + \u6d41\u7a0b\u6b65\u9a5f + \u63d0\u793a\u6846", {
    x: 0.4, y: 2.78, w: 9.2, h: 0.52,
    fontSize: 16, bold: true, color: C.white,
    valign: "middle", fontFace: "Calibri", margin: 0,
  });

  // Info Card 1 (left accent = teal)
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.25, y: 3.5, w: 3.0, h: 1.2,
    fill: { color: C.white }, shadow: makeShadow(0.12),
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.25, y: 3.5, w: 0.07, h: 1.2,
    fill: { color: C.teal },
  });
  s.addText("\u6587\u737b\u8abf\u7814", {
    x: 0.4, y: 3.55, w: 2.7, h: 0.28,
    fontSize: 12, bold: true, color: C.teal, margin: 0,
  });
  s.addText("CrossRef API \u9a57\u8b49\nSemantic Scholar \u5206\u6790\nObsidian \u77e5\u8b58\u5716\u8b5c", {
    x: 0.4, y: 3.85, w: 2.7, h: 0.75,
    fontSize: 10, color: C.darkText, margin: 0, lineSpacingMultiple: 1.25,
  });

  // Info Card 2 (left accent = gold/orange)
  s.addShape(pres.shapes.RECTANGLE, {
    x: 3.5, y: 3.5, w: 3.0, h: 1.2,
    fill: { color: C.white }, shadow: makeShadow(0.12),
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 3.5, y: 3.5, w: 0.07, h: 1.2,
    fill: { color: C.gold },
  });
  s.addText("\u54c1\u8cea\u5be9\u67e5", {
    x: 3.65, y: 3.55, w: 2.7, h: 0.28,
    fontSize: 12, bold: true, color: C.gold, margin: 0,
  });
  s.addText("\u4e03\u7dad\u5ea6\u8a55\u5206\u6846\u67b6\nP0-P3 \u554f\u984c\u5206\u7d1a\n\u4e09 AI \u5e73\u884c\u5be9\u67e5", {
    x: 3.65, y: 3.85, w: 2.7, h: 0.75,
    fontSize: 10, color: C.darkText, margin: 0, lineSpacingMultiple: 1.25,
  });

  // Info Card 3 (left accent = green)
  s.addShape(pres.shapes.RECTANGLE, {
    x: 6.75, y: 3.5, w: 3.0, h: 1.2,
    fill: { color: C.white }, shadow: makeShadow(0.12),
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 6.75, y: 3.5, w: 0.07, h: 1.2,
    fill: { color: C.green },
  });
  s.addText("\u6295\u7a3f\u6e96\u5099", {
    x: 6.9, y: 3.55, w: 2.7, h: 0.28,
    fontSize: 12, bold: true, color: C.green, margin: 0,
  });
  s.addText("Cover Letter \u64b0\u5beb\n10 \u9805\u7d20\u6750\u6e05\u55ae\nRebuttal Matrix", {
    x: 6.9, y: 3.85, w: 2.7, h: 0.75,
    fontSize: 10, color: C.darkText, margin: 0, lineSpacingMultiple: 1.25,
  });

  // Tip box
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.25, y: 4.9, w: 9.5, h: 0.42,
    fill: { color: C.lightBlue },
  });
  s.addText("\u2728 \u63d0\u793a\uff1a\u6240\u6709\u5f15\u7528\u5fc5\u9808\u7d93 API \u591a\u91cd\u9a57\u8b49\uff0c\u7d55\u4e0d\u76f2\u4fe1 AI \u7522\u51fa\u7684 DOI", {
    x: 0.4, y: 4.9, w: 9.2, h: 0.42,
    fontSize: 11, color: C.navy, valign: "middle", margin: 0,
  });

  // Bottom nav line
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 5.4, w: 10, h: 0.225,
    fill: { color: C.navy },
  });
  // Scheme label
  s.addText(C.name, {
    x: 0.3, y: 5.4, w: 9.4, h: 0.225,
    fontSize: 9, color: C.white, valign: "middle", margin: 0,
  });
}

async function main() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = "Color Scheme Samples";

  buildSampleSlide(pres, schemeA);
  buildSampleSlide(pres, schemeB);
  buildSampleSlide(pres, schemeC);

  const outPath = "/Users/user/Desktop/NILM+LLM/NILM_LLM_SETA/05_outputs/2026-03-06_AI_Paper_Workshop/Color_Scheme_Samples.pptx";
  await pres.writeFile({ fileName: outPath });
  console.log("Done! " + outPath);
}

main().catch(console.error);
