"""HTML/CSV validation reports."""
from __future__ import annotations

import csv
import html
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _pct(n: int, d: int) -> float:
    return (100.0 * n / d) if d else 0.0


def write_reports(
    out_dir: Path,
    *,
    results: list[dict[str, Any]],
    unsupported: list[dict[str, Any]],
    field_totals: dict[str, Any] | None = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    supported = [r for r in results if not r.get('unsupported')]
    passed = [r for r in supported if r.get('passed')]
    failed = [r for r in supported if not r.get('passed')]

    times = [r['elapsed_ms'] for r in supported if isinstance(r.get('elapsed_ms'), (int, float))]
    avg_time = statistics.mean(times) if times else 0.0
    slowest = sorted(
        [r for r in supported if r.get('elapsed_ms') is not None],
        key=lambda r: r['elapsed_ms'],
        reverse=True,
    )[:10]
    fastest = sorted(
        [r for r in supported if r.get('elapsed_ms') is not None],
        key=lambda r: r['elapsed_ms'],
    )[:10]

    cats = Counter(r.get('category') or 'Other' for r in failed)
    grounded_ok = sum(int(r.get('grounded_ok') or 0) for r in supported)
    grounded_total = sum(int(r.get('grounded_total') or 0) for r in supported)
    field_accuracy = (grounded_ok / grounded_total) if grounded_total else 0.0

    # summary.csv
    summary_rows = [
        ('total_supported', len(supported)),
        ('total_passed', len(passed)),
        ('total_failed', len(failed)),
        ('pass_percentage', round(_pct(len(passed), len(supported)), 3)),
        ('avg_parsing_time_ms', round(avg_time, 2)),
        ('field_level_accuracy', round(field_accuracy * 100, 3)),
        ('grounded_ok', grounded_ok),
        ('grounded_total', grounded_total),
        ('unsupported_count', len(unsupported)),
    ]
    with (out_dir / 'summary.csv').open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['metric', 'value'])
        w.writerows(summary_rows)
        w.writerow([])
        w.writerow(['failure_category', 'count'])
        for k, v in cats.most_common():
            w.writerow([k, v])

    # failures.csv
    with (out_dir / 'failures.csv').open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                'case_id', 'filename', 'category', 'signature', 'confidence',
                'elapsed_ms', 'field_accuracy', 'screenshot', 'parsed_json', 'log',
            ],
        )
        w.writeheader()
        for r in failed:
            paths = r.get('paths') or {}
            w.writerow({
                'case_id': r.get('case_id'),
                'filename': r.get('filename'),
                'category': r.get('category'),
                'signature': r.get('signature'),
                'confidence': r.get('confidence'),
                'elapsed_ms': r.get('elapsed_ms'),
                'field_accuracy': r.get('field_accuracy'),
                'screenshot': paths.get('screenshot', ''),
                'parsed_json': paths.get('parsed_json', ''),
                'log': paths.get('log', ''),
            })

    # unsupported.csv
    with (out_dir / 'unsupported.csv').open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=['filename', 'ext', 'size', 'reason'])
        w.writeheader()
        for u in unsupported:
            w.writerow({
                'filename': u.get('filename') or u.get('rel_name'),
                'ext': u.get('ext'),
                'size': u.get('size'),
                'reason': u.get('skip_reason') or u.get('reason'),
            })

    # grouped-failures
    grouped_dir = out_dir / 'grouped-failures'
    grouped_dir.mkdir(parents=True, exist_ok=True)
    by_cat: dict[str, list] = defaultdict(list)
    by_sig: dict[str, list] = defaultdict(list)
    for r in failed:
        cat = r.get('category') or 'Other'
        by_cat[cat].append(r)
        by_sig[f"{cat}::{r.get('signature') or 'unknown'}"].append(r)

    for cat, rows in by_cat.items():
        safe = cat.replace('/', '-').replace(' ', '_')
        path = grouped_dir / f'{safe}.json'
        path.write_text(json.dumps(rows, indent=2, default=str), encoding='utf-8')

    clusters = [
        {
            'key': k,
            'count': len(v),
            'category': k.split('::', 1)[0],
            'signature': k.split('::', 1)[1] if '::' in k else k,
            'examples': [x.get('filename') for x in v[:8]],
        }
        for k, v in sorted(by_sig.items(), key=lambda kv: -len(kv[1]))
    ]
    (grouped_dir / 'clusters.json').write_text(
        json.dumps(clusters, indent=2), encoding='utf-8'
    )

    # all results index
    (out_dir / 'results.json').write_text(
        json.dumps({'supported': supported, 'unsupported': unsupported}, indent=2, default=str),
        encoding='utf-8',
    )

    # summary.html
    def rows_html(items: list[dict], limit: int = 10) -> str:
        parts = []
        for r in items[:limit]:
            parts.append(
                '<tr>'
                f'<td>{html.escape(str(r.get("filename")))}</td>'
                f'<td>{html.escape(str(r.get("elapsed_ms")))}</td>'
                f'<td>{html.escape(str(r.get("confidence")))}</td>'
                f'<td>{html.escape(str(r.get("category") or ("PASS" if r.get("passed") else "")))}</td>'
                '</tr>'
            )
        return '\n'.join(parts)

    fail_links = []
    for r in failed[:50]:
        paths = r.get('paths') or {}
        shot = paths.get('screenshot', '')
        pj = paths.get('parsed_json', '')
        shot_html = f'<a href="{html.escape(shot)}">screenshot</a> ' if shot else ''
        json_html = f'<a href="{html.escape(pj)}">json</a>' if pj else ''
        fail_links.append(
            '<li>'
            f'<strong>{html.escape(str(r.get("filename")))}</strong> '
            f'[{html.escape(str(r.get("category")))}] '
            f'{shot_html}{json_html}'
            '</li>'
        )

    cat_rows = ''.join(
        f'<tr><td>{html.escape(k)}</td><td>{v}</td></tr>' for k, v in cats.most_common()
    )

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Resume Production Validation Report</title>
<style>
body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 2rem; color: #0f172a; background: #f8fafc; }}
h1,h2 {{ color: #0f172a; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(160px,1fr)); gap: 1rem; }}
.card {{ background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1rem; }}
.card .v {{ font-size: 1.6rem; font-weight: 700; }}
table {{ border-collapse: collapse; width: 100%; background: white; }}
th,td {{ border: 1px solid #e2e8f0; padding: .5rem .75rem; text-align: left; font-size: .9rem; }}
th {{ background: #f1f5f9; }}
.pass {{ color: #15803d; }}
.fail {{ color: #b91c1c; }}
section {{ margin: 2rem 0; }}
</style>
</head>
<body>
<h1>Resume Production E2E Validation</h1>
<section class="cards">
  <div class="card"><div>Processed (supported)</div><div class="v">{len(supported)}</div></div>
  <div class="card"><div>Passed</div><div class="v pass">{len(passed)}</div></div>
  <div class="card"><div>Failed</div><div class="v fail">{len(failed)}</div></div>
  <div class="card"><div>Pass %</div><div class="v">{_pct(len(passed), len(supported)):.2f}%</div></div>
  <div class="card"><div>Avg parse ms</div><div class="v">{avg_time:.0f}</div></div>
  <div class="card"><div>Field accuracy</div><div class="v">{field_accuracy*100:.2f}%</div></div>
  <div class="card"><div>Unsupported</div><div class="v">{len(unsupported)}</div></div>
</section>

<section>
<h2>Failure categories</h2>
<table><tr><th>Category</th><th>Count</th></tr>{cat_rows or '<tr><td colspan="2">None</td></tr>'}</table>
</section>

<section>
<h2>Slowest resumes</h2>
<table><tr><th>File</th><th>ms</th><th>Confidence</th><th>Category</th></tr>
{rows_html(slowest)}</table>
</section>

<section>
<h2>Fastest resumes</h2>
<table><tr><th>File</th><th>ms</th><th>Confidence</th><th>Category</th></tr>
{rows_html(fastest)}</table>
</section>

<section>
<h2>Failed cases (sample)</h2>
<ul>{''.join(fail_links) or '<li>None</li>'}</ul>
<p>See <code>failures.csv</code>, <code>screenshots/failed/</code>, <code>parsed-json/</code>, <code>logs/</code>, <code>grouped-failures/</code>.</p>
</section>

<section>
<h2>Unsupported documents</h2>
<p>{len(unsupported)} files excluded from pass percentage (see <code>unsupported.csv</code>).</p>
</section>
</body></html>
"""
    (out_dir / 'summary.html').write_text(doc, encoding='utf-8')
