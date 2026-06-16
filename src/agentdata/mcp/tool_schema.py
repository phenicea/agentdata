"""Single source of truth for the MCP tool's identity and schema.

The MCP server (``mcp/server.py``), the registry manifest (``server.json``) and the
machine-readable docs (``llms.txt`` / OpenAPI) must all describe the SAME tool the
same way. To avoid drift they read it from here:

* :data:`TOOL_NAME`           — the registered tool name.
* :func:`tool_description`     — human/agent-facing description, with per-tier pricing
                                 pulled live from :mod:`agentdata.api.pricing` (never hardcoded).
* :func:`input_schema`         — JSON Schema of the inputs. Mirrors the schema FastMCP
                                 auto-derives from the ``liquidity_exit_cost`` signature
                                 (token, size, tier, pool) so the published schema and the
                                 actually-served schema cannot diverge.
* :func:`output_summary`       — machine-readable description of the outputs, using the
                                 exact field names from :class:`agentdata.api.schemas.ExitCostResponse`.

The compute/pricing logic itself is NOT duplicated here — this module only describes
the contract. Tier names come from :class:`agentdata.compute.tiers.Tier`; prices from
:mod:`agentdata.api.pricing`; output fields from :mod:`agentdata.api.schemas`.
"""

from __future__ import annotations

from agentdata.api.pricing import DEFAULT_TIER, pricing_table
from agentdata.compute.tiers import Tier

TOOL_NAME = "liquidity_exit_cost"

# Tier enum values, in priced order. Source of truth = Tier (compute layer).
_TIER_VALUES = [t.value for t in Tier]


def tool_description() -> str:
    """One-paragraph description an MCP host shows to the agent for selection.

    Includes the per-tier pricing read from the single pricing table. ``is_mainnet``
    is intentionally fixed to False here: the published listing is testnet/preview
    (CEO gate), so prices read as $0 and no mainnet value leaks into discovery
    metadata. The live REST surface reports the active network's pricing via
    ``/pricing``; this static description advertises the testnet/preview status.
    """
    table = pricing_table(is_mainnet=False)
    tiers = table["tiers"]
    tier_blurb = ", ".join(
        f"{name} = {tiers[name]['price_string']}" for name in _TIER_VALUES
    )
    return (
        "Size-aware exit cost, depeg risk, and liquidity fragility for a token on "
        "Base. Given a token and a sell size, returns the realized cost of exiting "
        "(price impact + fee, in bps and units), the best route across venues, an "
        "aggregated fragility score, and — for pegged assets — a depeg-risk score. "
        "Computed deterministically from on-chain AMM state, so the result is "
        "reproducible and auditable. "
        f"Three tiers by compute depth (default '{DEFAULT_TIER.value}'): "
        "'quote' = best-route exit cost for one size; 'risk' = exit cost + fragility "
        "(+ depeg for pegged tokens); 'deep' = adds a multi-size exit-cost curve, "
        "max-size-before-cost thresholds, and an internal cross-check. "
        f"Pricing per call ({table['currency']}): {tier_blurb}. "
        f"Status: {table['network']}/preview — payment runs over the x402 HTTP "
        "surface, not this tool."
    )


def input_schema() -> dict:
    """JSON Schema of the tool inputs.

    Matches the schema FastMCP derives from the ``liquidity_exit_cost(token, size,
    tier, pool)`` signature (confirmed by CTO introspection). Keeping this here lets
    server.json / llms.txt advertise exactly what the server accepts. Per-parameter
    descriptions are added for agent/Bazaar readability (FastMCP folds them in via
    ``Field``); the ``tier`` enum and default come from the Tier enum + pricing table.
    """
    return {
        "type": "object",
        "required": ["token", "size"],
        "properties": {
            "token": {
                "type": "string",
                "title": "Token",
                "description": "Token symbol or address to exit (sell).",
            },
            "size": {
                "type": "number",
                "title": "Size",
                "exclusiveMinimum": 0,
                "description": "Sell size in human token units (> 0).",
            },
            "tier": {
                "type": "string",
                "enum": list(_TIER_VALUES),
                "default": DEFAULT_TIER.value,
                "title": "Tier",
                "description": (
                    "Compute depth / price tier: 'quote' (cheapest, one-size exit "
                    "cost), 'risk' (default, + fragility/depeg), 'deep' (+ exit-cost "
                    "curve and cross-check)."
                ),
            },
            "pool": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "default": None,
                "title": "Pool",
                "description": (
                    "Optional pool id to restrict the computation to a single venue; "
                    "if omitted, all known pools for the token are aggregated."
                ),
            },
        },
    }


def output_summary() -> dict:
    """Machine-readable description of the tool's outputs.

    Field names mirror :class:`agentdata.api.schemas.ExitCostResponse` exactly so the
    MCP outputSchema, OpenAPI, and llms.txt stay in lockstep with the REST response.
    Optional fields are populated per tier: ``fragility``/``depeg`` from 'risk' up,
    and ``exit_cost_curve``/``max_size_before_cost``/``cross_check`` for 'deep'.
    """
    return {
        "tier": "Requested tier (quote | risk | deep).",
        "network": "Active network mode (testnet | mainnet).",
        "token": "Echoed token symbol/address.",
        "size": "Echoed sell size in human token units.",
        "exit_cost": (
            "Best realized exit cost: size, amount_out, mid_price, exec_price, "
            "total_cost_bps, price_impact_bps, fee_bps."
        ),
        "route": (
            "Chosen route: best (exit cost), pool_id, dex, routed_split, "
            "venues_considered."
        ),
        "fragility": (
            "[risk, deep] Aggregated fragility: score (0..100), depth_score, "
            "concentration_score, convexity_score, total_exit_liquidity, venues."
        ),
        "depeg": (
            "[risk, deep — pegged tokens only] Depeg risk: deviation_bps, "
            "dispersion_bps, weighted_price, total_liquidity, score (0..100)."
        ),
        "exit_cost_curve": (
            "[deep] Exit cost at several size multiples (ladder of liquidation)."
        ),
        "max_size_before_cost": (
            "[deep] For each cost threshold (bps), the max size kept under it."
        ),
        "cross_check": (
            "[deep] Best-route cost vs the single deepest pool (routing-edge flag)."
        ),
    }
