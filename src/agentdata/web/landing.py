"""Landing page — a sober HTML root for humans (``GET /``).

This is block E of the discovery surface. Agents discover and select the service
through machine-readable artifacts (``llms.txt``, OpenAPI, the MCP tool schema);
this page is the *human* entry point: a person who opens the deployment URL in a
browser sees, in one screen, what the service does and where the real artifacts
are.

Design constraints (kept deliberately minimal — CLAUDE.md "ne sur-construis pas"):

* Pure stdlib + a FastAPI ``APIRouter``. No template engine, no static assets, no
  external CSS/JS/fonts — the page renders offline and behind no auth, just like
  ``llms.txt`` (CLAUDE.md §10).
* It is NOT a source of truth. Prices, schema, and capabilities live in
  ``/pricing``, ``/openapi.json``, ``/docs/api.md`` and ``llms.txt``; this page only
  *links* to them so there is nothing to keep in sync (tier names appear only as
  orientation, never dollar figures).
* Honest status: testnet / preview, no real funds — matches the banner already used
  by the API description and ``llms.txt``.

Wiring: the integrator mounts this router on the app
(``app.include_router(landing_router)``). This module never imports or edits
``app.py``.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["discovery"])


# Static HTML. Links are root-relative so the page works under any host (the Render
# testnet deployment, localhost, a future custom domain) without hardcoding a base
# URL. ``/docs`` is FastAPI's Swagger UI; ``/docs/api.md`` is the raw markdown doc —
# both are linked, they are distinct surfaces.
_LANDING_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AgentData — Executable Liquidity / Exit-Cost</title>
<meta name="description" content="Pay-per-call on-chain liquidity intelligence for AI agents: size-aware exit cost, depeg risk, and fragility on Base. Settled in USDC via x402.">
<style>
  :root { color-scheme: light dark; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.55; max-width: 46rem; margin: 0 auto; padding: 2.5rem 1.25rem;
    color: #1a1a1a; background: #fafafa;
  }
  @media (prefers-color-scheme: dark) {
    body { color: #e6e6e6; background: #141414; }
    a { color: #7ab7ff; }
    .banner { background: #3a2f00; color: #ffe08a; }
    code, .card { background: #1f1f1f; border-color: #333; }
  }
  h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
  .tagline { color: #666; margin-top: 0; }
  .banner {
    background: #fff4cc; color: #6b5400; border-radius: 6px;
    padding: 0.6rem 0.9rem; font-size: 0.9rem; margin: 1.25rem 0;
  }
  a { color: #0b66c3; }
  code {
    background: #eee; padding: 0.1rem 0.35rem; border-radius: 4px;
    font-size: 0.9em; border: 1px solid #ddd;
  }
  ul { padding-left: 1.2rem; }
  .links { list-style: none; padding: 0; }
  .links li { margin: 0.5rem 0; }
  .card {
    background: #fff; border: 1px solid #e2e2e2; border-radius: 8px;
    padding: 1rem 1.25rem; margin: 1.25rem 0;
  }
  footer { margin-top: 2.5rem; font-size: 0.85rem; color: #888; }
</style>
</head>
<body>
  <h1>AgentData — Executable Liquidity / Exit-Cost</h1>
  <p class="tagline">Pay-per-call on-chain liquidity intelligence for AI agents.</p>

  <div class="banner">
    <strong>Testnet / preview.</strong> No real funds. Prices are forced to $0 on
    testnet; any figures you see elsewhere are mainnet <em>targets</em>, not active
    charges. Mainnet is a separate, human-reviewed step.
  </div>

  <p>
    This service answers one question well: <strong>if I exit this token position
    right now, what does it actually cost, how much can I move before slippage blows
    past a threshold, and how fragile is that liquidity?</strong> The output is
    <em>computed, normalized, decision-grade</em> intelligence — size-aware exit
    cost, depeg risk, and a liquidity fragility score — derived from on-chain AMM
    math on Base. It is not a raw price feed.
  </p>

  <p>
    Settlement is in USDC via the open <strong>x402</strong> protocol (HTTP 402): the
    payment <em>is</em> the auth. No API key, no account, no subscription. One
    focused endpoint, sourced on-chain so it is cleanly redistributable, and
    deterministic so the result is verifiable against an on-chain swap quote.
  </p>

  <div class="card">
    <p style="margin-top:0"><strong>Endpoint</strong></p>
    <p style="margin-bottom:0">
      <code>GET /v1/liquidity/exit-cost?token=&lt;symbol|address&gt;&amp;size=&lt;number&gt;&amp;tier=&lt;quote|risk|deep&gt;</code>
    </p>
    <p style="margin-bottom:0; font-size:0.9rem; color:#777">
      Three tiers by compute depth: <code>quote</code> (single pool/size),
      <code>risk</code> (default — exit cost + fragility, plus depeg for pegged
      assets), <code>deep</code> (multi-size liquidation ladder). Prices are
      machine-readable at <code>/pricing</code> so an agent can choose before calling.
    </p>
  </div>

  <h2 style="font-size:1.1rem">Documentation &amp; metadata</h2>
  <ul class="links">
    <li><a href="/docs/api.md">/docs/api.md</a> — full API docs (raw markdown).</li>
    <li><a href="/openapi.json">/openapi.json</a> — OpenAPI specification.</li>
    <li><a href="/pricing">/pricing</a> — machine-readable pricing (single source of truth).</li>
    <li><a href="/llms.txt">/llms.txt</a> — plain-text summary for AI agents.</li>
    <li><a href="/docs">/docs</a> — interactive API explorer (Swagger UI).</li>
  </ul>

  <footer>
    AgentData endpoint #1 · settled in USDC via x402 on Base · MIT licensed.
  </footer>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def landing() -> str:
    """Serve the human-facing landing page (sober HTML, no JS, no external assets).

    Excluded from the OpenAPI schema (``include_in_schema=False``): the spec is for
    the machine surface (the ``/v1`` endpoint and the discovery helpers); the root
    HTML page is for humans and would only add noise to the agent-readable contract.
    """
    return _LANDING_HTML
