# Submission Checklist — Computers in Biology and Medicine

## Manuscript Status: MVP Draft (Simulated Results)

### Pre-submission Checklist

- [x] Title page with author name, affiliation, email
- [x] Structured abstract (≤ 250 words)
- [x] Keywords: ECG, arrhythmia classification, Transformer, CNN, benchmark, deep learning
- [x] Number-sections enabled (pandoc manages numbering)
- [x] Figures: 4 referenced (PNG files needed before submission)
- [x] Tables: 5 included via Quarto includes
- [x] References: 39 verified (CrossRef + Semantic Scholar)
- [x] All references cited in text (0 orphans)
- [x] Cover letter prepared
- [x] Data Availability Statement included
- [x] CSL citation style: elsevier-with-titles

### Before Real Submission (Post-MVP)

- [ ] **Replace simulated data** with actual experimental results
- [ ] Remove ^S^ markers from all tables
- [ ] Generate actual figure PNGs (framework, architecture, Pareto, Grad-CAM)
- [ ] Run Phase 9 Stage 2 (Paper Review) + Stage 3 (Elite Audit)
- [ ] Verify all numeric values match between prose and tables
- [ ] Proofread for British/American English consistency
- [ ] Check Elsevier author guidelines for CBIOMED
- [ ] Prepare Highlights (3-5 bullet points, ≤ 85 characters each)
- [ ] Prepare Graphical Abstract (if required)
- [ ] Submit via Elsevier Editorial Manager

### Highlights (Draft)

1. First controlled benchmark: 6 architectures × 3 ECG datasets
2. Hybrid CNN-Transformer achieves best macro-F1 across all datasets
3. Pure CNNs offer 3-5x efficiency for edge deployment
4. Statistical significance testing confirms architecture rankings
5. Practical selection guidelines for clinical deployment scenarios

### Output Files

| File | Status | Description |
|------|--------|-------------|
| paper_draft_v0.qmd | ✅ Complete | Full manuscript (MVP, simulated data) |
| references.bib | ✅ Complete | 39 verified references with abstracts |
| metadata.json | ✅ Complete | Citation metadata and section mapping |
| cover_letter.md | ✅ Complete | Editor cover letter |
| elsevier-with-titles.csl | ✅ Complete | Citation style |
| tables/tbl_datasets.md | ✅ Complete | Dataset characteristics |
| tables/tbl_main.md | ✅ Complete | Main results (3 panels, simulated) |
| tables/tbl_compute.md | ✅ Complete | Computational efficiency (simulated) |
| tables/tbl_ablation.md | ✅ Complete | Ablation study (simulated) |
| tables/tbl_significance.md | ✅ Complete | Statistical significance (simulated) |
| figures/fig_specs.json | ✅ Complete | Figure specifications |
| figures/*.png | ❌ Pending | Actual figure files (post-MVP) |
| phase1_concept.md | ✅ Complete | Research concept |
| phase2_doi_report.md | ✅ Complete | DOI verification report |
| phase3_positioning.md | ✅ Complete | Research positioning |
| phase4_structure.md | ✅ Complete | Paper structure plan |
| research_contract.md | ✅ Complete | Research contract |
| quality_review_log.md | ✅ Complete | Quality review log |
| progress.md | ✅ Complete | Progress tracker |
