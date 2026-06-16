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

from typing import Any

from agentdata.api.pricing import DEFAULT_TIER, price_string_for_settings
from agentdata.compute.tiers import Tier
from agentdata.config import Settings
from agentdata.mcp import tool_schema
from agentdata.safety import guard_network

# Path key for the single priced route. Matches the existing endpoint exactly
# (see agentdata.api.app); "METHOD /path" is the key shape required by x402.
PRICED_ROUTE_KEY = "GET /v1/liquidity/exit-cost"

# Default time the payer has to settle, in seconds. Conservative; mainnet review
# can revisit it as a config change, not a rewrite.
MAX_TIMEOUT_SECONDS = 120

# --- Bazaar (x402 discovery extension) resource-level metadata ---------------
# These are resource-level metadata for the x402 Bazaar discovery layer (listing
# #2). They are advertised ONLY when the payment middleware is mounted
# (X402_ENABLED=true) -> never on listing #1 (X402_ENABLED=false), per the bound.
#
# Constraints confirmed by the live doc (docs.x402.org/extensions/bazaar) and the
# Python SDK (DiscoveryResource.to_dict emits camelCase serviceName/tags/iconUrl):
#   * service_name: <= 32 ASCII chars.
#   * tags:         <= 5 entries, each <= 32 ASCII chars.
#   * icon_url:     absolute http(s) URL, or None.
# They are top-level RouteConfig fields (NOT inside extensions.bazaar) — the SDK
# maps them onto the wire. Do not duplicate them inside the extension payload.
BAZAAR_SERVICE_NAME = "Liquidity Exit Cost"  # 19 chars, <= 32
BAZAAR_TAGS = ["defi", "liquidity", "base", "exit-cost", "x402"]  # 5, each <= 32
# Absolute http(s) URL only; None until a real, deployed icon URL exists. SEAM:
# the founder can set this to the deployed asset URL at listing #2 prep time.
# TODO(listing#2): point at a hosted icon (https://<render-host>/icon.png) once
# the 2nd instance ('agentdata-pay') is deployed; keep None to stay well-formed.
BAZAAR_ICON_URL: str | None = None


def _bazaar_query_example() -> dict[str, Any]:
    """A representative ``queryParams`` example for the Bazaar input declaration.

    Mirrors the priced GET route's query contract (``token``/``size``/``tier``)
    and reuses the SINGLE source of truth for the tier default
    (:data:`DEFAULT_TIER`) so the discovery example cannot drift from what the
    endpoint actually accepts. Values are illustrative only (no real address).
    """
    return {
        "token": "0xEXAMPLE_TOKEN_ADDRESS_OR_SYMBOL",
        "size": 10000,
        "tier": DEFAULT_TIER.value,
    }


def _bazaar_input_schema() -> dict[str, Any]:
    """JSON Schema for the Bazaar input's ``queryParams``.

    Sourced from the SINGLE tool-schema source of truth
    (:func:`agentdata.mcp.tool_schema.input_schema`) so Bazaar discovery and the
    MCP tool describe the EXACT same input contract (token/size/tier/pool). The
    helper folds this under ``schema.properties.input.properties.queryParams`` and
    auto-injects the HTTP ``method`` at runtime (we do not pass it — GET route).
    """
    return tool_schema.input_schema()


def _bazaar_output_example() -> dict[str, Any]:
    """A representative JSON output example for the Bazaar output declaration.

    Built from the output FIELD NAMES of the single tool-schema source of truth
    (:func:`agentdata.mcp.tool_schema.output_summary`) so the advertised shape
    matches :class:`agentdata.api.schemas.ExitCostResponse`. Values are
    illustrative (a 'risk'-tier response); the canonical, typed schema lives in
    the OpenAPI / MCP outputSchema. We surface an example here (what the Bazaar
    helper actually emits under ``info.output.example``).
    """
    return {
        "tier": DEFAULT_TIER.value,
        "network": "testnet",
        "token": "0xEXAMPLE_TOKEN_ADDRESS_OR_SYMBOL",
        "size": 10000,
        "exit_cost": {
            "size": 10000,
            "amount_out": 9962.0,
            "mid_price": 1.0,
            "exec_price": 0.9962,
            "total_cost_bps": 38,
            "price_impact_bps": 31,
            "fee_bps": 7,
        },
        "route": {
            "best": {"total_cost_bps": 38},
            "pool_id": "0xEXAMPLE_POOL",
            "dex": "uniswap_v3",
            "routed_split": False,
            "venues_considered": 3,
        },
        "fragility": {"score": 27, "venues": 5},
        "depeg": {"deviation_bps": 6, "score": 12},
    }


