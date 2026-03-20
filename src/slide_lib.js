/**
 * AI Paper Workshop — Shared Slide Component Library
 * Reusable slide builders matching AI100 course design depth
 *
 * Brand: Navy #0B3C5D / Teal #0F9D8A / Gold #FFC857
 */

// ─── BRAND PALETTE ─────────────────────────────────────────
const C = {
  navy: "0B3C5D", navyLight: "134B6E", navyDark: "082D47",
  teal: "0F9D8A", tealLight: "12B89F", tealDark: "0A7A6B",
  gold: "FFC857", goldDark: "E6A820", goldLight: "FFE0A0",
  white: "FFFFFF", offwhite: "F5F7FA", lightBlue: "E8F4F2",
  darkText: "1A1A1A", grayText: "5A6B7A", slate: "2C3E50", mint: "D4F0EB",
  green: "27AE60", greenBg: "E8F8F0",
  orange: "E07A3A", orangeBg: "FEF2E8",
  red: "C0392B", redBg: "FEF2F2",
  purple: "6C5CE7",
  lgrey: "F2F2F2", mgrey: "D0D5DD",
};

const shadow = (o = 0.15) => ({ type: "outer", blur: 6, offset: 3, angle: 135, color: "000000", opacity: o });

// Shape type constants (avoid needing pres reference in helpers)
const SHAPES = { RECT: "rect", RRECT: "roundRect", OVAL: "ellipse" };

// ═══════════════════════════════════════════════════════════
// SLIDE BUILDERS
// ═══════════════════════════════════════════════════════════

/** Cover slide — dark navy with brand decorations */
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
      s.addText(b.text, { x: bx, y: 4.0, w: 1.4, h: 0.34, fontSize: 11, bold: true, color: C.white, align: "center", valign: "middle" });
    });
  }
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.2, w: 10, h: 0.425, fill: { color: C.teal, transparency: 60 } });
  if (footerLeft) s.addText(footerLeft, { x: 0.4, y: 5.2, w: 5, h: 0.425, fontSize: 11, color: C.white, valign: "middle" });
  if (footerRight) s.addText(footerRight, { x: 5, y: 5.2, w: 4.6, h: 0.425, fontSize: 11, color: C.white, valign: "middle", align: "right" });
  return s;
}

/** Section divider — dark navy with day badge */
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

/** Standard content slide with colored header bar */
function contentSlide(pres, title, accent = C.teal) {
  const s = pres.addSlide();
  s.background = { color: C.offwhite };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.72, fill: { color: accent } });
  s.addText(title, { x: 0.4, y: 0, w: 9.2, h: 0.72, fontSize: 22, bold: true, color: C.white, valign: "middle" });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.4, w: 10, h: 0.225, fill: { color: C.navy } });
  return s;
}

/** Concept slide — highlighted big text box + description + bullet items */
function conceptSlide(pres, title, bigText, desc, items) {
  const s = contentSlide(pres, title);
  // Big text box
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.3, y: 0.9, w: 9.4, h: 1.3, fill: { color: C.lightBlue }, rectRadius: 0.08 });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 0.9, w: 9.4, h: 0.06, fill: { color: C.teal } });
  s.addText(bigText, { x: 0.6, y: 0.98, w: 8.8, h: 0.55, fontSize: 18, bold: true, color: C.navy, align: "center", valign: "middle" });
  s.addText(desc, { x: 0.6, y: 1.55, w: 8.8, h: 0.5, fontSize: 14, color: C.grayText, align: "center", valign: "middle" });
  // Bullet items (reading-glasses: min 12pt)
  if (items && items.length > 0) {
    const fs = items.length > 5 ? 12 : 13;
    const lh = items.length > 5 ? 1.15 : 1.3;
    items.forEach((item, i) => {
      const y = 2.4 + i * (items.length > 5 ? 0.42 : 0.5);
      s.addText("\u25B8", { x: 0.4, y, w: 0.25, h: 0.35, fontSize: fs, color: C.teal, valign: "middle" });
      s.addText(item, { x: 0.7, y, w: 8.9, h: 0.35, fontSize: fs, color: C.darkText, valign: "middle", lineSpacingMultiple: lh });
    });
  }
  return s;
}

