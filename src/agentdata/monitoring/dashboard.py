"""Monitoring dashboard — a tiny, dependency-free HTML view of the metrics.

A single ``GET /dashboard`` route renders ``METRICS.snapshot()`` (the same data
``/metrics`` serves as JSON) as a plain HTML page: uptime, total calls/errors, and a
per-tier table (calls, errors, error rate, p50/p95 latency). It is meant for a human
glancing at testnet health — the machine path stays ``GET /metrics`` (JSON), this is
just the eyeball view that complements it.

Why a router (not added to ``app.py`` here): file ownership. This module only exposes
``router``; the integrator mounts it with ``app.include_router(router)``. Nothing here
imports the app, so it stays decoupled and the Phase 1 app is untouched until wired.

Pure standard library + FastAPI's ``APIRouter`` / ``HTMLResponse`` (already a project
dependency). No template engine, no JS, no external assets — an agent or a human can
read it with curl. Values are HTML-escaped defensively even though they come from our
own numeric metrics, so this never becomes an injection seam if tier labels ever carry
user input.
"""

from __future__ import annotations

from html import escape

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from .metrics import METRICS

router = APIRouter(tags=["ops"])


def _fmt_pct(rate: float) -> str:
    """Render an error-rate fraction (0.0–1.0) as a percentage string."""
    return f"{rate * 100:.2f}%"


def _fmt_uptime(seconds: float) -> str:
    """Human-friendly uptime, e.g. ``2d 03h 04m 05s`` (the 3-day listing gate is in
    days, so days are surfaced explicitly)."""
    secs = int(seconds)
    days, secs = divmod(secs, 86_400)
    hours, secs = divmod(secs, 3_600)
    minutes, secs = divmod(secs, 60)
    return f"{days}d {hours:02d}h {minutes:02d}m {secs:02d}s"


def _render(snapshot: dict) -> str:
    """Build the dashboard HTML from a ``METRICS.snapshot()`` dict.

    Kept as a pure function of the snapshot so it is trivial to unit-test without a
    running server (feed a snapshot, assert on the markup).
    """
    per_tier: dict = snapshot.get("per_tier", {})

    if per_tier:
        rows = "\n".join(
            "<tr>"
            f"<td>{escape(str(tier))}</td>"
            f"<td class='num'>{stat.get('calls', 0)}</td>"
            f"<td class='num'>{stat.get('errors', 0)}</td>"
            f"<td class='num'>{_fmt_pct(stat.get('error_rate', 0.0))}</td>"
            f"<td class='num'>{stat.get('latency_p50_ms', 0.0):g}</td>"
            f"<td class='num'>{stat.get('latency_p95_ms', 0.0):g}</td>"
            "</tr>"
            for tier, stat in sorted(per_tier.items())
        )
    else:
        rows = (
            "<tr><td colspan='6' class='empty'>No calls recorded yet.</td></tr>"
        )

    total_calls = snapshot.get("total_calls", 0)
    total_errors = snapshot.get("total_errors", 0)
    error_rate = _fmt_pct(snapshot.get("error_rate", 0.0))
    uptime = _fmt_uptime(snapshot.get("uptime_seconds", 0.0))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="15">
  <title>AgentData — Monitoring</title>
  <style>
    :root {{ color-scheme: light dark; }}
    body {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif;
            margin: 2rem; line-height: 1.45; }}
    h1 {{ font-size: 1.4rem; margin-bottom: 0.25rem; }}
    .sub {{ opacity: 0.7; font-size: 0.9rem; margin-bottom: 1.5rem; }}
    .cards {{ display: flex; flex-wrap: wrap; gap: 1rem; margin-bottom: 1.5rem; }}
    .card {{ border: 1px solid rgba(128,128,128,0.35); border-radius: 8px;
             padding: 0.75rem 1rem; min-width: 9rem; }}
    .card .label {{ opacity: 0.7; font-size: 0.8rem; text-transform: uppercase;
                    letter-spacing: 0.03em; }}
    .card .value {{ font-size: 1.3rem; font-weight: 600; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 640px; }}
    th, td {{ border: 1px solid rgba(128,128,128,0.35); padding: 0.4rem 0.7rem;
              text-align: left; }}
    th {{ background: rgba(128,128,128,0.12); }}
    td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    td.empty {{ text-align: center; opacity: 0.7; }}
    footer {{ margin-top: 1.5rem; font-size: 0.8rem; opacity: 0.65; }}
    a {{ color: inherit; }}
  </style>
</head>
<body>
  <h1>AgentData — Monitoring</h1>
  <p class="sub">Testnet / preview. Auto-refreshes every 15s.
     Machine-readable JSON at <a href="/metrics">/metrics</a>.</p>

  <div class="cards">
    <div class="card"><div class="label">Uptime</div>
      <div class="value">{uptime}</div></div>
    <div class="card"><div class="label">Total calls</div>
      <div class="value">{total_calls}</div></div>
    <div class="card"><div class="label">Total errors</div>
      <div class="value">{total_errors}</div></div>
    <div class="card"><div class="label">Error rate</div>
      <div class="value">{error_rate}</div></div>
  </div>

  <table>
    <thead>
      <tr>
        <th>Tier</th><th>Calls</th><th>Errors</th>
        <th>Error rate</th><th>p50 (ms)</th><th>p95 (ms)</th>
      </tr>
    </thead>
    <tbody>
{rows}
    </tbody>
  </table>

  <footer>AgentData — executable liquidity / exit-cost. Metrics are process-local
  (single instance); see monitoring/metrics.py for the production swap seam.</footer>
</body>
</html>"""


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    """Render the current ``METRICS.snapshot()`` as a simple HTML status page."""
    return _render(METRICS.snapshot())