def _build_bazaar_extension() -> dict[str, Any]:
    """Build the ``extensions`` dict for the priced RouteConfig (Bazaar opt-in).

    Returns the dict produced by the official helper
    ``x402.extensions.bazaar.declare_discovery_extension`` (shape ``{"bazaar":
    {"info": {...}, "schema": {...}}}``). Putting this on ``RouteConfig.extensions``
    is the entire opt-in: the SDK's ``payment_middleware`` factory detects the
    ``"bazaar"`` key, registers ``bazaar_resource_server_extension``, and the
    facilitator serves it at ``/discovery/resources`` (see CTO spec). No manual
    facilitator plumbing.

    EXPECTED non-blocking warning: at mount time the SDK runs
    ``validate_bazaar_extensions`` on the PRE-enrichment declaration, which emits a
    ``UserWarning`` ("input: 'method' is a required property"). This is benign — the
    HTTP ``method`` is injected per-request by ``enrich_declaration`` (we must NOT
    pre-set it; see SPEC), so the SERVED declaration is valid. The schema-level
    ``validate_discovery_extension`` already passes on our payload.

    SEAM / NOT-FULLY-CONFIRMED:
      * The helper surfaces ``OutputConfig.schema`` validation but only re-emits
        ``info.output.example``; whether a strict output JSON Schema is served (vs
        just the example) was not traced end-to-end. We pass both an example and a
        minimal ``{"type": "object"}`` schema; tighten if a strict output schema is
        ever required.
      * Whether the public x402.org testnet facilitator actually serves
        ``/discovery/resources`` is UNCONFIRMED (returned 404 on 2026-06-16). The
        server-side declaration here is correct; catalogue appearance depends on a
        facilitator that implements discovery (re-verify at listing #2).

    The SDK import is lazy (inside this function), consistent with the rest of the
    module: importing ``middleware`` never requires x402 to be installed.
    """
    from x402.extensions.bazaar import OutputConfig, declare_discovery_extension

    return declare_discovery_extension(
        # GET route: pass `input` as the query-params EXAMPLE; do NOT pass
        # body_type (None => "query discovery extension"). The HTTP method is
        # auto-injected by enrich_declaration at runtime.
        input=_bazaar_query_example(),
        input_schema=_bazaar_input_schema(),
        output=OutputConfig(
            example=_bazaar_output_example(),
            schema={"type": "object"},
        ),
    )


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
        # "$0" on testnet by default ($0.008/$0.02/$0.04 on mainnet) — single
        # source. Settings-aware so the OPT-IN testnet symbolic amount
        # (TESTNET_SYMBOLIC_PRICE_USDC) reaches the on-the-wire 402 when set.
        return price_string_for_settings(tier, settings)

    # --- facilitator + resource server with the EVM "exact" scheme ----------
    facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=settings.facilitator_url))
    server = x402ResourceServer(facilitator)
    # ExactEvmServerScheme() takes no args; USDC asset is auto-resolved per network.
    server.register(network, ExactEvmServerScheme())

    # --- bazaar discovery extension (listing #2) ----------------------------
    # Built from the SINGLE sources of truth (tool_schema for the input/output
    # contract, pricing via the per-tier callback above). Only reaches the wire
    # because this whole middleware is mounted (X402_ENABLED=true) -> never on
    # listing #1. Adding it to RouteConfig.extensions is the entire opt-in; the
    # SDK registers the bazaar server extension automatically.
    bazaar_ext = _build_bazaar_extension()

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
            # Resource-level discovery metadata (top-level RouteConfig fields, NOT
            # inside extensions.bazaar — the SDK maps them to wire serviceName/
            # tags/iconUrl). Constraints (<=32 ASCII, <=5 tags, absolute icon URL)
            # documented at the constant definitions above.
            service_name=BAZAAR_SERVICE_NAME,
            tags=BAZAAR_TAGS,
            icon_url=BAZAAR_ICON_URL,
            extensions=bazaar_ext,  # {"bazaar": {"info": {...}, "schema": {...}}}
        )
    }

    # The middleware owns the full 402 -> verify -> settle -> serve flow against
    # the facilitator's /verify and /settle endpoints. No manual verify/settle.
    app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)
    return app