/** Step slide — Step N with circle badge + content */
function stepSlide(pres, seriesTitle, stepNum, stepTitle, lines) {
  const s = contentSlide(pres, seriesTitle);
  // Step circle
  s.addShape(pres.shapes.OVAL, { x: 0.3, y: 0.9, w: 0.65, h: 0.65, fill: { color: C.teal } });
  s.addText(`Step ${stepNum}`, { x: 0.3, y: 0.9, w: 0.65, h: 0.65, fontSize: 12, bold: true, color: C.white, align: "center", valign: "middle" });
  s.addText(stepTitle, { x: 1.1, y: 0.92, w: 8.5, h: 0.6, fontSize: 20, bold: true, color: C.darkText, valign: "middle" });
  // Content lines (reading-glasses: min 12pt)
  const fs = lines.length > 5 ? 12 : 13;
  lines.forEach((line, i) => {
    const y = 1.7 + i * 0.52;
    s.addText("\u2022", { x: 0.4, y, w: 0.2, h: 0.4, fontSize: fs, color: C.teal, valign: "top" });
    s.addText(line, { x: 0.65, y, w: 9.0, h: 0.45, fontSize: fs, color: C.darkText, valign: "top", lineSpacingMultiple: 1.2 });
  });
  return s;
}

/** Example slide — scenario box + result lines */
function exampleSlide(pres, title, scenario, resultLines) {
  const s = pres.addSlide();
  s.background = { color: C.offwhite };
  // Green header for example
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.72, fill: { color: C.teal } });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.3, y: 0.12, w: 1.4, h: 0.48, fill: { color: C.gold }, rectRadius: 0.06 });
  s.addText("範例展示", { x: 0.3, y: 0.12, w: 1.4, h: 0.48, fontSize: 11, bold: true, color: C.navy, align: "center", valign: "middle" });
  s.addText(title, { x: 1.85, y: 0, w: 7.8, h: 0.72, fontSize: 20, bold: true, color: C.white, valign: "middle" });
  // Scenario box
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.3, y: 0.85, w: 9.4, h: 0.85, fill: { color: C.orangeBg }, rectRadius: 0.06 });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 0.85, w: 0.07, h: 0.85, fill: { color: C.orange } });
  s.addText("情境：", { x: 0.5, y: 0.88, w: 0.8, h: 0.35, fontSize: 13, bold: true, color: C.orange, valign: "middle" });
  s.addText(scenario, { x: 1.3, y: 0.88, w: 8.2, h: 0.75, fontSize: 13, color: C.darkText, valign: "middle", lineSpacingMultiple: 1.2 });
  // Result
  s.addText("回覆：", { x: 0.3, y: 1.85, w: 2, h: 0.35, fontSize: 13, bold: true, color: C.teal });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.3, y: 2.2, w: 9.4, h: 3.0, fill: { color: C.lgrey }, rectRadius: 0.06 });
  const fs = resultLines.length > 8 ? 11 : 12;
  s.addText(resultLines.join("\n"), { x: 0.5, y: 2.3, w: 9.0, h: 2.8, fontSize: fs, color: C.darkText, lineSpacingMultiple: 1.25 });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.4, w: 10, h: 0.225, fill: { color: C.navy } });
  return s;
}

/** Exercise slide — green accent with numbered instructions */
function exerciseSlide(pres, title, instructions, timeStr) {
  const s = pres.addSlide();
  s.background = { color: C.offwhite };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.12, fill: { color: C.green } });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.3, y: 0.3, w: 1.5, h: 0.45, fill: { color: C.green }, rectRadius: 0.06 });
  s.addText("動手練習", { x: 0.3, y: 0.3, w: 1.5, h: 0.45, fontSize: 12, bold: true, color: C.white, align: "center", valign: "middle" });
  s.addText(title, { x: 2.0, y: 0.28, w: 7.6, h: 0.5, fontSize: 18, bold: true, color: C.darkText, valign: "middle" });
  if (timeStr) s.addText(timeStr, { x: 2.0, y: 0.76, w: 5, h: 0.3, fontSize: 12, color: C.grayText });
  instructions.forEach((inst, i) => {
    const y = 1.2 + i * 0.58;
    s.addShape(pres.shapes.OVAL, { x: 0.35, y: y + 0.02, w: 0.38, h: 0.38, fill: { color: C.teal } });
    s.addText(String(i + 1), { x: 0.35, y: y + 0.02, w: 0.38, h: 0.38, fontSize: 12, bold: true, color: C.white, align: "center", valign: "middle" });
    s.addText(inst, { x: 0.85, y, w: 8.8, h: 0.45, fontSize: 13, color: C.darkText, valign: "middle" });
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.4, w: 10, h: 0.225, fill: { color: C.navy } });
  return s;
}

