"""FastAPI application — the JSON API layer (Phase 1).

Single, focused endpoint: size-aware exit cost + fragility (+ depeg) for a token
on Base. x402 payment middleware is Phase 2 and slots in front of this without
changing the response contract; pricing metadata is already exposed here so the
402 amount and the discovery artifacts read from one source.
"""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse

from agentdata.chain import TokenNotFound, get_provider
from agentdata.compute.tiers import Tier, compute_tier
from agentdata.config import load_settings
from agentdata.monitoring import METRICS
from agentdata.safety import guard_network

from .pricing import DEFAULT_TIER, pricing_table
from .schemas import ExitCostResponse

# Repo root = parents of src/agentdata/api/app.py (app.py -> api -> agentdata ->
# src -> repo root). The discovery artifacts (llms.txt) live at the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_LLMS_TXT = _REPO_ROOT / "llms.txt"
_API_DOCS = _REPO_ROOT / "docs" / "api.md"

app = FastAPI(
    title="AgentData — Executable Liquidity / Exit-Cost",
    version="0.1.0",
    description=(
        "Pay-per-call data service for AI agents: size-aware **exit cost**, "
        "**depeg risk**, and liquidity **fragility** for a token on Base. Computed "
        "deterministically from on-chain AMM state (Aerodrome + Uniswap v3), so the "
        "result is reproducible and redistributable — not a raw price feed.\n\n"
        "Three tiers by compute depth (default `risk`): `quote`, `risk`, `deep`. "
        "Pricing is machine-readable at `/pricing` (single source of truth) and "
        "replicated into the MCP tool schema and `llms.txt`.\n\n"
        "Settlement is in USDC via the open x402 protocol (HTTP 402); payment is the "
        "auth. **Status: testnet/preview** — prices are forced to $0 and no real "
        "funds are involved. Mainnet is a separate, human-reviewed escalation."
    ),
    contact={
        "name": "AgentData — Executable Liquidity",
        "url": "https://github.com/phenicea/agentdata",
    },
    license_info={"name": "MIT"},
    openapi_tags=[
        {
            "name": "liquidity",
            "description": "Size-aware exit cost, depeg risk, and fragility.",
        },
        {
            "name": "discovery",
            "description": (
                "Machine-readable metadata for agent selection: pricing, raw "
                "`llms.txt`, OpenAPI."
            ),
        },
        {
            "name": "ops",
            "description": "Operational endpoints: health and monitoring metrics.",
        },
    ],
)


@app.get("/health", tags=["ops"])
def health() -> dict:
    s = load_settings()
    return {"status": "ok", "network": s.network_mode.value, "pool_source": s.pool_source.value}


@app.get("/metrics", tags=["ops"])
def metrics() -> dict:
    return METRICS.snapshot()


@app.get("/pricing", tags=["discovery"])
def pricing() -> dict:
    return pricing_table(is_mainnet=load_settings().is_mainnet)


@app.get("/llms.txt", response_class=PlainTextResponse, tags=["discovery"])
def llms_txt() -> str:
    """Serve the discovery ``llms.txt`` raw, as ``text/plain``.

    An agent reads this directly (no JS/auth) to decide whether and how to call the
    service (CLAUDE.md §10). It is the file shipped at the repo root, served verbatim
    — single source, no duplication. 404 (not 500) if the artifact is missing.
    """
    if not _LLMS_TXT.is_file():
        raise HTTPException(status_code=404, detail="llms.txt not available")
    return _LLMS_TXT.read_text(encoding="utf-8")


@app.get("/docs/api.md", response_class=PlainTextResponse, tags=["discovery"])
def api_docs_md() -> str:
    """Serve the raw markdown API docs, as advertised by ``llms.txt``.

    The link in ``llms.txt`` must resolve — an agent that follows it to a dead 404
    is an agent that doesn't pick us. Served verbatim from the repo's ``docs/api.md``
    (single source). Distinct from FastAPI's Swagger UI at ``/docs``.
    """
    if not _API_DOCS.is_file():
        raise HTTPException(status_code=404, detail="api.md not available")
    return _API_DOCS.read_text(encoding="utf-8")


@app.get("/v1/liquidity/exit-cost", response_model=ExitCostResponse, tags=["liquidity"])
def exit_cost_endpoint(
    token: str = Query(..., description="Token symbol/address to exit (sell)."),
    size: float = Query(..., gt=0, description="Sell size in human token units."),
    tier: str = Query(DEFAULT_TIER.value, description="quote | risk | deep"),
    pool: str | None = Query(None, description="Restrict to a single pool id."),
) -> ExitCostResponse:
    started = time.perf_counter()
    tier_label = tier
    error = True
    try:
        try:
            tier_enum = Tier(tier.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"unknown tier {tier!r}")
        tier_label = tier_enum.value

        settings = load_settings()
        provider = get_provider(settings)
        try:
            pools = provider.get_pools(token)
        except TokenNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except NotImplementedError as exc:
            raise HTTPException(status_code=501, detail=str(exc))

        if pool is not None:
            pools = [p for p in pools if p.pool_id == pool]
            if not pools:
                raise HTTPException(status_code=404, detail=f"pool {pool!r} not found for {token!r}")

        peg = provider.is_pegged(token)
        try:
            result = compute_tier(tier_enum, pools, size, peg=peg)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        result["network"] = settings.network_mode.value
        result["token"] = token
        response = ExitCostResponse(**result)
        error = False
        return response
    finally:
        latency_ms = (time.perf_counter() - started) * 1000.0
        METRICS.record(tier_label, latency_ms, error=error)


def _maybe_mount_x402(application: FastAPI) -> None:
    """Mount the x402 payment middleware ONLY when explicitly opted in.

    OPT-IN by config (CLAUDE.md §0/§14, ADR-001 §4): the middleware is mounted
    solely when ``X402_ENABLED=true`` AND a public receiving address is set. With
    payments off (the default) nothing here runs, the x402 SDK is never imported,
    and the Phase 1 app/tests stay byte-for-byte unchanged. Testnet stays the
    default; no mainnet value is active without a separate, reviewed NETWORK_MODE
    flip (a human escalation).
    """
    settings = load_settings()
    if not settings.x402_enabled:
        return
    if not settings.pay_to_address:
        # Fail loud rather than emit a 402 with an empty pay_to: a misconfigured
        # opt-in must not silently produce broken/unpayable payment terms.
        raise RuntimeError(
            "X402_ENABLED=true but PAY_TO_ADDRESS is empty. Set the PUBLIC receiving "
            "address (private key stays in a secret manager, never in the repo)."
        )
    # LAZY import: the x402 SDK is only required when payments are actually enabled.
    from agentdata.payment import build_x402_middleware

    build_x402_middleware(application, settings)


# ADR-001 §4 guardrail: refuse to start on mainnet without explicit authorization,
# and assert testnet pricing is free. Runs BEFORE any payment middleware is mounted.
guard_network(load_settings())
_maybe_mount_x402(app)
