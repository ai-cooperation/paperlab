#!/bin/bash
# QA Screenshot Generator
# Converts PPTX → PDF → JPG for visual inspection
# Requires: LibreOffice (soffice), poppler-utils (pdftoppm)

set -e

DIST_DIR="$(dirname "$0")/../dist"
QA_DIR="$(dirname "$0")/../qa_screenshots"

echo "=== PPTX QA Screenshot Generator ==="

# Day 1
if [ -f "$DIST_DIR/Day1_Full_AI研究基礎.pptx" ]; then
  echo "[1/4] Converting Day1 PPTX → PDF..."
  soffice --headless --convert-to pdf "$DIST_DIR/Day1_Full_AI研究基礎.pptx" --outdir "$DIST_DIR"
  echo "[2/4] Generating Day1 screenshots..."
  rm -rf "$QA_DIR/day1" && mkdir -p "$QA_DIR/day1"
  pdftoppm -jpeg -r 150 "$DIST_DIR/Day1_Full_AI研究基礎.pdf" "$QA_DIR/day1/s"
  echo "  Day1: $(ls "$QA_DIR/day1/"*.jpg | wc -l) slides"
fi

# Day 2
if [ -f "$DIST_DIR/Day2_Full_AI研究進階.pptx" ]; then
  echo "[3/4] Converting Day2 PPTX → PDF..."
  soffice --headless --convert-to pdf "$DIST_DIR/Day2_Full_AI研究進階.pptx" --outdir "$DIST_DIR"
  echo "[4/4] Generating Day2 screenshots..."
  rm -rf "$QA_DIR/day2" && mkdir -p "$QA_DIR/day2"
  pdftoppm -jpeg -r 150 "$DIST_DIR/Day2_Full_AI研究進階.pdf" "$QA_DIR/day2/s"
  echo "  Day2: $(ls "$QA_DIR/day2/"*.jpg | wc -l) slides"
fi

# Cleanup PDFs
rm -f "$DIST_DIR/"*.pdf

echo ""
echo "=== QA Checklist ==="
echo "[ ] Text overflow: no text exceeds element boundaries"
echo "[ ] Element overlap: titles do not overlap with body text"
echo "[ ] Margin consistency: content stays within 0.25\"~9.75\" horizontal"
echo "[ ] Element spacing: minimum 0.1\" between elements"
echo "[ ] Bottom nav bar: no content below y=5.35\""
echo "[ ] Chinese fonts: all CJK characters render correctly"
echo ""
echo "Screenshots saved to: $QA_DIR/"