/** Compare slide — two columns side by side */
function compareSlide(pres, title, lTitle, lItems, rTitle, rItems) {
  const s = contentSlide(pres, title);
  // Left column
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.3, y: 0.9, w: 4.5, h: 4.2, fill: { color: C.lightBlue }, rectRadius: 0.08 });
  s.addText(lTitle, { x: 0.5, y: 1.0, w: 4.1, h: 0.4, fontSize: 14, bold: true, color: C.teal });
  lItems.forEach((item, i) => {
    s.addText("\u2022 " + item, { x: 0.6, y: 1.5 + i * 0.42, w: 4.0, h: 0.38, fontSize: 12, color: C.darkText, valign: "middle" });
  });
  // Right column
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.2, y: 0.9, w: 4.5, h: 4.2, fill: { color: C.greenBg }, rectRadius: 0.08 });
  s.addText(rTitle, { x: 5.4, y: 1.0, w: 4.1, h: 0.4, fontSize: 14, bold: true, color: C.green });
  rItems.forEach((item, i) => {
    s.addText("\u2022 " + item, { x: 5.5, y: 1.5 + i * 0.42, w: 4.0, h: 0.38, fontSize: 12, color: C.darkText, valign: "middle" });
  });
  return s;
}

/** Horizontal cards slide — 2-4 cards with accent top bar */
function cardsSlide(pres, title, cards) {
  const s = contentSlide(pres, title);
  const nc = Math.min(cards.length, 4);
  const gap = 0.2;
  const cw = (9.4 - gap * (nc - 1)) / nc;
  const accents = [C.teal, C.navy, C.goldDark, C.tealDark];
  const bgs = [C.lightBlue, "E8EDF4", "FFF7E6", C.mint];
  cards.forEach((card, i) => {
    const x = 0.3 + i * (cw + gap);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 0.9, w: cw, h: 4.2, fill: { color: bgs[i % 4] }, rectRadius: 0.08, shadow: shadow(0.08) });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.9, w: cw, h: 0.06, fill: { color: accents[i % 4] } });
    // Icon/emoji
    if (card.icon) s.addText(card.icon, { x, y: 1.1, w: cw, h: 0.5, fontSize: 22, align: "center", valign: "middle" });
    const ty = card.icon ? 1.6 : 1.1;
    s.addText(card.title, { x: x + 0.1, y: ty, w: cw - 0.2, h: 0.4, fontSize: 13, bold: true, color: accents[i % 4], align: "center" });
    // Description (reading-glasses: min 12pt)
    const dy = ty + 0.45;
    const desc = Array.isArray(card.desc) ? card.desc.join("\n") : card.desc;
    s.addText(desc, { x: x + 0.12, y: dy, w: cw - 0.24, h: 4.2 - (dy - 0.9) - 0.15, fontSize: 12, color: C.darkText, lineSpacingMultiple: 1.25 });
  });
  return s;
}

/** Key points slide — numbered points with heading + description (2-col grid) */
function keyPointsSlide(pres, title, points) {
  const s = contentSlide(pres, title);
  const n = Math.min(points.length, 6);
  const cols = n <= 3 ? 1 : 2;
  const colW = cols === 2 ? 4.5 : 9.2;
  const rowH = n <= 3 ? 1.2 : (n <= 4 ? 1.1 : 0.9);
  points.forEach((pt, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const x = 0.3 + col * 4.85;
    const y = 0.9 + row * rowH;
    // Number circle
    s.addShape(pres.shapes.OVAL, { x, y: y + 0.05, w: 0.42, h: 0.42, fill: { color: C.teal } });
    s.addText(String(i + 1), { x, y: y + 0.05, w: 0.42, h: 0.42, fontSize: 14, bold: true, color: C.white, align: "center", valign: "middle" });
    // Heading
    s.addText(pt.heading, { x: x + 0.55, y, w: colW - 0.7, h: 0.35, fontSize: 13, bold: true, color: C.navy });
    // Description (reading-glasses: min 12pt)
    s.addText(pt.desc, { x: x + 0.55, y: y + 0.35, w: colW - 0.7, h: rowH - 0.42, fontSize: 12, color: C.grayText, lineSpacingMultiple: 1.2 });
  });
  return s;
}

