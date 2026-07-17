#!/usr/bin/env python3
"""
paper-logic-audit: 論文送審前硬檢查 (VENDORED for the engine — Gate F backend).

Vendored verbatim from ``~/.claude/skills/paper-logic-audit/audit.py`` (2026-06-15)
so the engine is self-contained. The 5 scan functions (formulas / quantifiers /
attribution / contradictions / cherry-pick) and their verdict logic are UNCHANGED;
only an importable ``run_audit(text, result_files, table_data)`` wrapper was added so
Gate F can call the 7-scan in-process (no CLI shell-out, no report file written).

Usage (CLI, unchanged): python3 logic_audit.py --paper paper.qmd --results results/

Exit codes: 0 = all pass; 1 = has FAIL items.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from collections import defaultdict


# ============================================================
# Scan 1: 公式極端值測試
# ============================================================
INEQ_PATTERN = re.compile(
    r'(\$[^$]*?[<>≤≥][^$]*?\$)|(\\begin\{equation\}.*?\\end\{equation\})',
    re.DOTALL,
)
INEQ_DIRECTION = re.compile(r'([^<>≤≥=\s\\]+)\s*(\\[lg]eq?|[<>≤≥])\s*([^<>≤≥=\s\\$]+)')


def scan_formulas(text):
    """Extract inequalities/equations. Output template for manual extreme-value check."""
    hits = []
    for m in INEQ_PATTERN.finditer(text):
        formula = m.group(0)
        ctx_start = max(0, m.start() - 200)
        ctx_end = min(len(text), m.end() + 200)
        context = text[ctx_start:ctx_end].replace('\n', ' ')
        direction_hint = _infer_direction(context)
        hits.append({
            'formula': formula.strip()[:80],
            'context_snippet': context[:240],
            'text_direction_hint': direction_hint,
            'auto_verdict': 'REVIEW_NEEDED',
        })
    return hits


def _infer_direction(context):
    """Guess whether prose says 'must be below/above critical'."""
    below = re.search(r'\b(below|under|less than|stay below|must not exceed|upper bound|ceiling)\b', context, re.I)
    above = re.search(r'\b(above|exceed|greater than|lower bound|at least|minimum)\b', context, re.I)
    if below and not above:
        return 'prose implies UPPER BOUND (<=)'
    if above and not below:
        return 'prose implies LOWER BOUND (>=)'
    return 'prose direction unclear'


# ============================================================
# Scan 2: Claim 量詞精確度 + 數字來源追溯
# ============================================================
# Thousands-separated form FIRST so 365,049.852 matches as one token instead
# of fragments (365 / 049.852) that can never trace back to evidence — a
# scanner-manufactured unfixable finding (live: v3_e9f0eae7e200, 2026-07-17,
# healer burned 6 repair rounds against it). The ',' in the lookbehind stops
# fragment matches after a misplaced separator (980510,598302 yields one
# untraceable token, not two), keeping malformed groupings flagged yet
# healable: reformat to well-formed groups -> normalizes -> traces -> passes.
NUMBER_PATTERN = re.compile(
    r'(?<![\w.,])'
    r'([≥≤<>]?\s*(?:\d{1,3}(?:,\d{3})+(?:\.\d{1,4})?|\d{1,6}(?:\.\d{1,4})?)[%×]?)'
    r'(?![\w.])'
)
APPROX_NUMBER = re.compile(r'[≥≤<>]\s*\d+(?:\.\d+)?[%]?')


def scan_quantifiers(text, result_files):
    """Numbers in paper must be traceable to JSON sources. Approximations (>=X) flagged."""
    # Collect all numbers from result JSONs
    source_numbers = set()
    for fp in result_files:
        try:
            data = json.load(open(fp))
            source_numbers.update(_extract_numbers(data))
        except Exception:
            continue

    findings = []
    for m in NUMBER_PATTERN.finditer(text):
        num_str = m.group(1).strip()
        line_start = text.rfind('\n', 0, m.start()) + 1
        line_end = text.find('\n', m.end())
        line = text[line_start:line_end if line_end != -1 else len(text)].strip()

        # Skip trivial numbers (likely formula constants, not empirical claims)
        try:
            v = float(re.sub(r'[≥≤<>%×\s,]', '', num_str))
        except ValueError:
            continue
        if v == 0 or v == 1 or v == 100 and '%' not in num_str:
            continue

        # Check if number appears in any source JSON. Magnitude comparison on
        # both sides: the pattern never captures a leading minus (hyphens are
        # ambiguous in prose), so signed evidence values could never trace.
        trace_found = any(
            abs(abs(v) - abs(s)) < 0.05 * max(abs(v), 1) for s in source_numbers if s
        )
        is_approx = bool(APPROX_NUMBER.search(num_str))

        if not trace_found:
            findings.append({
                'number': num_str,
                'line': line[:160],
                'verdict': 'NO_SOURCE' if not is_approx else 'NO_SOURCE_AND_APPROX',
            })
        elif is_approx:
            findings.append({
                'number': num_str,
                'line': line[:160],
                'verdict': 'APPROX (consider exact value)',
            })
    return findings


def _extract_numbers(obj, acc=None):
    if acc is None:
        acc = set()
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        acc.add(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _extract_numbers(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _extract_numbers(v, acc)
    elif isinstance(obj, str):
        for m in re.finditer(r'-?\d+\.?\d*', obj):
            try:
                acc.add(float(m.group()))
            except ValueError:
                pass
    return acc


# ============================================================
# Scan 3: 歸因動詞強度
# ============================================================
STRONG_VERBS = ['dominates', 'dominate', 'causes', 'cause', 'drives', 'drive',
                'determines', 'determine', 'proves', 'prove', 'demonstrates causality']
MEDIUM_VERBS = ['correlates with', 'is associated with', 'linked to', 'predicts']
WEAK_VERBS = ['suggests', 'is consistent with', 'indicates', 'hints at']


def scan_attribution(text):
    """Find strong causal verbs; flag those near small-N evidence."""
    findings = []
    for verb in STRONG_VERBS:
        for m in re.finditer(r'\b' + re.escape(verb) + r'\b', text, re.I):
            ctx_start = max(0, m.start() - 300)
            ctx_end = min(len(text), m.end() + 300)
            ctx = text[ctx_start:ctx_end]
            n_matches = re.findall(r'\b[nN]\s*=\s*(\d+)\b|\b(\d+)\s+(?:points?|samples?|pairs?|models?|cases?)\b', ctx)
            n_values = [int(x) for pair in n_matches for x in pair if x]
            min_n = min(n_values) if n_values else None

            line_start = text.rfind('\n', 0, m.start()) + 1
            line_end = text.find('\n', m.end())
            line = text[line_start:line_end if line_end != -1 else len(text)].strip()

            if min_n is None:
                verdict = 'STRONG_VERB_NO_N (specify sample size)'
            elif min_n < 3:
                verdict = f'FAIL: N={min_n} too small for "{verb}" — use weak verb'
            elif min_n < 10:
                verdict = f'DOWNGRADE: N={min_n}, suggest medium verb like "correlates with"'
            else:
                verdict = f'OK: N={min_n}'

            findings.append({
                'verb': verb,
                'line': line[:160],
                'n': min_n,
                'verdict': verdict,
            })
    return findings


# ============================================================
# Scan 4: 內部矛盾（checklist 推薦 vs results）
# ============================================================
RECOMMEND_PATTERN = re.compile(
    r'\b(select|choose|use|adopt|recommend|opt for|prefer)\s+([^.;,]{5,80})',
    re.I,
)


def scan_contradictions(text):
    """Extract recommendations; flag those that mention options the paper describes as failing."""
    findings = []
    # Detect failure language
    fail_tokens = re.findall(
        r'\b(fails?|failed|unable|does not|not viable|inadequate|poor|underperform\w*)\b',
        text, re.I,
    )

    for m in RECOMMEND_PATTERN.finditer(text):
        verb = m.group(1)
        target = m.group(2).strip()
        line_start = text.rfind('\n', 0, m.start()) + 1
        line_end = text.find('\n', m.end())
        line = text[line_start:line_end if line_end != -1 else len(text)].strip()

        # Look for the target term earlier in text near failure language
        target_key = re.sub(r'\W+', ' ', target).strip()[:30]
        if len(target_key) < 4:
            continue
        target_mentions = [mm.start() for mm in re.finditer(re.escape(target_key), text, re.I) if mm.start() < m.start()]
        contradicted = False
        for pos in target_mentions:
            window = text[max(0, pos - 200):pos + 200]
            if any(tok in window.lower() for tok in ['fail', 'not pass', 'did not pass', 'underperform', 'poor']):
                contradicted = True
                break
        findings.append({
            'recommend': f'{verb} {target}',
            'line': line[:180],
            'verdict': 'CONTRADICTION' if contradicted else 'OK',
        })
    return [f for f in findings if f['verdict'] != 'OK']


# ============================================================
# Scan 5: Cherry-pick 偵測
# ============================================================
LADDER_PATTERN = re.compile(
    r'at\s+(\d+)\s*%[^,;.]{0,60}?(CVR|accuracy|error|IAE)[^,;.]{0,5}[=≈~]\s*([\d.]+)\s*%?',
    re.I,
)


def scan_cherry_pick(text, table_data):
    """Detect tiered claims; if multiple data points fit a tier but only one cited → cherry-pick."""
    findings = []
    for m in LADDER_PATTERN.finditer(text):
        tier_pct = int(m.group(1))
        metric = m.group(2)
        quoted_val = m.group(3)
        # Count matching rows in table_data
        matching = [r for r in table_data if r.get('tier_pct') == tier_pct]
        if len(matching) >= 2:
            cited_values = [r[metric.lower()] for r in matching if metric.lower() in r]
            line_start = text.rfind('\n', 0, m.start()) + 1
            line_end = text.find('\n', m.end())
            line = text[line_start:line_end if line_end != -1 else len(text)].strip()
            findings.append({
                'claim': f'at {tier_pct}%, {metric}≈{quoted_val}',
                'line': line[:160],
                'matching_n': len(matching),
                'all_values': cited_values,
                'verdict': f'CHERRY_PICK (use range {min(cited_values)}-{max(cited_values)})' if cited_values else 'CHERRY_PICK',
            })
    return findings


# ============================================================
# Report generation
# ============================================================
def generate_report(paper_path, scan_results):
    lines = [f'# Logic Audit Report — {paper_path}', '']
    total_fail = 0

    def section(title, items, cols, fail_filter=None):
        nonlocal total_fail
        lines.append(f'## {title}')
        if not items:
            lines.append('_(no findings)_\n')
            return
        lines.append('| ' + ' | '.join(cols) + ' |')
        lines.append('|' + '|'.join(['---'] * len(cols)) + '|')
        for item in items:
            row = [str(item.get(c.replace(' ', '_').lower(), item.get(c, '')))[:120].replace('|', '\\|').replace('\n', ' ') for c in cols]
            lines.append('| ' + ' | '.join(row) + ' |')
            if fail_filter and fail_filter(item):
                total_fail += 1
        lines.append('')

    section('Scan 1: 公式極端值測試',
            scan_results['formulas'],
            ['formula', 'text_direction_hint', 'auto_verdict'])

    section('Scan 2: Claim 量詞精確度',
            scan_results['quantifiers'],
            ['number', 'line', 'verdict'],
            fail_filter=lambda x: 'NO_SOURCE' in x.get('verdict', ''))

    section('Scan 3: 歸因動詞強度',
            scan_results['attribution'],
            ['verb', 'n', 'line', 'verdict'],
            fail_filter=lambda x: 'FAIL' in x.get('verdict', ''))

    section('Scan 4: 內部矛盾',
            scan_results['contradictions'],
            ['recommend', 'line', 'verdict'],
            fail_filter=lambda x: x.get('verdict') == 'CONTRADICTION')

    section('Scan 5: Cherry-pick',
            scan_results['cherry_pick'],
            ['claim', 'matching_n', 'line', 'verdict'],
            fail_filter=lambda x: 'CHERRY_PICK' in x.get('verdict', ''))

    lines.insert(2, f'**Total FAIL items: {total_fail}**\n')
    if total_fail > 0:
        lines.insert(3, '⛔ **論文禁止送審，修正後重跑。**\n')
    else:
        lines.insert(3, '✅ **通過硬檢查（仍建議跑 elite-reviewer-audit）**\n')
    return '\n'.join(lines), total_fail


# ============================================================
# Importable wrapper (Gate F backend — behaviour identical to the CLI scans)
# ============================================================
def run_audit(text: str, result_files=None, table_data=None) -> dict:
    """Run the 7-scan over already-loaded inputs and return a structured verdict.

    Mirrors ``main()`` exactly: same five scan calls, same FAIL counting as
    ``generate_report`` (the fail_filter per section), but takes inputs directly
    instead of file paths so Gate F can run it in-process. Returns::

        {"scan_results": {...}, "fail_items": [...], "total_fail": int}

    The CLI ``main()`` is left untouched and still produces the markdown report.
    """
    result_files = list(result_files or [])
    table_data = list(table_data or [])

    scan_results = {
        "formulas": scan_formulas(text),
        "quantifiers": scan_quantifiers(text, result_files),
        "attribution": scan_attribution(text),
        "contradictions": scan_contradictions(text),
        "cherry_pick": scan_cherry_pick(text, table_data),
    }

    # Same FAIL definition the markdown report uses (generate_report fail_filters).
    fail_items: list[dict] = []
    for f in scan_results["quantifiers"]:
        if "NO_SOURCE" in f.get("verdict", ""):
            fail_items.append({"scan": "quantifiers", **f})
    for f in scan_results["attribution"]:
        if "FAIL" in f.get("verdict", ""):
            fail_items.append({"scan": "attribution", **f})
    for f in scan_results["contradictions"]:
        if f.get("verdict") == "CONTRADICTION":
            fail_items.append({"scan": "contradictions", **f})
    for f in scan_results["cherry_pick"]:
        if "CHERRY_PICK" in f.get("verdict", ""):
            fail_items.append({"scan": "cherry_pick", **f})

    return {"scan_results": scan_results,
            "fail_items": fail_items,
            "total_fail": len(fail_items)}


# ============================================================
# Main
# ============================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--paper', required=True, help='Paper file (QMD or TeX)')
    ap.add_argument('--results', default='experiments/results',
                    help='Dir containing results JSONs')
    ap.add_argument('--table-json', help='Optional JSON with table rows for Scan 5')
    ap.add_argument('--output', default='logic_audit_report.md')
    args = ap.parse_args()

    paper_path = Path(args.paper)
    if not paper_path.exists():
        print(f'Paper not found: {paper_path}', file=sys.stderr)
        return 2
    text = paper_path.read_text()

    result_files = list(Path(args.results).rglob('*.json')) if Path(args.results).exists() else []
    table_data = []
    if args.table_json and Path(args.table_json).exists():
        table_data = json.load(open(args.table_json))

    scan_results = {
        'formulas': scan_formulas(text),
        'quantifiers': scan_quantifiers(text, result_files),
        'attribution': scan_attribution(text),
        'contradictions': scan_contradictions(text),
        'cherry_pick': scan_cherry_pick(text, table_data),
    }

    report, total_fail = generate_report(paper_path.name, scan_results)
    Path(args.output).write_text(report)
    print(f'Report: {args.output}  |  FAIL items: {total_fail}')
    return 0 if total_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
