"""Build the x402 "payment requirements" for the 402 response, per tier.

This is the bridge between the single pricing source of truth
(:mod:`agentdata.api.pricing`) and the on-the-wire x402 ``PaymentRequirements``
shape. The standard seller path (``PaymentMiddlewareASGI``) builds these for you
from a ``PaymentOption``; this helper exists for the cases where we need the 402
terms explicitly: manual verify/settle, discovery/metadata, and tests asserting
the exact amount/network/asset emitted per tier.

Shape (confirmed via x402 2.13.0 ``PaymentRequirements.model_fields``):
``scheme, network, asset, amount, pay_to, max_timeout_seconds, extra``.

* ``scheme``  -> ``"exact"`` (EVM exact scheme).
* ``network`` -> CAIP-2 string from ``settings.chain_id`` (testnet ``eip155:84532``).
* ``amount``  -> atomic-units string (USDC 6 decimals); derived by the SDK from the
  dollar price so we never hand-roll decimals.
* ``asset``   -> USDC contract address, auto-resolved per network by the EVM exact
  scheme (testnet USDC, not a guessed/hard-coded address).
* ``pay_to``  -> ``settings.pay_to_address`` (public receiving address only).

Testnet => price is $0 (pricing.price_usdc forces it), so ``amount`` resolves to
``"0"``. No mainnet value is active unless ``settings.is_mainnet`` is deliberately
flipped (an escalated, reviewed decision).
"""

from __future__ import annotations

from agentdata.api.pricing import price_string_for_settings
from agentdata.compute.tiers import Tier
from agentdata.config import Settings

# EVM "exact" scheme name (x402.mechanisms.evm.exact.ExactEvmServerScheme.scheme == "exact").
SCHEME = "exact"

# Default validity window for the payment terms, in seconds. Conservative; the
# middleware path uses its own default — this only applies to manually-built terms.
DEFAULT_MAX_TIMEOUT_SECONDS = 120


def payment_requirements(tier: Tier, settings: Settings) -> dict:
    """Return the x402 402 payment requirements for ``tier`` as a plain dict.

    The dollar price comes from the single pricing source of truth
    (testnet => "$0"); the atomic ``amount`` and the USDC ``asset`` address are
    resolved by the EVM exact scheme per network, so neither is guessed here.
    """
    # Settings-aware: testnet => "$0" by default, or the OPT-IN symbolic amount
    # (TESTNET_SYMBOLIC_PRICE_USDC) when set; mainnet => fixed price (symbolic
    # never applies on mainnet — guarded in pricing.price_usdc).
    price = price_string_for_settings(tier, settings)
    asset_amount = _resolve_asset_amount(price, settings.chain_id)

    return {
        "scheme": SCHEME,
        "network": settings.chain_id,
        "asset": asset_amount["asset"],
        "amount": asset_amount["amount"],
        "pay_to": settings.pay_to_address,
        "max_timeout_seconds": DEFAULT_MAX_TIMEOUT_SECONDS,
        "extra": asset_amount.get("extra", {}),
    }


def _resolve_asset_amount(price: str, network: str) -> dict:
    """Resolve {asset, amount, extra} from a dollar price string for ``network``.

    Uses the x402 EVM exact scheme's ``parse_price`` (confirmed signature:
    ``parse_price(price, network) -> AssetAmount`` with fields amount/asset/extra),
    which yields the USDC contract address for the network and the atomic-units
    amount string. Import is lazy so this module (and the Phase 1 app) load fine
    without the x402 EVM extra installed.

    SEAM / TODO: if the x402 import path or ``parse_price`` contract changes in a
    future SDK version, this is the only place to update — the dict shape returned
    to callers stays stable. Requires ``x402[evm]`` (the ``[fastapi]`` extra alone
    does NOT pull in the EVM exact scheme — confirmed by CTO spec).
    """
    from x402.mechanisms.evm.exact import ExactEvmServerScheme

    scheme = ExactEvmServerScheme()
    asset_amount = scheme.parse_price(price, network)
    # AssetAmount is a pydantic model; normalise to a plain dict for callers.
    return dict(asset_amount)