/** Quote slide — full navy background with large quote */
function quoteSlide(pres, quote, sub) {
  const s = pres.addSlide();
  s.background = { color: C.navy };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.12, h: 5.625, fill: { color: C.teal } });
  s.addText(quote, { x: 1.0, y: 1.2, w: 8.0, h: 2.5, fontSize: 30, bold: true, color: C.white, align: "center", valign: "middle", lineSpacingMultiple: 1.3 });
  if (sub) s.addText(sub, { x: 1.0, y: 3.8, w: 8.0, h: 0.8, fontSize: 14, color: C.teal, align: "center", valign: "middle" });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.2, w: 10, h: 0.425, fill: { color: C.teal, transparency: 70 } });
  return s;
}

/** Transition slide — dark with two-line text */
function transitionSlide(pres, top, bottom) {
  const s = pres.addSlide();
  s.background = { color: C.navyDark };
  s.addText(top, { x: 1.0, y: 1.8, w: 8.0, h: 0.8, fontSize: 16, color: C.teal, align: "center", valign: "middle" });
  s.addText(bottom, { x: 1.0, y: 2.8, w: 8.0, h: 1.2, fontSize: 32, bold: true, color: C.white, align: "center", valign: "middle" });
  return s;
}

/** Output/deliverables slide */
function outputSlide(pres, title, deliverables) {
  const s = contentSlide(pres, title);
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.3, y: 0.9, w: 2.0, h: 0.4, fill: { color: C.teal }, rectRadius: 0.06 });
  s.addText("學員產出", { x: 0.3, y: 0.9, w: 2.0, h: 0.4, fontSize: 12, bold: true, color: C.white, align: "center", valign: "middle" });
  deliverables.forEach((d, i) => {
    const y = 1.5 + i * 0.75;
    const bg = i % 2 === 0 ? C.greenBg : C.lightBlue;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.3, y, w: 9.4, h: 0.65, fill: { color: bg }, rectRadius: 0.06 });
    s.addText(d.item, { x: 0.5, y, w: 3.5, h: 0.65, fontSize: 13, bold: true, color: C.navy, valign: "middle" });
    s.addText(d.desc, { x: 4.0, y, w: 5.5, h: 0.65, fontSize: 12, color: C.darkText, valign: "middle" });
  });
  return s;
}

/** Before/After comparison slide */
function beforeAfterSlide(pres, title, beforeLines, afterLines) {
  const s = contentSlide(pres, title);
  // Before
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.3, y: 0.9, w: 4.5, h: 4.2, fill: { color: C.redBg }, rectRadius: 0.08 });
  s.addText("Before", { x: 0.5, y: 1.0, w: 2.5, h: 0.35, fontSize: 14, bold: true, color: C.red });
  beforeLines.forEach((line, i) => {
    s.addText(line, { x: 0.6, y: 1.45 + i * 0.38, w: 4.0, h: 0.34, fontSize: 12, color: C.darkText, valign: "middle" });
  });
  // After
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.2, y: 0.9, w: 4.5, h: 4.2, fill: { color: C.greenBg }, rectRadius: 0.08 });
  s.addText("After", { x: 5.4, y: 1.0, w: 2.5, h: 0.35, fontSize: 14, bold: true, color: C.green });
  afterLines.forEach((line, i) => {
    s.addText(line, { x: 5.5, y: 1.45 + i * 0.38, w: 4.0, h: 0.34, fontSize: 12, color: C.darkText, valign: "middle" });
  });
  return s;
}

