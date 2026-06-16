"""x402 payment middleware wiring (Phase 2) — OPT-IN, testnet-first.

This mounts the **official** x402 SDK middleware (``PaymentMiddlewareASGI``) in
front of the existing FastAPI app. It is deliberately a no-op unless explicitly
enabled by the integrator (``X402_ENABLED=true``), so Phase 1's 42 tests and the
untouched app keep passing.

Design (confirmed against x402 2.13.0 — locally introspected + live docs, see
ADR-001 §4 and the CTO spec handoff):

* One existing route ``GET /v1/liquidity/exit-cost`` is registered with a single
  ``PaymentOption`` whose ``price`` is a **DynamicPrice callback**. The callback
  reads the ``tier`` query param off the incoming request and returns the price
  string from the SINGLE pricing source of truth (:mod:`agentdata.api.pricing`).
  No per-tier route duplication, no scattered hard-coded amounts.
* Testnet forces every price to ``$0`` via ``pricing.price_string`` (mode is read
  from ``settings``). No mainnet value is active unless ``NETWORK_MODE=mainnet``
  is deliberately set — an escalated, human-only decision (CLAUDE.md §0/§14).
* Only the **public** receiving address (``settings.pay_to_address``) is used.
  The wallet private key never appears here or anywhere in the repo.

The SDK import is **lazy** (inside the function) so importing this module — or
running the app without x402 installed — never breaks the app.
"""

from __future__ import annotations

from agentdata.api.pricing import DEFAULT_TIER, price_string
from agentdata.compute.tiers import Tier
from agentdata.config import Settings
from agentdata.safety import guard_network

# Path key for the single priced route. Matches the existing endpoint exactly
# (see agentdata.api.app); "METHOD /path" is the key shape required by x402.
PRICED_ROUTE_KEY = "GET /v1/liquidity/exit-cost"

# Default time the payer has to settle, in seconds. Conservative; mainnet review
# can revisit it as a config change, not a rewrite.
MAX_TIMEOUT_SECONDS = 120


def _tier_from_query(raw_tier: str | None) -> Tier:
    """Resolve a ``tier`` query value to a :class:`Tier`, defaulting to RISK.

    The default mirrors the API layer (``DEFAULT_TIER``): an absent or unknown
    tier is treated as the showcase RISK tier so a request is never under-priced.
    """
    if raw_tier:
        try:
            return Tier(raw_tier.lower())
        except ValueError:
            pass
    return DEFAULT_TIER


def build_x402_middleware(app, settings: Settings):
    """Mount the official x402 payment middleware on ``app`` (per-tier pricing).

    Returns the configured ASGI app. This function does NOT consult any enable
    flag itself — the integrator gates the call behind ``X402_ENABLED`` so the
    Phase 1 app stays untouched when payments are off. Calling it always mounts
    the middleware.

    The x402 SDK is imported lazily here so module import / app startup never
    depends on the SDK being installed.
    """
    # --- defense in depth: the funds-touching path guards itself -------------
    # Don't rely solely on the caller (_maybe_mount_x402) having guarded: any
    # future mount path (MCP server, a script) that calls this must still refuse
    # mainnet without ALLOW_MAINNET. guard_network is idempotent and cheap.
    guard_network(settings)
    if not settings.facilitator_url:
        raise RuntimeError(
            "x402 is enabled but FACILITATOR_URL is empty. Refusing to mount a "
            "payment middleware with no facilitator (it could not verify/settle). "
            "Testnet defaults to https://x402.org/facilitator; mainnet must be set "
            "deliberately at the human escalation."
        )

    # --- LAZY SDK import (never at top level) -------------------------------
    from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
    from x402.http.middleware.fastapi import PaymentMiddlewareASGI
    from x402.http.types import HTTPRequestContext, RouteConfig
    from x402.mechanisms.evm.exact import ExactEvmServerScheme
    from x402.server import x402ResourceServer

    network = settings.chain_id  # CAIP-2, e.g. "eip155:84532" (Base Sepolia)
    is_mainnet = settings.is_mainnet

    # --- per-request price: read the tier, price from the single source -----
    def tier_price(ctx: HTTPRequestContext) -> str:
        # ctx.adapter is the FastAPIAdapter; get_query_param is a confirmed
        # method on the HTTPAdapter protocol (introspected on x402 2.13.0).
        # Wrapped: a malformed request / SDK shape change must not crash the
        # priced route — fall back to the default (showcase) tier, never under-price.
        try:
            raw_tier = ctx.adapter.get_query_param("tier")
            tier = _tier_from_query(raw_tier if isinstance(raw_tier, str) else None)
        except Exception:
            tier = DEFAULT_TIER
        # "$0" on testnet, "$0.008/$0.02/$0.04" on mainnet — single source.
        return price_string(tier, is_mainnet=is_mainnet)

    # --- facilitator + resource server with the EVM "exact" scheme ----------
    facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=settings.facilitator_url))
    server = x402ResourceServer(facilitator)
    # ExactEvmServerScheme() takes no args; USDC asset is auto-resolved per network.
    server.register(network, ExactEvmServerScheme())

    # --- single route, dynamic per-tier price -------------------------------
    routes: dict[str, RouteConfig] = {
        PRICED_ROUTE_KEY: RouteConfig(
            accepts=[
                PaymentOption(
                    scheme="exact",
                    pay_to=settings.pay_to_address,
                    price=tier_price,            # DynamicPrice callback
                    network=network,
                    max_timeout_seconds=MAX_TIMEOUT_SECONDS,
                )
            ],
            mime_type="application/json",
            description=(
                "Size-aware exit cost, depeg risk, and liquidity fragility for a "
                "token on Base. Price depends on tier (quote/risk/deep)."
            ),
        )
    }

    # The middleware owns the full 402 -> verify -> settle -> serve flow against
    # the facilitator's /verify and /settle endpoints. No manual verify/settle.
    app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)
    return app
