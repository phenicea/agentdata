"""Pricing — the SINGLE source of truth for per-call prices.

Every surface that must agree on price (the x402 402 amount, OpenAPI, the MCP tool
schema, llms.txt, discovery metadata) reads from here. Do not duplicate prices
elsewhere. Values set by the CEO decision (DECISION_LOG 2026-06-16):

* quote = $0.008   risk = $0.02 (default)   deep = $0.04   — floor defended at $0.008.

Testnet forces every price to $0 (flow is still exercised end-to-end in test funds).
"""

from __future__ import annotations

from agentdata.compute.tiers import Tier

# Mainnet target prices in USDC. CHANGING THESE OR GOING LIVE = escalate to human.
MAINNET_PRICE_USDC = {
    Tier.QUOTE: 0.008,
    Tier.RISK: 0.02,
    Tier.DEEP: 0.04,
}

DEFAULT_TIER = Tier.RISK
PRICE_FLOOR_USDC = 0.008  # we do not race to the bottom (CLAUDE.md §16)


def price_usdc(tier: Tier, *, is_mainnet: bool) -> float:
    """Per-call price for ``tier``. Always 0 on testnet."""
    if not is_mainnet:
        return 0.0
    return MAINNET_PRICE_USDC[tier]


def price_string(tier: Tier, *, is_mainnet: bool) -> str:
    """x402-style dollar price string, e.g. ``"$0.02"`` (``"$0"`` on testnet)."""
    return f"${price_usdc(tier, is_mainnet=is_mainnet):g}"


def pricing_table(*, is_mainnet: bool) -> dict:
    """Machine-readable pricing for discovery artifacts."""
    return {
        "currency": "USDC",
        "default_tier": DEFAULT_TIER.value,
        "network": "mainnet" if is_mainnet else "testnet",
        "tiers": {
            t.value: {
                "price": price_usdc(t, is_mainnet=is_mainnet),
                "price_string": price_string(t, is_mainnet=is_mainnet),
            }
            for t in Tier
        },
    }