/** TOC slide with numbered items */
function tocSlide(pres, title, items) {
  const s = contentSlide(pres, title, C.navy);
  items.forEach((item, i) => {
    const y = 0.9 + i * 0.68;
    s.addShape(pres.shapes.OVAL, { x: 0.4, y: y + 0.05, w: 0.45, h: 0.45, fill: { color: C.teal } });
    s.addText(item.num || String(i + 1), { x: 0.4, y: y + 0.05, w: 0.45, h: 0.45, fontSize: 13, bold: true, color: C.white, align: "center", valign: "middle" });
    s.addText(item.title, { x: 1.05, y, w: 5.5, h: 0.3, fontSize: 13, bold: true, color: C.darkText, valign: "middle" });
    s.addText(item.time || "", { x: 7.0, y, w: 2.7, h: 0.3, fontSize: 12, color: C.grayText, valign: "middle", align: "right" });
    if (item.desc) s.addText(item.desc, { x: 1.05, y: y + 0.3, w: 8.5, h: 0.3, fontSize: 12, color: C.grayText, valign: "middle" });
  });
  return s;
}

/** Module section — 4 topic cards (like AI100 S_section) */
function moduleSection(pres, secNum, secTitle, timeStr, cards) {
  const s = contentSlide(pres, `${secNum}. ${secTitle}`);
  s.addText(timeStr, { x: 0.4, y: 0.72, w: 5, h: 0.3, fontSize: 12, color: C.grayText });
  const nc = Math.min(cards.length, 4);
  const gap = 0.15;
  const cw = (9.4 - gap * (nc - 1)) / nc;
  cards.forEach((card, i) => {
    const x = 0.3 + i * (cw + gap);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.2, w: cw, h: 3.9, fill: { color: C.lgrey }, rectRadius: 0.08, shadow: shadow(0.06) });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.2, w: cw, h: 0.05, fill: { color: C.teal } });
    s.addText(card.title, { x: x + 0.1, y: 1.35, w: cw - 0.2, h: 0.4, fontSize: 13, bold: true, color: C.navy });
    s.addText(card.desc, { x: x + 0.1, y: 1.8, w: cw - 0.2, h: 3.1, fontSize: 12, color: C.darkText, lineSpacingMultiple: 1.3 });
  });
  return s;
}

/** Info card helper (used within slides) */
function infoCard(s, pres, x, y, w, h, title, body, accent = C.teal) {
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: C.white }, shadow: shadow(0.12) });
  s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.07, h, fill: { color: accent } });
  s.addText(title, { x: x + 0.15, y: y + 0.08, w: w - 0.22, h: 0.32, fontSize: 13, bold: true, color: accent, margin: 0, fit: "shrink" });
  s.addText(body, { x: x + 0.15, y: y + 0.46, w: w - 0.22, h: h - 0.56, fontSize: 12, color: C.darkText, margin: 0, lineSpacingMultiple: 1.2, fit: "shrink" });
}

/** Code box helper */
function codeBox(s, pres, x, y, w, h, title, code) {
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: C.darkText }, shadow: shadow() });
  if (title) s.addText(title, { x: x + 0.12, y: y + 0.06, w: w - 0.24, h: 0.28, fontSize: 11, bold: true, color: C.gold, margin: 0, fit: "shrink" });
  const cy = title ? y + 0.40 : y + 0.08;
  const ch = title ? h - 0.48 : h - 0.16;
  s.addText(code, { x: x + 0.12, y: cy, w: w - 0.24, h: ch, fontSize: 11, fontFace: "Consolas", color: C.teal, margin: 0, lineSpacingMultiple: 1.25, fit: "shrink" });
}

/** Tip/info box helper */
function tipBox(s, x, y, w, text) {
  s.addShape(SHAPES.RECT, { x, y, w, h: 0.42, fill: { color: C.lightBlue } });
  s.addText(text, { x: x + 0.12, y, w: w - 0.24, h: 0.42, fontSize: 12, color: C.navy, valign: "middle" });
}

/** Warning box helper */
function warnBox(s, x, y, w, text) {
  s.addShape(SHAPES.RECT, { x, y, w, h: 0.55, fill: { color: C.redBg } });
  s.addShape(SHAPES.RECT, { x, y, w: 0.07, h: 0.55, fill: { color: C.red } });
  s.addText(text, { x: x + 0.2, y, w: w - 0.3, h: 0.55, fontSize: 12, bold: true, color: C.red, valign: "middle" });
}

