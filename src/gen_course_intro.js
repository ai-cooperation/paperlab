const pptxgen = require("pptxgenjs");

// ─── DESIGN SYSTEM ──────────────────────────────────────────
// ─── BRAND PALETTE: AI Paper Workshop ─────────────────────
const C = {
  // Primary
  navy:      "0B3C5D",  // Deep Academic Blue
  navyLight: "134B6E",
  // Secondary
  teal:      "0F9D8A",  // Emerald Research Green
  tealLight: "12B89F",
  tealDark:  "0A7A6B",
  // Accent
  gold:      "FFC857",  // Research Highlight Yellow
  goldDark:  "E6A820",
  // Neutral
  white:     "FFFFFF",
  offwhite:  "F5F7FA",  // Light Background
  lightBlue: "E8F4F2",  // Tinted with teal for tip boxes
  darkText:  "1A1A1A",  // Text
  grayText:  "5A6B7A",  // Muted text
  slate:     "2C3E50",  // Secondary dark
  mint:      "D4F0EB",  // Light teal for dark-bg text
  // Functional
  green:     "0F9D8A",  // Same as teal (success)
  purple:    "0B3C5D",  // Reuse navy for consistency
  orange:    "E07A3A",  // Warning/problem
};

const makeShadow = (opacity = 0.15) => ({
  type: "outer", color: "000000",
  blur: 6, offset: 3, angle: 135, opacity,
});

// ─── ICON UTILITY ───────────────────────────────────────────
async function iconToBase64Png(iconName, color = "#FFFFFF", size = 256) {
  try {
    const fa = require("react-icons/fa");
    const md = require("react-icons/md");
    const bi = require("react-icons/bi");
    const allIcons = { ...fa, ...md, ...bi };
    const IconComponent = allIcons[iconName];
    if (!IconComponent) return null;
    const svg = ReactDOMServer.renderToStaticMarkup(
      React.createElement(IconComponent, { color, size: String(size) })
    );
    const pngBuffer = await sharp(Buffer.from(svg)).png().toBuffer();
    return "image/png;base64," + pngBuffer.toString("base64");
  } catch (e) { return null; }
}

// ─── SLIDE TEMPLATES ────────────────────────────────────────

function addSectionDivider(pres, title, subtitle, dayLabel, bgColor = C.navy) {
  const slide = pres.addSlide();
  slide.background = { color: bgColor };
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 0.12, h: 5.625, fill: { color: C.teal },
  });
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.5, y: 0.4, w: 1.6, h: 0.55,
    fill: { color: C.teal }, rectRadius: 0.08,
  });
  slide.addText(dayLabel, {
    x: 0.5, y: 0.4, w: 1.6, h: 0.55,
    fontSize: 14, bold: true, color: C.navy,
    align: "center", valign: "middle", margin: 0,
  });
  slide.addText(title, {
    x: 0.5, y: 1.2, w: 9, h: 1.5,
    fontSize: 42, bold: true, color: C.white, fontFace: "Calibri",
  });
  slide.addText(subtitle, {
    x: 0.5, y: 2.8, w: 9, h: 0.7,
    fontSize: 18, color: C.teal, fontFace: "Calibri",
  });
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 5.2, w: 10, h: 0.425,
    fill: { color: C.teal, transparency: 70 },
  });
  return slide;
}

function addContentSlide(pres, title, accentColor = C.teal) {
  const slide = pres.addSlide();
  slide.background = { color: C.offwhite };
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 10, h: 0.72, fill: { color: accentColor },
  });
  slide.addText(title, {
    x: 0.4, y: 0, w: 9.2, h: 0.72,
    fontSize: 22, bold: true, color: C.white,
    valign: "middle", fontFace: "Calibri", margin: 0,
  });
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 5.4, w: 10, h: 0.225, fill: { color: C.navy },
  });
  return slide;
}

function addInfoCard(slide, pres, x, y, w, h, title, body, accentColor = C.teal) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h, fill: { color: C.white }, shadow: makeShadow(0.12),
  });
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w: 0.07, h, fill: { color: accentColor },
  });
  slide.addText(title, {
    x: x + 0.15, y: y + 0.08, w: w - 0.2, h: 0.32,
    fontSize: 13, bold: true, color: accentColor, fontFace: "Calibri", margin: 0,
  });
  slide.addText(body, {
    x: x + 0.15, y: y + 0.38, w: w - 0.2, h: h - 0.46,
    fontSize: 10.5, color: C.darkText, fontFace: "Calibri", margin: 0,
    lineSpacingMultiple: 1.25,
  });
}

function addProcessSteps(slide, pres, steps, startY = 1.2) {
  const stepW = (9.5 - (steps.length - 1) * 0.15) / steps.length;
  steps.forEach((step, i) => {
    const x = 0.25 + i * (stepW + 0.15);
    slide.addShape(pres.shapes.RECTANGLE, {
      x, y: startY, w: stepW, h: 2.2, fill: { color: step.color },
      shadow: makeShadow(),
    });
    slide.addShape(pres.shapes.OVAL, {
      x: x + stepW / 2 - 0.32, y: startY + 0.1, w: 0.64, h: 0.64,
      fill: { color: C.white },
    });
    slide.addText(step.n, {
      x: x + stepW / 2 - 0.32, y: startY + 0.1, w: 0.64, h: 0.64,
      fontSize: 18, bold: true, color: step.color,
      align: "center", valign: "middle", margin: 0,
    });
    slide.addText(step.title, {
      x, y: startY + 0.82, w: stepW, h: 0.4,
      fontSize: 12, bold: true, color: C.white, align: "center", margin: 0,
    });
    slide.addText(step.desc, {
      x: x + 0.06, y: startY + 1.22, w: stepW - 0.12, h: 0.85,
      fontSize: 9, color: C.mint, align: "center", margin: 0,
      lineSpacingMultiple: 1.2,
    });
    if (i < steps.length - 1) {
      slide.addText("\u25B6", {
        x: x + stepW + 0.01, y: startY + 0.85,
        w: 0.13, h: 0.35, fontSize: 10,
        color: C.grayText, align: "center", margin: 0,
      });
    }
  });
}

function addTipBox(slide, pres, x, y, w, h, text) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h, fill: { color: C.lightBlue },
  });
  slide.addText(text, {
    x: x + 0.15, y, w: w - 0.3, h,
    fontSize: 11, color: C.navy, valign: "middle", margin: 0,
  });
}

function addBadge(slide, pres, x, y, w, h, text, bgColor, textColor = C.white) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, fill: { color: bgColor }, rectRadius: 0.06,
  });
  slide.addText(text, {
    x, y, w, h, fontSize: 10, bold: true, color: textColor,
    align: "center", valign: "middle", margin: 0,
  });
}

// ─── MAIN ───────────────────────────────────────────────────

