"""Framework HTML report fallback (used ONLY when Allure CLI is unavailable).

This is an honestly-labeled, data-rich static HTML report built from the real
recorded run results (``reports/.last_run/results.json`` or a history entry).
It is NOT an Allure report and is always presented as the fallback, together
with instructions for installing the Allure CLI to get the real thing.
"""

from __future__ import annotations

import html
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = PROJECT_ROOT / "reports" / "framework-report.html"


def _status_class(status: str) -> str:
    return {"passed": "passed", "failed": "failed", "error": "failed",
            "skipped": "skipped"}.get(status, "interrupted")


def generate_framework_report(run: dict, reason: str) -> Path:
    """Build the fallback HTML report for *run*. Returns the file path."""
    counts = run.get("counts", {})
    settings = run.get("settings", {})
    stats = run.get("stats", {})
    results = run.get("results", [])
    run_id = run.get("run_id", "unknown")

    rows = []
    for r in results:
        failure = html.escape((r.get("failure") or "")[:1200])
        rows.append(
            "<tr>"
            f"<td class='mono'>{html.escape(r.get('nodeid', ''))}</td>"
            f"<td>{html.escape(r.get('category', ''))}</td>"
            f"<td><span class='{_status_class(r.get('status', ''))}'>"
            f"{html.escape(r.get('status', ''))}</span></td>"
            f"<td class='mono'>{html.escape(r.get('duration_formatted', '') or '-')}</td>"
            f"<td class='mono'>{html.escape(r.get('start', '') or '-')}</td>"
            f"<td class='mono'>{html.escape(r.get('end', '') or '-')}</td>"
            f"<td><pre class='failure'>{failure}</pre></td>"
            f"<td><a href=\"/api/artifacts/for-test?nodeid={html.escape(r.get('nodeid', ''))}\">artifacts (json)</a></td>"
            "</tr>"
        )

    by_cat = (stats.get("by_category") or {}) if isinstance(stats, dict) else {}
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Framework Report - {html.escape(run_id)}</title>
<style>
body{{font-family:system-ui,Arial,sans-serif;margin:0;padding:24px;background:#f3f4f6;color:#111}}
.card{{background:#fff;border:1px solid #d1d5db;border-radius:10px;padding:16px;margin-bottom:16px}}
.notice{{background:#fffbeb;border:1px solid #f59e0b;border-radius:10px;padding:12px 16px;margin-bottom:16px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}}
.label{{display:block;color:#6b7280;font-size:.75rem;text-transform:uppercase}}
.mono{{font-family:ui-monospace,Consolas,monospace;font-size:.82rem;word-break:break-all}}
table{{border-collapse:collapse;width:100%;font-size:.84rem}}
th,td{{border:1px solid #d1d5db;padding:6px 8px;text-align:left;vertical-align:top}}
thead th{{background:#f9fafb}}
.passed{{color:#15803d;font-weight:700}}.failed{{color:#b91c1c;font-weight:700}}
.skipped{{color:#6b7280;font-weight:700}}.interrupted{{color:#b45309;font-weight:700}}
.failure{{max-width:420px;max-height:120px;overflow:auto;white-space:pre-wrap;font-size:.75rem;margin:0}}
code{{background:#f3f4f6;padding:1px 6px;border-radius:4px}}
</style></head><body>
<h1>Framework Report <span class="mono">{html.escape(run_id)}</span></h1>
<div class="notice"><strong>Fallback report.</strong> {html.escape(reason)}<br>
To view the full interactive Allure report instead: install the Allure CLI
(see <code>README.md</code> &ldquo;Allure reporting&rdquo;), run any test suite, then click
<strong>Open Allure Report</strong> again.</div>
<div class="card"><h2>Suite summary</h2><div class="grid">
<div><span class="label">Status</span><strong>{html.escape(run.get("status", ""))}</strong></div>
<div><span class="label">Total</span><span class="mono">{counts.get("total", 0)}</span></div>
<div><span class="label">Passed</span><span class="mono">{counts.get("passed", 0)}</span></div>
<div><span class="label">Failed</span><span class="mono">{counts.get("failed", 0)}</span></div>
<div><span class="label">Skipped</span><span class="mono">{counts.get("skipped", 0)}</span></div>
<div><span class="label">Errors</span><span class="mono">{counts.get("error", 0)}</span></div>
<div><span class="label">Interrupted</span><span class="mono">{counts.get("interrupted", 0)}</span></div>
<div><span class="label">Suite duration</span><span class="mono">{html.escape(run.get("suite_duration_formatted", "-"))}</span></div>
<div><span class="label">Average test</span><span class="mono">{html.escape(stats.get("average_duration_formatted", "-") if isinstance(stats, dict) else "-")}</span></div>
<div><span class="label">API/UI/API+UI/E2E</span><span class="mono">{by_cat.get("api", 0)}/{by_cat.get("ui", 0)}/{by_cat.get("api_ui", 0)}/{by_cat.get("e2e", 0)}</span></div>
<div><span class="label">Browser</span><span class="mono">{html.escape(settings.get("browser", "-"))} ({'headed' if settings.get("headless") is False else 'headless'})</span></div>
<div><span class="label">Environment</span><span class="mono">{html.escape(str(settings.get("environment", "-")).upper())}</span></div>
</div></div>
<div class="card"><h2>Results ({len(results)})</h2>
<table><thead><tr><th>Test</th><th>Category</th><th>Status</th><th>Duration</th>
<th>Start</th><th>End</th><th>Failure</th><th>Artifacts</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p><a href="/">Back to dashboard</a></p>
</body></html>
"""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(page, encoding="utf-8")
    return OUTPUT_FILE