/** Process steps — horizontal numbered boxes with arrows */
function processSteps(s, pres, steps, startY = 1.2) {
  const gap = 0.15;
  const sw = (9.5 - (steps.length - 1) * gap) / steps.length;
  steps.forEach((st, i) => {
    const x = 0.25 + i * (sw + gap);
    s.addShape(pres.shapes.RECTANGLE, { x, y: startY, w: sw, h: 2.6, fill: { color: st.color }, shadow: shadow() });
    s.addShape(pres.shapes.OVAL, { x: x + sw / 2 - 0.35, y: startY + 0.12, w: 0.7, h: 0.7, fill: { color: C.white } });
    s.addText(st.n, { x: x + sw / 2 - 0.35, y: startY + 0.12, w: 0.7, h: 0.7, fontSize: 20, bold: true, color: st.color, align: "center", valign: "middle" });
    s.addText(st.title, { x: x + 0.06, y: startY + 0.95, w: sw - 0.12, h: 0.42, fontSize: 13, bold: true, color: C.white, align: "center" });
    s.addText(st.desc, { x: x + 0.08, y: startY + 1.4, w: sw - 0.16, h: 1.1, fontSize: 11, color: C.mint, align: "center", lineSpacingMultiple: 1.2 });
    if (i < steps.length - 1) {
      s.addText("\u25B6", { x: x + sw + 0.01, y: startY + 1.05, w: 0.14, h: 0.4, fontSize: 11, color: C.grayText, align: "center" });
    }
  });
}

/** Table slide helper */
function tableSlide(s, headers, rows, opts = {}) {
  const startY = opts.y || 1.0;
  const colW = opts.colW || headers.map(() => 9.4 / headers.length);
  const tableRows = [
    headers.map(h => ({ text: h, options: { fontSize: 12, bold: true, color: C.white, fill: { color: C.navy }, align: "center", valign: "middle" } })),
    ...rows.map((row, ri) =>
      row.map((cell, ci) => ({
        text: cell,
        options: { fontSize: 12, color: C.darkText, fill: { color: ri % 2 === 0 ? C.white : C.lightBlue }, valign: "middle", align: ci === 0 ? "left" : "center" },
      }))
    ),
  ];
  s.addTable(tableRows, { x: 0.3, y: startY, w: 9.4, colW, border: { type: "solid", pt: 0.5, color: "D0D5DD" } });
}

/** Closing slide */
function closingSlide(pres, mainText, subtitle, note) {
  const s = pres.addSlide();
  s.background = { color: C.navy };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.08, fill: { color: C.gold } });
  s.addShape(pres.shapes.OVAL, { x: 7.2, y: -0.5, w: 3.5, h: 3.5, fill: { color: C.teal, transparency: 85 } });
  s.addShape(pres.shapes.OVAL, { x: 7.8, y: 0.5, w: 2.5, h: 2.5, fill: { color: C.gold, transparency: 80 } });
  s.addText(mainText, { x: 1.0, y: 1.5, w: 8.0, h: 1.5, fontSize: 38, bold: true, color: C.white, align: "center", valign: "middle" });
  s.addText(subtitle, { x: 1.0, y: 3.2, w: 8.0, h: 0.8, fontSize: 18, color: C.teal, align: "center", valign: "middle" });
  if (note) s.addText(note, { x: 1.0, y: 4.2, w: 8.0, h: 0.6, fontSize: 14, color: C.gold, align: "center", valign: "middle" });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.2, w: 10, h: 0.425, fill: { color: C.teal, transparency: 60 } });
  return s;
}

module.exports = {
  C, shadow,
  coverSlide, sectionDivider, contentSlide,
  conceptSlide, stepSlide, exampleSlide, exerciseSlide,
  compareSlide, cardsSlide, keyPointsSlide,
  quoteSlide, transitionSlide, outputSlide,
  beforeAfterSlide, tocSlide, moduleSection,
  infoCard, codeBox, tipBox, warnBox, processSteps, tableSlide,
  closingSlide,
};