async function main() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = "AI \u5b78\u8853\u7814\u7a76\u5168\u6d41\u7a0b\u5de5\u4f5c\u574a 2026";
  pres.author = "Alan Chen";

  // ══════════════════════════════════════════════════════════
  // SLIDE 1: Cover
  // ══════════════════════════════════════════════════════════
  {
    const s = pres.addSlide();
    s.background = { color: C.navy };
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0, y: 0, w: 10, h: 0.08, fill: { color: C.gold },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0, y: 0.08, w: 0.12, h: 5.545, fill: { color: C.teal },
    });
    s.addShape(pres.shapes.OVAL, {
      x: 7.2, y: -0.5, w: 3.5, h: 3.5,
      fill: { color: C.teal, transparency: 88 },
    });
    s.addShape(pres.shapes.OVAL, {
      x: 7.8, y: 0.5, w: 2.5, h: 2.5,
      fill: { color: C.gold, transparency: 85 },
    });
    // Main title
    s.addText("AI \u5b78\u8853\u7814\u7a76\n\u5168\u6d41\u7a0b\u5de5\u4f5c\u574a", {
      x: 0.4, y: 0.8, w: 7.5, h: 2.2,
      fontSize: 46, bold: true, color: C.white,
      fontFace: "Calibri", lineSpacingMultiple: 1.15,
    });
    // Subtitle
    s.addText("\u5f9e\u6982\u5ff5\u63a2\u7d22\u5230\u8ad6\u6587\u6295\u7a3f\u7684\u5b8c\u6574 AI \u5354\u4f5c\u5de5\u4f5c\u6d41\u7a0b", {
      x: 0.4, y: 3.1, w: 7.5, h: 0.55,
      fontSize: 17, color: C.gold, fontFace: "Calibri",
    });
    // Tags
    const tags = [
      { t: "2 Days", x: 0.4 },
      { t: "11 Phases", x: 1.5 },
      { t: "24 Skills", x: 2.75 },
      { t: "8 Agents", x: 3.95 },
      { t: "5 Commands", x: 5.05 },
      { t: "4 APIs", x: 6.3 },
    ];
    tags.forEach(tag => {
      addBadge(s, pres, tag.x, 3.78, 0.95, 0.35, tag.t, C.teal);
    });
    // Bottom bar
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0, y: 5.2, w: 10, h: 0.425,
      fill: { color: C.teal, transparency: 60 },
    });
    s.addText("Smart Manufacturing Research Lab  |  L1D2 + L2D1  |  2026", {
      x: 0.4, y: 5.2, w: 9.2, h: 0.425,
      fontSize: 10, color: C.white, valign: "middle", margin: 0,
    });
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 2: 為什麼這堂課很重要？— 論文造假警鐘
  // ══════════════════════════════════════════════════════════
  {
    const s = pres.addSlide();
    s.background = { color: C.navy };
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.12, h: 5.625, fill: { color: C.orange } });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 0.4, w: 2.4, h: 0.55, fill: { color: C.orange }, rectRadius: 0.08 });
    s.addText("Course Motivation", { x: 0.5, y: 0.4, w: 2.4, h: 0.55, fontSize: 14, bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });
    s.addText("為什麼這堂課很重要？", { x: 0.5, y: 1.2, w: 9, h: 1.2, fontSize: 42, bold: true, color: C.white, fontFace: "Calibri" });
    s.addText("AI 時代的論文造假 — 今天的新聞，明天的教訓", { x: 0.5, y: 2.5, w: 9, h: 0.7, fontSize: 18, color: C.gold, fontFace: "Calibri" });
    const stats = [
      { num: "11,000+", label: "Wiley 撤回\n造假論文", color: C.orange },
      { num: "100+", label: "NeurIPS 2025\n虛構引用", color: C.orange },
      { num: "20%", label: "ChatGPT 引用\n捏造比例", color: C.gold },
      { num: "Today", label: "政大國發所\n博士論文下架", color: C.orange },
    ];
    stats.forEach((st, i) => {
      const x = 0.5 + i * 2.35;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 3.5, w: 2.15, h: 1.4, fill: { color: st.color, transparency: 30 }, rectRadius: 0.08 });
      s.addText(st.num, { x, y: 3.55, w: 2.15, h: 0.6, fontSize: 30, bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });
      s.addText(st.label, { x, y: 4.15, w: 2.15, h: 0.65, fontSize: 12, color: C.mint, align: "center", valign: "middle", lineSpacingMultiple: 1.2, margin: 0 });
    });
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.2, w: 10, h: 0.425, fill: { color: C.orange, transparency: 60 } });
    s.addText("不學會驗證，你就是下一個受害者", { x: 0.4, y: 5.2, w: 9.2, h: 0.425, fontSize: 12, bold: true, color: C.white, valign: "middle", align: "center", margin: 0 });
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 3: 全球論文造假案例
  // ══════════════════════════════════════════════════════════
  {
    const s = addContentSlide(pres, "全球論文造假：這不是個案，是系統性危機", C.orange);
    const cases = [
      { title: "NeurIPS 2025", desc: "全球頂級 AI 會議，53 篇論文中發現 100+ 條 AI 幻覺引用，通過 3+ 位審稿人的審查仍未被發現", color: C.orange },
      { title: "ICLR 2026", desc: "投稿量暴增 70%（近 20,000 篇），50+ 條虛構引用；21% 的同行審查本身也是 AI 生成", color: C.orange },
      { title: "Wiley/Hindawi", desc: "撤回近 11,000 篇論文工廠產品，關閉 19 本期刊，史上最大規模撤稿", color: C.navy },
      { title: "ChatGPT 研究", desc: "研究顯示 ChatGPT 捏造 20% 的學術引用，45% 的真實引用包含錯誤資訊", color: C.gold },
      { title: "政大國發所", desc: "2026-03-13：博士論文遭質疑虛構參考文獻，AI 工具生成書目錯漏，論文已下架調查中", color: C.orange },
    ];
    cases.forEach((c, i) => {
      const y = 0.9 + i * 0.88;
      const bg = i % 2 === 0 ? C.offwhite : C.white;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.3, y, w: 9.4, h: 0.78, fill: { color: bg }, rectRadius: 0.06 });
      s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y, w: 0.07, h: 0.78, fill: { color: c.color } });
      addBadge(s, pres, 0.5, y + 0.08, 1.4, 0.26, c.title, c.color);
      s.addText(c.desc, { x: 2.1, y: y + 0.02, w: 7.4, h: 0.74, fontSize: 11.5, color: C.darkText, valign: "middle", margin: 0, lineSpacingMultiple: 1.2 });
    });
    addTipBox(s, pres, 0.3, 5.3, 9.4, 0.2, "");
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 4: 核心原則 — 信任但驗證
  // ══════════════════════════════════════════════════════════
  {
    const s = addContentSlide(pres, "本課程的核心原則：信任但驗證（Trust but Verify）");
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.3, y: 0.9, w: 9.4, h: 1.1, fill: { color: C.lightBlue }, rectRadius: 0.08 });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 0.9, w: 9.4, h: 0.06, fill: { color: C.teal } });
    s.addText("AI 是強大的助手，但絕不是可以盲信的權威", { x: 0.6, y: 0.98, w: 8.8, h: 0.45, fontSize: 18, bold: true, color: C.navy, align: "center", valign: "middle", margin: 0 });
    s.addText("每一個 AI 產出的資訊，都必須經過人工確認或 API 自動驗證後才能使用", { x: 0.6, y: 1.45, w: 8.8, h: 0.4, fontSize: 12, color: C.grayText, align: "center", valign: "middle", margin: 0 });
    const items = [
      { label: "文獻引用", desc: "CrossRef + Semantic Scholar + OpenAlex 三重 API 驗證", color: C.teal },
      { label: "研究數據", desc: "回溯原始來源，確認數字、表格、圖表的一致性", color: C.navy },
      { label: "AI 寫作", desc: "逐段審查，確保不抄襲、不捏造、不過度解讀", color: C.gold },
      { label: "實驗結果", desc: "統計驗證 + 消融實驗 + 誤差分析", color: C.green },
    ];
    items.forEach((item, i) => {
      const y = 2.2 + i * 0.58;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.4, y, w: 1.5, h: 0.42, fill: { color: item.color }, rectRadius: 0.06 });
      s.addText(item.label, { x: 0.4, y, w: 1.5, h: 0.42, fontSize: 12, bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });
      s.addText(item.desc, { x: 2.1, y, w: 7.5, h: 0.42, fontSize: 12, color: C.darkText, valign: "middle", margin: 0 });
    });
    addTipBox(s, pres, 0.3, 4.7, 9.4, 0.42, "這不是「限制 AI」，而是「負責任地使用 AI」— 讓你的研究經得起檢驗");
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 5: 三種研究模式 — 成長歷程總覽
  // ══════════════════════════════════════════════════════════
  {
    const s = addContentSlide(pres, "我的 AI 研究成長歷程：三種模式的演進", C.navy);
    const modes = [
      { n: "1", title: "入門模式", subtitle: "ChatGPT + Word", desc: "AI 聊天打草稿\n手動處理文獻\nWord + Zotero 引用", color: C.teal, bg: C.lightBlue },
      { n: "2", title: "整合模式", subtitle: "Zotero + GAS + Obsidian", desc: "Deep Research 探索\nGAS 自動分析 PDF\nMD 匯入 Obsidian", color: C.navy, bg: C.offwhite },
      { n: "3", title: "系統模式", subtitle: "IDE + API + 自動化", desc: "IDE 建專案\nAPI 三重驗證 DOI\n架構設計+實驗", color: C.gold, bg: C.offwhite },
    ];
    modes.forEach((m, i) => {
      const x = 0.3 + i * 3.2;
      const w = 2.95;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.0, w, h: 3.6, fill: { color: m.bg }, rectRadius: 0.08, shadow: makeShadow(0.1) });
      s.addShape(pres.shapes.RECTANGLE, { x, y: 1.0, w, h: 0.06, fill: { color: m.color } });
      s.addShape(pres.shapes.OVAL, { x: x + w / 2 - 0.28, y: 1.2, w: 0.56, h: 0.56, fill: { color: m.color } });
      s.addText(m.n, { x: x + w / 2 - 0.28, y: 1.2, w: 0.56, h: 0.56, fontSize: 20, bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });
      s.addText(m.title, { x: x + 0.1, y: 1.85, w: w - 0.2, h: 0.32, fontSize: 15, bold: true, color: m.color, align: "center", margin: 0 });
      s.addText(m.subtitle, { x: x + 0.1, y: 2.17, w: w - 0.2, h: 0.25, fontSize: 11, color: C.grayText, align: "center", margin: 0 });
      s.addText(m.desc, { x: x + 0.15, y: 2.55, w: w - 0.3, h: 1.9, fontSize: 12, color: C.darkText, lineSpacingMultiple: 1.3, margin: 0 });
      if (i < 2) s.addText("\u27A1", { x: x + w - 0.05, y: 2.5, w: 0.5, h: 0.4, fontSize: 18, color: C.grayText, align: "center", margin: 0 });
    });
    addTipBox(s, pres, 0.3, 4.75, 9.4, 0.42, "本課程涵蓋三種模式 — Day 1 主要教模式 1+2，Day 2 進入模式 3 的系統化流程");
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 6: 模式 1 — ChatGPT + Word（簡易版）
  // ══════════════════════════════════════════════════════════
  {
    const s = addContentSlide(pres, "模式 1：AI 聊天 + 手動整理（入門）");
    addBadge(s, pres, 0.3, 0.9, 0.5, 0.45, "1", C.teal);
    s.addText("最快上手，適合初次使用 AI 做研究的人", { x: 0.95, y: 0.92, w: 8.5, h: 0.42, fontSize: 14, bold: true, color: C.darkText, valign: "middle", margin: 0 });
    const steps = [
      { n: "1", title: "Deep Research\n找議題", desc: "ChatGPT o3\nClaude / Gemini", color: C.teal },
      { n: "2", title: "AI 打草稿", desc: "多輪對話\n持續優化", color: C.navy },
      { n: "3", title: "手動處理\n文獻", desc: "Zotero 管理\n確認引用", color: C.gold },
      { n: "4", title: "Word 編輯", desc: "插入引用\n排版完成", color: C.green },
    ];
    addProcessSteps(s, pres, steps, 1.55);
    // Pros/cons
    addInfoCard(s, pres, 0.25, 4.0, 4.55, 0.8, "優點", "門檻最低、5 分鐘上手、不需要技術背景", C.green);
    addInfoCard(s, pres, 5.2, 4.0, 4.55, 0.8, "風險", "AI 幻覺引用、手動驗證耗時、無法批量處理", C.orange);
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 7: 模式 2 — Zotero + GAS + Obsidian（簡易版）
  // ══════════════════════════════════════════════════════════
  {
    const s = addContentSlide(pres, "模式 2：知識管理整合 AI（進階）");
    addBadge(s, pres, 0.3, 0.9, 0.5, 0.45, "2", C.navy);
    s.addText("學術知識管理 + AI 增強 — 最成熟的研究組合", { x: 0.95, y: 0.92, w: 8.5, h: 0.42, fontSize: 14, bold: true, color: C.darkText, valign: "middle", margin: 0 });
    const steps = [
      { n: "1", text: "Deep Research 探索研究方向", sub: "ChatGPT / Claude / Gemini" },
      { n: "2", text: "AI 收集相關文獻 DOI List", sub: "確認方向後批量收集" },
      { n: "3", text: "DOI 導入 Zotero + 驗證真實性", sub: "逐一確認文獻存在且正確" },
      { n: "4", text: "GAS 自動分析 PDF → 生成 MD 筆記", sub: "透過 AI API 批量摘要文獻" },
      { n: "5", text: "MD 匯入 Obsidian + 寫入觀點", sub: "逐一確認，加入個人註解" },
      { n: "6", text: "AI 整理研究框架初版", sub: "MD 筆記 + 研究架構 → AI 產出框架" },
      { n: "7", text: "深度概念整理與跨文獻連結", sub: "Obsidian Graph View 知識圖譜" },
    ];
    steps.forEach((st, i) => {
      const y = 1.45 + i * 0.44;
      const bg = i % 2 === 0 ? C.offwhite : C.white;
      const stepColor = i < 2 ? C.teal : (i < 4 ? C.navy : (i < 6 ? C.gold : C.green));
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.3, y, w: 9.4, h: 0.38, fill: { color: bg }, rectRadius: 0.04 });
      s.addShape(pres.shapes.OVAL, { x: 0.4, y: y + 0.03, w: 0.3, h: 0.3, fill: { color: stepColor } });
      s.addText(st.n, { x: 0.4, y: y + 0.03, w: 0.3, h: 0.3, fontSize: 11, bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });
      s.addText(st.text, { x: 0.85, y, w: 4.3, h: 0.38, fontSize: 12, bold: true, color: C.darkText, valign: "middle", margin: 0 });
      s.addText(st.sub, { x: 5.3, y, w: 4.2, h: 0.38, fontSize: 11, color: C.grayText, valign: "middle", margin: 0 });
    });
    addTipBox(s, pres, 0.3, 4.7, 9.4, 0.42, "工具：Zotero + GAS (Google Apps Script + AI API) + Obsidian + Zotero Integration Plugin");
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 8: 模式 3 — IDE + API 自動化（簡易版）
  // ══════════════════════════════════════════════════════════
  {
    const s = addContentSlide(pres, "模式 3：IDE 驅動 + API 自動驗證（系統化）");
    addBadge(s, pres, 0.3, 0.9, 0.5, 0.45, "3", C.gold, C.navy);
    s.addText("本課程的核心模式 — 用程式化方法確保研究品質", { x: 0.95, y: 0.92, w: 8.5, h: 0.42, fontSize: 14, bold: true, color: C.darkText, valign: "middle", margin: 0 });
    const phases = [
      { n: "1", title: "IDE 建立\n研究專案", desc: "VS Code / Cursor\nMarkdown + YAML\nGit 版本控制", color: C.teal },
      { n: "2", title: "AI 收集 +\nAPI 驗證", desc: "CrossRef API\nSemantic Scholar\nOpenAlex 交叉確認", color: C.navy },
      { n: "3", title: "自動化\n文獻處理", desc: "批量下載 PDF\nAI 自動摘要\nGAS 批量分析", color: C.gold },
      { n: "4", title: "架構設計 +\n實驗執行", desc: "IMRaD 架構\nQMD + BibTeX\nGPU + TG 監控", color: C.green },
    ];
    addProcessSteps(s, pres, phases, 1.55);
    // Key difference
    s.addShape(pres.shapes.RECTANGLE, { x: 0.25, y: 4.05, w: 9.5, h: 0.7, fill: { color: C.offwhite } });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.25, y: 4.05, w: 0.07, h: 0.7, fill: { color: C.orange } });
    s.addText("關鍵差異：模式 3 用 API 自動驗證取代手動確認 — 杜絕虛構引用問題", { x: 0.5, y: 4.05, w: 9.0, h: 0.7, fontSize: 13, bold: true, color: C.orange, valign: "middle", margin: 0 });
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 9 (original 2): Why this workshop?
  // ══════════════════════════════════════════════════════════
  {
    const s = addContentSlide(pres, "\u70ba\u4ec0\u9ebc\u9700\u8981\u9019\u5802\u8ab2\uff1f");
    // Left: Pain points
    addInfoCard(s, pres, 0.25, 0.95, 4.55, 1.35,
      "\u7814\u7a76\u75db\u9ede",
      "\u2022 \u6587\u737b\u67e5\u627e\u8017\u6642\u8017\u529b\uff0cAI \u7522\u51fa\u7684 DOI \u4e0d\u53ef\u4fe1\n\u2022 \u8ad6\u6587\u64b0\u5beb\u7e41\u7463\uff0c\u683c\u5f0f\u53cd\u8986\u8abf\u6574\n\u2022 \u54c1\u8cea\u5be9\u67e5\u9760\u4eba\u5de5\u2014\u2014\u907a\u6f0f\u7387\u9ad8\n\u2022 \u5be6\u9a57\u76e3\u63a7\u7121\u6cd5\u9060\u7aef\u8ffd\u8e64",
      C.orange
    );
    addInfoCard(s, pres, 5.2, 0.95, 4.55, 1.35,
      "AI \u89e3\u65b9",
      "\u2022 CrossRef/Semantic Scholar API \u591a\u91cd\u9a57\u8b49\n\u2022 QMD + YAML \u4e00\u9375\u8f49\u63db\u591a\u671f\u520a\u683c\u5f0f\n\u2022 Claude\u00d7ChatGPT\u00d7Gemini \u4e09 AI \u5e73\u884c\u5be9\u67e5\n\u2022 Telegram Bot \u4e09\u5c64\u5373\u6642\u76e3\u63a7",
      C.green
    );
    // Arrow between
    s.addText("\u27A1", {
      x: 4.65, y: 1.3, w: 0.7, h: 0.5,
      fontSize: 24, color: C.teal, align: "center", valign: "middle", margin: 0,
    });

    // Bottom: key difference
    addInfoCard(s, pres, 0.25, 2.55, 9.5, 2.55,
      "\u672c\u5de5\u4f5c\u574a\u7684\u6838\u5fc3\u5dee\u7570",
      "\u4e00\u822c AI \u8ab2\u7a0b                     \u672c\u5de5\u4f5c\u574a\n" +
      "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500     \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n" +
      "\u6559 ChatGPT \u600e\u9ebc\u7528              \u6559\u5f9e\u6982\u5ff5\u5230\u6295\u7a3f\u7684\u7aef\u5230\u7aef\u6d41\u7a0b\n" +
      "\u5de5\u5177\u5c0e\u5411                         \u6d41\u7a0b\u5c0e\u5411\uff0c\u5de5\u5177\u670d\u52d9\u6d41\u7a0b\n" +
      "\u55ae\u9ede\u793a\u7bc4                         \u7cfb\u7d71\u5316\u81ea\u52d5\u5316\uff08Skills + Agents + Commands\uff09\n" +
      "\u7121\u54c1\u8cea\u4fdd\u8b49                     \u5167\u5efa\u591a\u7dad\u5ea6\u5be9\u67e5 + P0-P3 \u5206\u7d1a\n" +
      "\u7121\u5f8c\u7e8c\u8ffd\u8e64                     \u63d0\u4f9b\u5b8c\u6574\u7cfb\u7d71\u53ef\u5e36\u8d70\u90e8\u7f72",
      C.navy
    );
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 3: Target Audience
  // ══════════════════════════════════════════════════════════
  {
    const s = addContentSlide(pres, "\u8ab2\u7a0b\u5b9a\u4f4d\u8207\u53d7\u773e");
    // L1D2 card
    addInfoCard(s, pres, 0.25, 0.95, 4.55, 2.2,
      "Day 1\uff1aL1D2 \u521d\u968e\u9032\u968e",
      "\u524d\u63d0\uff1a\u7528\u904e ChatGPT/Claude\n" +
      "\u91cd\u5fc3\uff1a\u6982\u5ff5\u63a2\u7d22 + \u6587\u737b\u7814\u7a76\n" +
      "\u7522\u51fa\uff1a\u7814\u7a76\u65b9\u5411 + \u6587\u737b\u7ba1\u7406\u7cfb\u7d71\n" +
      "\u5de5\u5177\uff1aClaude Chat + Prompt Engineering\n" +
      "AI \u89d2\u8272\uff1a\u300c\u8070\u660e\u7684\u52a9\u6559\u300d\n\n" +
      "\u9069\u5408\uff1a\u7814\u7a76\u751f\u3001\u535a\u58eb\u751f\u3001\u7522\u5b78\u5408\u4f5c\u7814\u7a76\u54e1",
      C.teal
    );
    // L2D1 card
    addInfoCard(s, pres, 5.2, 0.95, 4.55, 2.2,
      "Day 2\uff1aL2D1 \u4e2d\u968e\u5165\u9580",
      "\u524d\u63d0\uff1a\u5b8c\u6210 Day 1\u3001\u6703\u5beb\u7d50\u69cb\u5316 Prompt\n" +
      "\u91cd\u5fc3\uff1a\u5be6\u9a57\u8a2d\u8a08 + \u8ad6\u6587\u64b0\u5beb + \u54c1\u8cea\u4fdd\u8b49\n" +
      "\u7522\u51fa\uff1a\u8ad6\u6587\u521d\u7a3f\u6846\u67b6 + \u54c1\u8cea\u5be9\u67e5\u5831\u544a\n" +
      "\u5de5\u5177\uff1aClaude Code + QMD + BibTeX\n" +
      "AI \u89d2\u8272\uff1a\u300c\u7814\u7a76\u5718\u968a\u300d\uff088 \u500b\u5c08\u5bb6 Agent\uff09\n\n" +
      "\u9069\u5408\uff1a\u6709\u660e\u78ba\u7814\u7a76\u4e3b\u984c\u7684\u7814\u7a76\u751f/\u535a\u58eb\u751f",
      C.purple
    );
    // Bottom: Prerequisites
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.25, y: 3.4, w: 9.5, h: 1.7,
      fill: { color: C.lightBlue },
    });
    s.addText("\u5b78\u54e1\u524d\u7f6e\u6e96\u5099", {
      x: 0.45, y: 3.48, w: 4, h: 0.3,
      fontSize: 13, bold: true, color: C.navy, margin: 0,
    });
    s.addText(
      "Day 1 \u524d\uff1a\u8a3b\u518a Claude \u5e33\u865f + \u6e96\u5099\u7814\u7a76\u4e3b\u984c + \u5b89\u88dd VS Code\uff08\u53ef\u9078\uff09\n" +
      "Day 2 \u524d\uff1a\u5b89\u88dd Claude Code CLI + \u5b89\u88dd Quarto + \u6e96\u5099 5 \u7bc7 PDF \u6587\u737b",
      {
        x: 0.45, y: 3.82, w: 9.1, h: 1.1,
        fontSize: 11, color: C.darkText, margin: 0,
        lineSpacingMultiple: 1.4,
      }
    );
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 4: 11 Phase Workflow Overview
  // ══════════════════════════════════════════════════════════
  {
    const s = addContentSlide(pres, "\u5b8c\u6574\u5de5\u4f5c\u6d41\u7a0b\uff1a11 Phase \u7e3d\u89bd");
    // Row 1: Phase 1-4
    const row1 = [
      { n: "P1", title: "\u6982\u5ff5\u63a2\u7d22", desc: "AI \u5c0d\u8a71\n\u65b9\u5411\u78ba\u8a8d", color: C.teal },
      { n: "P2", title: "\u6587\u737b\u8abf\u7814", desc: "DOI\u2192API\u9a57\u8b49\nZotero\u2192Obsidian", color: C.navyLight },
      { n: "P3", title: "\u7814\u7a76\u5b9a\u4f4d", desc: "Research Gap\n\u4e3b\u7de8\u5206\u6790", color: C.purple },
      { n: "P4", title: "\u8ad6\u6587\u67b6\u69cb", desc: "IMRaD \u8a2d\u8a08\nMD\u2192QMD\u2192YAML", color: C.navy },
    ];
    addProcessSteps(s, pres, row1, 0.95);
    // Row 2: Phase 5-8
    const row2 = [
      { n: "P5", title: "\u5be6\u9a57\u8a2d\u8a08", desc: "IDE + Colab\n\u9060\u7aef 3090", color: C.teal },
      { n: "P6", title: "\u5be6\u9a57\u57f7\u884c", desc: "GPU \u76e3\u63a7\nTG Bot \u901a\u77e5", color: C.navyLight },
      { n: "P7", title: "\u6578\u64da\u5206\u6790", desc: "Skill \u9a57\u8b49\n\u4e09\u89d2\u6aa2\u67e5", color: C.purple },
      { n: "P8", title: "\u8ad6\u6587\u64b0\u5beb", desc: "QMD\u2192TeX\nSVG \u5411\u91cf\u5716", color: C.navy },
    ];
    addProcessSteps(s, pres, row2, 3.35);
    // Label Day 1 / Day 2
    addBadge(s, pres, 0.25, 0.78, 0.8, 0.22, "Day 1", C.gold, C.navy);
    addBadge(s, pres, 5.35, 3.18, 0.8, 0.22, "Day 2", C.gold, C.navy);
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 5: Workflow continued (Phase 9-11) + tool ecosystem
  // ══════════════════════════════════════════════════════════
  {
    const s = addContentSlide(pres, "AI \u5de5\u5177\u751f\u614b\u7cfb + \u6d41\u7a0b\u7e8c\u7bc7");
    // Phase 9-11
    const row3 = [
      { n: "P9", title: "\u54c1\u8cea\u5be9\u67e5", desc: "\u4e09 AI \u5e73\u884c\u5be9\u67e5\nP0-P3 \u5206\u7d1a", color: C.green },
      { n: "P10", title: "\u6295\u7a3f\u6e96\u5099", desc: "Cover Letter\n10\u9805\u7d20\u6750\u6e05\u55ae", color: C.teal },
      { n: "P11", title: "\u5be9\u7a3f\u56de\u8986", desc: "Rebuttal Matrix\n\u9010\u689d\u56de\u61c9", color: C.navy },
    ];
    addProcessSteps(s, pres, row3, 0.95);

    // Tool ecosystem stats
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.25, y: 3.4, w: 9.5, h: 1.8,
      fill: { color: C.white }, shadow: makeShadow(0.1),
    });
    s.addText("\u5de5\u5177\u751f\u614b\u7cfb\u7e3d\u89bd", {
      x: 0.45, y: 3.48, w: 3, h: 0.3,
      fontSize: 14, bold: true, color: C.navy, margin: 0,
    });
    // Four stat boxes
    const stats = [
      { label: "24 Skills", desc: "\u5c08\u696d\u77e5\u8b58\u5eab", color: C.teal },
      { label: "8 Agents", desc: "AI \u5c08\u5bb6\u5718\u968a", color: C.purple },
      { label: "5 Commands", desc: "\u4e00\u9375\u5de5\u4f5c\u6d41", color: C.navy },
      { label: "4 APIs", desc: "\u6587\u737b\u9a57\u8b49\u670d\u52d9", color: C.green },
    ];
    stats.forEach((st, i) => {
      const bx = 0.45 + i * 2.35;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
        x: bx, y: 3.9, w: 2.1, h: 1.1,
        fill: { color: st.color }, rectRadius: 0.08,
        shadow: makeShadow(0.1),
      });
      s.addText(st.label, {
        x: bx, y: 3.98, w: 2.1, h: 0.55,
        fontSize: 22, bold: true, color: C.white,
        align: "center", valign: "middle", margin: 0,
      });
      s.addText(st.desc, {
        x: bx, y: 4.5, w: 2.1, h: 0.4,
        fontSize: 11, color: C.mint,
        align: "center", valign: "middle", margin: 0,
      });
    });
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 6: Day 1 Section Divider
  // ══════════════════════════════════════════════════════════
  addSectionDivider(pres,
    "Day 1: AI \u7814\u7a76\u57fa\u790e",
    "\u5f9e\u6982\u5ff5\u63a2\u7d22\u5230\u6587\u737b\u7ba1\u7406\u7cfb\u7d71\u5efa\u7acb",
    "L1D2 \u521d\u968e\u9032\u968e"
  );

  // ══════════════════════════════════════════════════════════
  // SLIDE 7: Session 1 - Concept Exploration
  // ══════════════════════════════════════════════════════════
  {
    const s = addContentSlide(pres, "Session 1\uff1aAI \u6982\u5ff5\u63a2\u7d22\u8207\u7814\u7a76\u65b9\u5411\u78ba\u5b9a\uff0875 min\uff09");
    addInfoCard(s, pres, 0.25, 0.95, 4.55, 1.85,
      "\u7814\u7a76 Prompt \u5de5\u7a0b",
      "CARE \u6846\u67b6\uff1aContext / Action / Role / Example\n\n" +
      "5 \u5957\u7814\u7a76\u5c08\u7528 Prompt \u6a21\u677f\uff1a\n" +
      "\u2460 \u9818\u57df\u6383\u63cf  \u2461 Research Gap \u8b58\u5225\n" +
      "\u2462 \u53ef\u884c\u6027\u5206\u6790  \u2463 \u5275\u65b0\u6027\u5b9a\u4f4d\n" +
      "\u2464 \u7814\u7a76\u554f\u984c\u7cbe\u7149",
      C.teal
    );
    addInfoCard(s, pres, 5.2, 0.95, 4.55, 1.85,
      "\u591a\u8f2a\u5c0d\u8a71\u7b56\u7565",
      "\u6f38\u9032\u5f0f\u7e2e\u7126\u6cd5\uff08\u5bec \u2192 \u7a84\uff09\n\n" +
      "Extended Thinking \u6307\u4ee4\uff1a\n" +
      "think \u2192 think hard \u2192 ultrathink\n\n" +
      "\u6848\u4f8b\uff1a\u5f9e\u300c\u667a\u6167\u88fd\u9020\u300d\u5230\n" +
      "\u300cTraining-Free NILM\u300d\u7684 5 \u8f2a\u5c0d\u8a71",
      C.purple
    );
    // Practice box
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.25, y: 3.05, w: 9.5, h: 2.1,
      fill: { color: C.lightBlue },
    });
    s.addText("\u5373\u6642\u7df4\u7fd2\uff0815 min\uff09", {
      x: 0.45, y: 3.12, w: 4, h: 0.3,
      fontSize: 13, bold: true, color: C.navy, margin: 0,
    });
    s.addText(
      "\u2611 \u9078\u5b9a\u81ea\u5df1\u7684\u7814\u7a76\u4e3b\u984c\n" +
      "\u2611 \u7528 CARE \u6846\u67b6\u5beb\u51fa\u7b2c\u4e00\u500b Prompt\n" +
      "\u2611 \u8207 AI \u9032\u884c 3 \u8f2a\u5c0d\u8a71\uff0c\u78ba\u8a8d\u7814\u7a76\u65b9\u5411\n" +
      "\u2611 \u4e09\u89d2\u9a57\u8b49\uff1aAI \u5efa\u8b70 \u00d7 \u6587\u737b\u8b49\u64da \u00d7 \u5c0e\u5e2b\u610f\u898b",
      {
        x: 0.45, y: 3.48, w: 9.1, h: 1.5,
        fontSize: 11, color: C.darkText, margin: 0,
        lineSpacingMultiple: 1.4,
      }
    );
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 8: Session 2 - Literature + API Verification
  // ══════════════════════════════════════════════════════════
  {
    const s = addContentSlide(pres, "Session 2\uff1a\u6587\u737b\u8abf\u7814 + API \u9a57\u8b49 + Obsidian\uff0860 min\uff09");
    // Three-column cards
    addInfoCard(s, pres, 0.25, 0.95, 3.05, 2.3,
      "\u7a2e\u5b50 DOI + API \u9a57\u8b49",
      "AI \u7522\u51fa\u5019\u9078 DOI \u6e05\u55ae\n\n" +
      "\u22a2 CrossRef API\n  DOI \u5b58\u5728\u6027 + metadata\n" +
      "\u22a2 Semantic Scholar API\n  Abstract + \u5f15\u7528\u6578\n" +
      "\u22a2 OpenAlex API\n  OA \u72c0\u614b + \u6a5f\u69cb\n" +
      "\u22a2 AI \u8a9e\u7fa9\u6bd4\u5c0d\n  \u76f8\u95dc\u6027 1-5 \u5206",
      C.teal
    );
    addInfoCard(s, pres, 3.5, 0.95, 3.05, 2.3,
      "\u6279\u6b21\u532f\u5165 Zotero",
      "4 \u7a2e\u532f\u5165\u65b9\u5f0f\uff1a\n\n" +
      "\u2460 Magic Wand\uff08\u8cbc DOI\uff09\n" +
      "\u2461 Connector\uff08\u700f\u89bd\u5668\u5916\u639b\uff09\n" +
      "\u2462 BibTeX \u532f\u5165\n" +
      "\u2463 pyzotero API\uff08\u6279\u6b21\uff09\n\n" +
      "DOI \u2192 \u9a57\u8b49 \u2192 Zotero \u2192 BibTeX",
      C.purple
    );
    addInfoCard(s, pres, 6.75, 0.95, 3.0, 2.3,
      "Obsidian \u77e5\u8b58\u5716\u8b5c",
      "\u6587\u737b\u7b46\u8a18\u5361\u683c\u5f0f\uff1a\n\n" +
      "\u2022 YAML frontmatter\n  tags, doi, relevance\n" +
      "\u2022 [[\u96d9\u5411\u9023\u7d50]]\n  \u95dc\u806f\u6587\u737b\u7db2\u7d61\n" +
      "\u2022 Graph View\n  \u7bc0\u9ede=\u6587\u737b\u3001\u9023\u7dda=\u5f15\u7528\n" +
      "\u2022 \u5b64\u7acb\u7bc0\u9ede = \u907a\u6f0f\u6587\u737b",
      C.green
    );
    // Bottom highlight
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.25, y: 3.5, w: 9.5, h: 1.6,
      fill: { color: C.lightBlue },
    });
    s.addText("\u2622 \u95dc\u9375\u8b66\u544a\uff1aAI \u7522\u51fa\u7684 DOI \u4e0d\u80fd\u76f4\u63a5\u4fe1\u4efb\uff01\u5fc5\u9808\u7d93 API \u591a\u91cd\u9a57\u8b49\u624d\u80fd\u4f7f\u7528", {
      x: 0.45, y: 3.55, w: 9.1, h: 0.35,
      fontSize: 12, bold: true, color: C.orange, margin: 0,
    });
    s.addText(
      "\u6848\u4f8b\uff1a43 \u7bc7\u5f15\u7528\u5168\u90e8\u7d93 CrossRef \u9a57\u8b49 \u2192 \u767c\u73fe 3 \u7bc7 DOI \u932f\u8aa4\u3001 2 \u7bc7\u5e74\u4efd\u4e0d\u5339\u914d \u2192 \u4fee\u6b63\u5f8c\u5165\u5eab\n" +
      "\u73fe\u5834 Demo\uff1a\u7528 curl \u547c\u53eb CrossRef API \u9a57\u8b49\u4e00\u500b DOI\uff0c\u5c0d\u6bd4 AI \u7d66\u7684 metadata \u662f\u5426\u6b63\u78ba",
      {
        x: 0.45, y: 3.95, w: 9.1, h: 1.0,
        fontSize: 11, color: C.darkText, margin: 0,
        lineSpacingMultiple: 1.4,
      }
    );
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 9: Session 2b - Research Positioning + EIC Analysis
  // ══════════════════════════════════════════════════════════
  {
    const s = addContentSlide(pres, "Session 2b\uff1a\u7814\u7a76\u5b9a\u4f4d + \u671f\u520a\u5339\u914d + \u4e3b\u7de8\u5206\u6790\uff0890 min\uff09");
    // Left: Gap + Innovation
    addInfoCard(s, pres, 0.25, 0.95, 4.55, 2.0,
      "Research Gap + \u5275\u65b0\u6027\u5b9a\u4f4d",
      "\u6587\u737b\u5206\u985e\u77e9\u9663 \u2192 Gap \u8b58\u5225\n" +
      "literature-synthesis skill \u793a\u7bc4\n" +
      "/analyze-literature command\n\n" +
      "\u5275\u65b0\u6027\u4e09\u5c64\u6846\u67b6\uff1a\n" +
      "innovation-positioning skill\n" +
      "\u907f\u514d\u9677\u9631\uff1a\"Inspired by...\" / \"We improve...\"",
      C.teal
    );
    // Right: Journal matching
    addInfoCard(s, pres, 5.2, 0.95, 4.55, 2.0,
      "\u671f\u520a\u5339\u914d 6 \u7dad\u5ea6 + \u4e3b\u7de8\u5206\u6790",
      "\u2460 Scope \u5951\u5408\u5ea6 (35%)\n" +
      "\u2461 Impact Factor (15%)\n" +
      "\u2462 \u4e3b\u7de8\u7814\u7a76\u504f\u597d (20%)\n" +
      "\u2463 \u8fd1\u671f\u6536\u9304\u4e3b\u984c (15%)\n" +
      "\u2464 \u5be9\u7a3f\u9031\u671f (10%)\n" +
      "\u2465 OA/APC (5%)\n\n" +
      "\u4e3b\u7de8\u5206\u6790\uff1aGoogle Scholar \u2192 \u504f\u597d\u65b9\u5411",
      C.purple
    );
    // Bottom: Case
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.25, y: 3.2, w: 9.5, h: 1.9,
      fill: { color: C.lightBlue },
    });
    s.addText("\u6848\u4f8b\uff1a10 \u671f\u520a\u52a0\u6b0a\u8a55\u5206", {
      x: 0.45, y: 3.28, w: 5, h: 0.3,
      fontSize: 13, bold: true, color: C.navy, margin: 0,
    });
    s.addText(
      "Applied Energy (91) > IEEE TII (89) > Energy & Buildings (87) > SETA (82) > ...\n" +
      "\u6700\u7d42\u9078\u64c7 SETA \u7684\u539f\u56e0\uff1a\u5be9\u7a3f\u9031\u671f\u77ed\u3001\u63a5\u53d7\u7387\u9ad8\u3001\u8207\u7814\u7a76\u4e3b\u984c\u5951\u5408\n\n" +
      "\u4e3b\u7de8\u5206\u6790\u65b9\u6cd5\uff1a\n" +
      "\u2460 \u671f\u520a\u5b98\u7db2 \u2192 Editorial Board \u2192 EIC + AE\n" +
      "\u2461 Google Scholar \u67e5\u4e3b\u7de8 5 \u5e74\u767c\u8868 \u2192 h-index + \u7814\u7a76\u95dc\u9375\u8a5e\n" +
      "\u2462 \u5206\u6790 Editorial \u5167\u5bb9 \u2192 \u504f\u597d\u65b9\u5411\n" +
      "\u2463 \u8fd1 2 \u5e74\u6536\u9304\u6587\u7ae0\u6a19\u984c \u2192 AI topic clustering",
      {
        x: 0.45, y: 3.62, w: 9.1, h: 1.3,
        fontSize: 10.5, color: C.darkText, margin: 0,
        lineSpacingMultiple: 1.3,
      }
    );
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 10: Day 1 Practice & Outputs
  // ══════════════════════════════════════════════════════════
  {
    const s = addContentSlide(pres, "Day 1 \u5be6\u4f5c\u8207\u7522\u51fa");
    addInfoCard(s, pres, 0.25, 0.95, 4.55, 3.0,
      "\u5be6\u4f5c\u7df4\u7fd2 1\uff0830 min\uff09",
      "\u2611 \u9078\u5b9a\u7814\u7a76\u4e3b\u984c\uff0c\u7528 CARE \u5beb 3 \u500b Prompt\n" +
      "\u2611 \u7528 AI \u5c0d\u8a71 5 \u8f2a\u78ba\u5b9a\u7814\u7a76\u65b9\u5411\n" +
      "\u2611 \u7528 AI \u7522\u51fa 10 \u500b\u7a2e\u5b50 DOI\n" +
      "\u2611 \u7528 CrossRef API \u9a57\u8b49\u81f3\u5c11 3 \u500b DOI\n" +
      "\u2611 \u5efa\u7acb 3 \u7bc7 Obsidian \u6587\u737b\u7b46\u8a18\u5361\n  \uff08\u542b\u96d9\u5411\u9023\u7d50\uff09\n" +
      "\u2611 \u5efa\u7acb references.bib\uff08\u81f3\u5c11 5 \u7bc7\uff09\n" +
      "\u2611 \uff08\u9032\u968e\uff09Semantic Scholar API \u53d6 Abstract",
      C.teal
    );
    addInfoCard(s, pres, 5.2, 0.95, 4.55, 3.0,
      "Day 1 \u7522\u51fa\u6210\u679c",
      "\u2705 \u660e\u78ba\u7684\u7814\u7a76\u65b9\u5411 + Research Gap\n\n" +
      "\u2705 \u7d93 API \u9a57\u8b49\u7684\u6587\u737b\u6e05\u55ae\n\n" +
      "\u2705 Obsidian \u77e5\u8b58\u5716\u8b5c\uff08Graph View\uff09\n\n" +
      "\u2705 references.bib \u5f15\u7528\u6a94\n\n" +
      "\u2705 \u671f\u520a\u5339\u914d\u521d\u8a55\n\n" +
      "\u2705 \u7814\u7a76\u65b9\u5411\u8aaa\u660e\u66f8\uff08\u4f5c\u696d\uff09",
      C.green
    );
    // Time allocation
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.25, y: 4.2, w: 9.5, h: 0.95,
      fill: { color: C.lightBlue },
    });
    s.addText("\u6642\u9593\u5206\u914d\uff1a\u8b1b\u8ff0 3.0h (37.5%) + Demo 1.5h (18.8%) + \u5be6\u4f5c 2.0h (25.0%) + \u4f11\u606f/Q&A 1.5h (18.8%)", {
      x: 0.45, y: 4.25, w: 9.1, h: 0.85,
      fontSize: 11, color: C.navy, valign: "middle", margin: 0,
    });
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 11: Day 2 Section Divider
  // ══════════════════════════════════════════════════════════
  addSectionDivider(pres,
    "Day 2: \u5f9e\u67b6\u69cb\u5230\u6295\u7a3f",
    "\u8ad6\u6587\u64b0\u5beb\u3001\u54c1\u8cea\u4fdd\u8b49\u3001\u6295\u7a3f\u7b56\u7565",
    "L2D1 \u4e2d\u968e\u5165\u9580"
  );

  // ══════════════════════════════════════════════════════════
  // SLIDE 12: Session 3 - Paper Structure + Experiment
  // ══════════════════════════════════════════════════════════
  {
    const s = addContentSlide(pres, "Session 3\uff1a\u8ad6\u6587\u67b6\u69cb + \u5be6\u9a57\u898f\u5283\uff0885 min + 60 min\uff09");
    // Three cards
    addInfoCard(s, pres, 0.25, 0.95, 3.05, 2.0,
      "IMRaD + QMD \u67b6\u69cb",
      "I: \u80cc\u666f\u2192\u554f\u984c\u2192\u76ee\u7684\u2192\u8ca2\u7372\n" +
      "M: \u554f\u984c\u5b9a\u7fa9\u2192\u67b6\u69cb\u2192\u6f14\u7b97\u6cd5\n" +
      "R: \u4e3b\u7d50\u679c\u2192Ablation\u2192\u7d71\u8a08\n" +
      "aD: \u5206\u6790\u2192\u908a\u754c\u2192\u9650\u5236\n\n" +
      "MD \u2192 QMD\uff08\u52a0 YAML \u6a94\u982d\uff09\n" +
      "4 \u7a2e\u671f\u520a YAML \u914d\u7f6e\u7bc4\u4f8b",
      C.teal
    );
    addInfoCard(s, pres, 3.5, 0.95, 3.05, 2.0,
      "IDE + \u9060\u7aef GPU \u5be6\u9a57",
      "VS Code \u5de5\u4f5c\u6d41\uff1a\n" +
      "\u2022 Python + Jupyter Extension\n" +
      "\u2022 Quarto Extension\n" +
      "\u2022 Remote-SSH\u2192\u9060\u7aef GPU\n\n" +
      "\u4e09\u5c64\u57f7\u884c\u74b0\u5883\uff1a\n" +
      "\u672c\u5730 | Colab (T4/A100) | 3090",
      C.purple
    );
    addInfoCard(s, pres, 6.75, 0.95, 3.0, 2.0,
      "TG Bot + Skill \u9a57\u8b49",
      "TG Bot \u4e09\u5c64\u76e3\u63a7\uff1a\n" +
      "L1: 1min GPU / 5min \u65e5\u8a8c\n" +
      "L2: \u6bcf15min \u5b9a\u671f\u6aa2\u67e5\n" +
      "L3: \u7570\u5e38\u5373\u6642\u901a\u77e5\n\n" +
      "/analyze-experiment \u81ea\u52d5\u5316\uff1a\n" +
      "\u2192 data-validator\n" +
      "\u2192 stats-validator\n" +
      "\u2192 \u8ad6\u6587\u7528\u5831\u544a",
      C.green
    );
    // Bottom stats
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.25, y: 3.2, w: 9.5, h: 1.95,
      fill: { color: C.lightBlue },
    });
    s.addText("\u7d71\u8a08\u9a57\u8b49 + \u53ef\u91cd\u73fe\u6027", {
      x: 0.45, y: 3.28, w: 5, h: 0.3,
      fontSize: 13, bold: true, color: C.navy, margin: 0,
    });
    s.addText(
      "\u7d71\u8a08\u65b9\u6cd5\uff1aBootstrap CI / Mann-Whitney U / Cohen's d / Power Analysis\n" +
      "\u6578\u64da\u4e00\u81f4\u6027\u4e09\u89d2\u6aa2\u67e5\uff1aText \u2194 Table \u2194 Figure\uff08figure-table-checker skill\uff09\n" +
      "\u53ef\u91cd\u73fe\u6027\u8a2d\u8a08\uff1aseed=42 / YAML \u53c3\u6578\u6a94 / NumpyEncoder / metric-audit skill\n" +
      "\u7d50\u679c\u6d41\uff1aresults/*.json \u2192 EXPERIMENT_RESULTS.md \u2192 paper.qmd",
      {
        x: 0.45, y: 3.62, w: 9.1, h: 1.35,
        fontSize: 11, color: C.darkText, margin: 0,
        lineSpacingMultiple: 1.4,
      }
    );
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 13: Session 4 - Writing + Automation
  // ══════════════════════════════════════════════════════════
  {
    const s = addContentSlide(pres, "Session 4\uff1aQMD \u64b0\u5beb + Claude Code \u81ea\u52d5\u5316\uff0875+30 min\uff09");
    addInfoCard(s, pres, 0.25, 0.95, 4.55, 2.0,
      "\u8ad6\u6587\u64b0\u5beb + \u8f49\u6295\u7b56\u7565",
      "IMRaD \u5c0d\u61c9\u5404\u7ae0\u7bc0\u64b0\u5beb\u7b56\u7565\uff1a\n" +
      "\u2022 Intro: \u5012\u91d1\u5b57\u5854 + \u8ca2\u7372\u8072\u660e\n" +
      "\u2022 Related Work: Obsidian \u6587\u737b\u77e9\u9663 \u2192 \u6bb5\u843d\n" +
      "\u2022 Methods: \u5716\u8868\u5148\u884c\u3001AI \u751f\u6587\u5b57\n" +
      "\u2022 Results: \u6578\u64da\u8868 \u2192 AI \u7d71\u8a08\u5206\u6790\n\n" +
      "\u8f49\u6295\u7b56\u7565\uff1a\u6293\u53d6\u76ee\u6a19\u671f\u520a 100 \u7bc7\u6a19\u984c\n" +
      "\u2192 AI topic clustering \u2192 \u8abf\u6574 Title\n" +
      "\u2192 \u4fee\u6539 YAML format + CSL \u2192 quarto render",
      C.teal
    );
    addInfoCard(s, pres, 5.2, 0.95, 4.55, 2.0,
      "SVG + Claude Code Demo",
      "SVG \u5411\u91cf\u5716\u88fd\u4f5c\uff1a\n" +
      "\u2022 Python \u2192 SVG/PDF/PNG \u4e09\u683c\u5f0f\n" +
      "\u2022 Inkscape \u5f8c\u8655\u7406\uff1aSVG\u2192PDF/EPS\n" +
      "\u2022 QMD \u5f15\u7528\uff1a![](fig.pdf){#fig-label}\n\n" +
      "Claude Code 3 \u500b Demo\uff1a\n" +
      "\u2460 /review-paper \u2192 \u4e03\u7dad\u5ea6\u5831\u544a\n" +
      "\u2461 /analyze-experiment \u2192 \u7d71\u8a08\u5831\u544a\n" +
      "\u2462 /prepare-submission \u2192 Cover Letter",
      C.purple
    );
    // Practice 2
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.25, y: 3.2, w: 9.5, h: 1.9,
      fill: { color: C.lightBlue },
    });
    s.addText("\u5be6\u4f5c\u7df4\u7fd2 2\uff0815 min\uff09", {
      x: 0.45, y: 3.28, w: 4, h: 0.3,
      fontSize: 13, bold: true, color: C.navy, margin: 0,
    });
    s.addText(
      "\u2611 \u5efa\u7acb QMD \u8ad6\u6587\u9aa8\u67b6\uff08\u542b\u5b8c\u6574 YAML \u6a94\u982d\uff09\n" +
      "\u2611 \u8a2d\u5b9a bibliography + csl\n" +
      "\u2611 \u5beb\u51fa Abstract \u521d\u7a3f\uff08200 \u5b57\uff09\n" +
      "\u2611 \u52a0\u5165 3 \u500b\u5f15\u7528\uff0cquarto render \u9a57\u8b49\u683c\u5f0f\n" +
      "\u2611 \uff08\u9032\u968e\uff09\u7522\u51fa\u4e00\u5f35 SVG \u5716\u4e26\u5d4c\u5165 QMD",
      {
        x: 0.45, y: 3.62, w: 9.1, h: 1.3,
        fontSize: 11, color: C.darkText, margin: 0,
        lineSpacingMultiple: 1.4,
      }
    );
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 14: Session 5 - Quality + Submission
  // ══════════════════════════════════════════════════════════
  {
    const s = addContentSlide(pres, "Session 5\uff1a\u54c1\u8cea\u5be9\u67e5 + \u6295\u7a3f\u7b56\u7565\uff0890 min\uff09", C.navy);
    // Three AI parallel review
    addInfoCard(s, pres, 0.25, 0.95, 3.05, 2.3,
      "Claude Code \u5be9\u67e5",
      "\u4e03\u7dad\u5ea6\u8a55\u5206\u6846\u67b6\uff1a\n" +
      "\u2460 \u7d50\u69cb\u5b8c\u6574\u6027\n" +
      "\u2461 \u65b9\u6cd5\u8ad6\u56b4\u8b39\u6027\n" +
      "\u2462 \u5be6\u9a57\u8a2d\u8a08\n" +
      "\u2463 \u6578\u64da\u53ef\u4fe1\u5ea6\n" +
      "\u2464 \u5beb\u4f5c\u6e05\u6670\u5ea6\n" +
      "\u2465 \u5f15\u7528\u5b8c\u6574\u6027\n" +
      "\u2466 \u5275\u65b0\u8ca2\u7372\n\n" +
      "P0-P3 \u554f\u984c\u5206\u7d1a + Skills \u81ea\u52d5\u5316",
      C.teal
    );
    addInfoCard(s, pres, 3.5, 0.95, 3.05, 2.3,
      "ChatGPT \u5be9\u67e5",
      "\u5f37\u9805\uff1a\u7d50\u69cb/\u5beb\u4f5c\u6d41\u66a2\u5ea6\n\n" +
      "\u5be9\u67e5\u91cd\u9ede\uff1a\n" +
      "\u2022 \u6bb5\u843d\u908f\u8f2f\u9023\u8cab\u6027\n" +
      "\u2022 \u8ad6\u8ff0\u6d41\u66a2\u5ea6\n" +
      "\u2022 \u8a9e\u6cd5 + \u53ef\u8b80\u6027\n" +
      "\u2022 Passive voice \u6bd4\u4f8b\n\n" +
      "Custom Prompt \u5c08\u6848\u5be9\u67e5",
      C.gold
    );
    addInfoCard(s, pres, 6.75, 0.95, 3.0, 2.3,
      "Gemini \u5be9\u67e5",
      "\u5f37\u9805\uff1a\u4e8b\u5be6\u67e5\u6838/\u9577\u6587\u6aa2\u7d22\n\n" +
      "\u5be9\u67e5\u91cd\u9ede\uff1a\n" +
      "\u2022 \u5f15\u7528\u4e8b\u5be6\u6838\u5c0d\n" +
      "\u2022 \u6578\u64da\u8072\u660e\u9a57\u8b49\n" +
      "\u2022 \u6700\u65b0\u6587\u737b\u8986\u84cb\u6aa2\u67e5\n" +
      "\u2022 Deep Research \u6df1\u5ea6\u6aa2\u7d22\n\n" +
      "\u4e09\u4efd\u5831\u544a\u5408\u4f75 \u2192 \u6309 P0-P3 \u6392\u5e8f",
      C.green
    );
    // Bottom: Submission
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.25, y: 3.5, w: 9.5, h: 1.6,
      fill: { color: C.white }, shadow: makeShadow(0.1),
    });
    s.addText("\u6295\u7a3f\u7b56\u7565 + 10 \u9805\u7d20\u6750\u6e05\u55ae", {
      x: 0.45, y: 3.55, w: 5, h: 0.3,
      fontSize: 13, bold: true, color: C.navy, margin: 0,
    });
    s.addText(
      "\u2460 \u8ad6\u6587 PDF  \u2461 .tex \u6e90\u78bc  \u2462 Cover Letter  \u2463 \u9ad8\u89e3\u6790\u5716\u8868\uff08SVG/PDF/TIFF\uff09  \u2464 Supplementary\n" +
      "\u2465 CRediT  \u2466 Highlights  \u2467 Graphical Abstract  \u2468 Suggested Reviewers  \u2469 Data Availability\n\n" +
      "submission-bundle skill + /prepare-submission command \u4e00\u9375\u6aa2\u67e5",
      {
        x: 0.45, y: 3.88, w: 9.1, h: 1.1,
        fontSize: 10.5, color: C.darkText, margin: 0,
        lineSpacingMultiple: 1.35,
      }
    );
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 15: Day 2 Practice & Outputs
  // ══════════════════════════════════════════════════════════
  {
    const s = addContentSlide(pres, "Day 2 \u5be6\u4f5c\u8207\u7522\u51fa");
    addInfoCard(s, pres, 0.25, 0.95, 4.55, 2.5,
      "Day 2 \u6838\u5fc3\u7522\u51fa",
      "\u2705 \u5b8c\u6574 QMD \u8ad6\u6587\u9aa8\u67b6\uff08\u542b YAML \u6a94\u982d\uff09\n\n" +
      "\u2705 Abstract + 3 \u5f15\u7528 + \u683c\u5f0f\u9a57\u8b49\n\n" +
      "\u2705 SVG \u5411\u91cf\u5716\uff08\u9032\u968e\uff09\n\n" +
      "\u2705 Claude Code \u5be9\u67e5\u5831\u544a\uff08\u4e03\u7dad\u5ea6\uff09\n\n" +
      "\u2705 \u5e73\u884c\u5be9\u67e5\u6574\u5408\u5831\u544a\n\n" +
      "\u2705 research-workspace \u90e8\u7f72\u5b8c\u6210",
      C.green
    );
    addInfoCard(s, pres, 5.2, 0.95, 4.55, 2.5,
      "\u5b78\u54e1\u80fd\u5e36\u8d70\u7684\u7cfb\u7d71",
      "research-workspace.zip \u5305\u542b\uff1a\n\n" +
      "\u2022 24 Skills \u5c08\u696d\u77e5\u8b58\u5eab\n" +
      "\u2022 8 Agents AI \u5c08\u5bb6\u5718\u968a\n" +
      "\u2022 5 Commands \u4e00\u9375\u5de5\u4f5c\u6d41\n" +
      "\u2022 CLAUDE.md \u5ba2\u88fd\u5316\u6a21\u677f\n" +
      "\u2022 QMD \u8ad6\u6587\u6a21\u677f\uff084 \u7a2e\u671f\u520a\uff09\n" +
      "\u2022 Obsidian Vault \u7bc4\u4f8b\n" +
      "\u2022 API \u9a57\u8b49\u8173\u672c\n" +
      "\u2022 TG Bot \u8a2d\u5b9a\u6307\u5357",
      C.navy
    );
    // Time allocation
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.25, y: 3.7, w: 9.5, h: 1.45,
      fill: { color: C.lightBlue },
    });
    s.addText("\u6642\u9593\u5206\u914d\uff1a\u8b1b\u8ff0 3.0h (35%) + Demo 2.0h (24%) + \u5be6\u4f5c 1.5h (18%) + \u4f11\u606f/Q&A 2.0h (23%)", {
      x: 0.45, y: 3.75, w: 9.1, h: 0.45,
      fontSize: 11, color: C.navy, valign: "middle", margin: 0,
    });
    s.addText("\u8b1b\u8ff0:Demo:\u5be6\u4f5c = 46%:27%:27%\uff08\u5169\u5929\u5408\u8a08\uff09", {
      x: 0.45, y: 4.22, w: 9.1, h: 0.35,
      fontSize: 12, bold: true, color: C.teal, valign: "middle", margin: 0,
    });
    s.addText(
      "\u5b78\u7fd2\u8def\u5f91\uff1a\u5373\u523b\u884c\u52d5\uff08\u672c\u9031\u90e8\u7f72\u7cfb\u7d71\uff09\u2192 \u77ed\u671f\u76ee\u6a19\uff081\u6708\u5b8c\u6210\u521d\u7a3f\uff09\u2192 \u4e2d\u671f\u76ee\u6a19\uff083\u6708\u6295\u7a3f\uff09",
      {
        x: 0.45, y: 4.6, w: 9.1, h: 0.4,
        fontSize: 11, color: C.darkText, valign: "middle", margin: 0,
      }
    );
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 16: Real Case Study
  // ══════════════════════════════════════════════════════════
  {
    const s = addContentSlide(pres, "\u771f\u5be6\u6848\u4f8b\uff1aNILM+LLM \u2192 SETA \u6295\u7a3f\u6b77\u7a0b");
    // Timeline
    const phases = [
      { label: "\u6982\u5ff5\u63a2\u7d22", time: "3 days", y: 0.95, color: C.teal },
      { label: "\u6587\u737b\u8abf\u7814\uff0843 \u7bc7 DOI\uff09", time: "5 days", y: 1.58, color: C.navyLight },
      { label: "IMRaD \u67b6\u69cb + \u5be6\u9a57", time: "10 days", y: 2.21, color: C.purple },
      { label: "QMD \u64b0\u5beb + SVG", time: "7 days", y: 2.84, color: C.navy },
      { label: "\u54c1\u8cea\u5be9\u67e5 + \u4fee\u6b63", time: "5 days", y: 3.47, color: C.green },
      { label: "SETA \u6295\u7a3f", time: "2 days", y: 4.1, color: C.gold },
    ];
    phases.forEach((p) => {
      // Timeline dot
      s.addShape(pres.shapes.OVAL, {
        x: 0.5, y: p.y + 0.12, w: 0.28, h: 0.28,
        fill: { color: p.color },
      });
      // Line
      if (p.y < 4.1) {
        s.addShape(pres.shapes.RECTANGLE, {
          x: 0.61, y: p.y + 0.40, w: 0.06, h: 0.35,
          fill: { color: C.grayText },
        });
      }
      // Label
      s.addText(p.label, {
        x: 1.0, y: p.y + 0.05, w: 3.5, h: 0.35,
        fontSize: 12, bold: true, color: C.darkText, margin: 0, valign: "middle",
      });
      s.addText(p.time, {
        x: 1.0, y: p.y + 0.32, w: 3.5, h: 0.25,
        fontSize: 10, color: C.grayText, margin: 0,
      });
    });
    // Right side: Key stats
    addInfoCard(s, pres, 5.0, 0.95, 4.75, 3.7,
      "\u95dc\u9375\u6578\u64da",
      "\u7e3d\u8017\u6642\uff1a~32 \u5929\uff08\u50b3\u7d71\u65b9\u5f0f\u9700 4-6 \u500b\u6708\uff09\n\n" +
      "AI \u53c3\u8207\u5ea6\uff1a65-70%\n\n" +
      "\u6587\u737b\uff1a43 \u7bc7 DOI\uff0c\u5168\u90e8 API \u9a57\u8b49\n\n" +
      "\u5be6\u9a57\uff1a3 \u500b\u6578\u64da\u96c6\uff0cF1 = 0.8488\n\n" +
      "\u5be9\u67e5\uff1a\u4e03\u7dad\u5ea6\u8a55\u5206 + P0-P3 \u5206\u7d1a\n\n" +
      "\u7d71\u8a08\uff1aBootstrap CI + Cohen's d + Power\n\n" +
      "\u5de5\u5177\uff1a24 Skills + 8 Agents + 5 Commands\n\n" +
      "\u683c\u5f0f\uff1aQMD \u2192 Elsevier PDF + .tex",
      C.navy
    );
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 17: Core Differentiation
  // ══════════════════════════════════════════════════════════
  {
    const s = addContentSlide(pres, "\u6838\u5fc3\u5dee\u7570\u5316\uff1a\u70ba\u4ec0\u9ebc\u9078\u64c7\u9019\u500b\u5de5\u4f5c\u574a\uff1f");
    // 5 key points
    const points = [
      { title: "\u7aef\u5230\u7aef\u5b8c\u6574\u6d41\u7a0b", desc: "11 Phase \u5f9e\u6982\u5ff5\u5230\u6295\u7a3f\uff0c\u975e\u55ae\u9ede\u6559\u5b78", color: C.teal },
      { title: "\u771f\u5be6\u6848\u4f8b\u9a57\u8b49", desc: "NILM+LLM \u8ad6\u6587\u5b8c\u6574\u6b77\u7a0b\uff0c\u975e\u865b\u69cb\u7bc4\u4f8b", color: C.purple },
      { title: "\u6587\u737b\u6b63\u78ba\u6027\u4fdd\u8b49", desc: "CrossRef/SS/OA \u591a\u91cd API \u9a57\u8b49\uff0c\u975e\u76f2\u4fe1 AI", color: C.navy },
      { title: "\u4e09 AI \u5e73\u884c\u5be9\u67e5", desc: "Claude\u00d7ChatGPT\u00d7Gemini \u4ea4\u53c9\u6aa2\u67e5\uff0c\u975e\u55ae\u4e00\u5de5\u5177", color: C.green },
      { title: "\u53ef\u5e36\u8d70\u7684\u7cfb\u7d71", desc: "research-workspace.zip \u5b8c\u6574\u90e8\u7f72\uff0c\u975e\u7d14\u77e5\u8b58", color: C.gold },
    ];
    points.forEach((p, i) => {
      const y = 0.95 + i * 0.85;
      s.addShape(pres.shapes.RECTANGLE, {
        x: 0.25, y, w: 9.5, h: 0.72,
        fill: { color: C.white }, shadow: makeShadow(0.08),
      });
      s.addShape(pres.shapes.RECTANGLE, {
        x: 0.25, y, w: 0.08, h: 0.72,
        fill: { color: p.color },
      });
      s.addShape(pres.shapes.OVAL, {
        x: 0.5, y: y + 0.11, w: 0.5, h: 0.5,
        fill: { color: p.color },
      });
      s.addText(String(i + 1), {
        x: 0.5, y: y + 0.11, w: 0.5, h: 0.5,
        fontSize: 16, bold: true, color: C.white,
        align: "center", valign: "middle", margin: 0,
      });
      s.addText(p.title, {
        x: 1.2, y: y + 0.05, w: 3.5, h: 0.35,
        fontSize: 14, bold: true, color: C.darkText, margin: 0, valign: "middle",
      });
      s.addText(p.desc, {
        x: 1.2, y: y + 0.37, w: 8.3, h: 0.3,
        fontSize: 11, color: C.grayText, margin: 0, valign: "middle",
      });
    });
  }

  // ══════════════════════════════════════════════════════════
  // SLIDE 18: Closing
  // ══════════════════════════════════════════════════════════
  {
    const s = pres.addSlide();
    s.background = { color: C.navy };
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0, y: 0, w: 10, h: 0.08, fill: { color: C.gold },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0, y: 0.08, w: 0.12, h: 5.545, fill: { color: C.teal },
    });
    s.addShape(pres.shapes.OVAL, {
      x: 7.2, y: 2.0, w: 3.5, h: 3.5,
      fill: { color: C.teal, transparency: 88 },
    });
    s.addShape(pres.shapes.OVAL, {
      x: 7.8, y: 2.8, w: 2.5, h: 2.5,
      fill: { color: C.gold, transparency: 85 },
    });
    s.addText("\u958b\u59cb\u4f60\u7684\nAI \u7814\u7a76\u4e4b\u65c5", {
      x: 0.4, y: 1.0, w: 7.5, h: 2.0,
      fontSize: 46, bold: true, color: C.white,
      fontFace: "Calibri", lineSpacingMultiple: 1.15,
    });
    s.addText("\u5f9e\u6982\u5ff5\u5230\u6295\u7a3f\uff0cAI \u662f\u4f60\u7684\u7814\u7a76\u5718\u968a", {
      x: 0.4, y: 3.1, w: 7.5, h: 0.55,
      fontSize: 17, color: C.gold, fontFace: "Calibri",
    });
    // Bottom
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0, y: 5.2, w: 10, h: 0.425,
      fill: { color: C.teal, transparency: 60 },
    });
    s.addText("Smart Manufacturing Research Lab  |  alan.chen75@gmail.com", {
      x: 0.4, y: 5.2, w: 9.2, h: 0.425,
      fontSize: 10, color: C.white, valign: "middle", margin: 0,
    });
  }

  // ── OUTPUT ──
  const path = require("path");
  const outPath = path.join(__dirname, "..", "dist", "AI_Research_Workshop_Course_Intro.pptx");
  await pres.writeFile({ fileName: outPath });
  console.log("Done! " + outPath);
}

main().catch(console.error);
