"""Pricing — the SINGLE source of truth for per-call prices.

Every surface that must agree on price (the x402 402 amount, OpenAPI, the MCP tool
schema, llms.txt, discovery metadata) reads from here. Do not duplicate prices
elsewhere. Values set by the CEO decision (DECISION_LOG 2026-06-16):

* quote = $0.008   risk = $0.02 (default)   deep = $0.04   — floor defended at $0.008.

Testnet forces every price to $0 by default (the flow is still exercised end-to-end
in test funds, and listing #1 ships at $0).

OPT-IN testnet symbolic price (DECISION_LOG 2026-06-16 — symbolic_amount_plan)
-----------------------------------------------------------------------------
The x402 facilitator's behaviour on a *zero-value* EIP-3009 authorization is not
confirmed (the SDK accepts ``$0``, but the live facilitator may reject a 0-value
transfer at /verify or /settle). So we add a SEPARATE, OPT-IN, TESTNET-ONLY symbolic
amount that the founder can switch on for the real E2E:

* Env ``TESTNET_SYMBOLIC_PRICE_USDC`` (read in :mod:`agentdata.config`), default 0.0.
* Passed in here as ``symbolic_testnet_usdc``. Default 0.0 => behaviour is byte-for-
  byte identical to before (testnet = $0): the existing tests, the listing #1 default,
  and the ``safety.guard_network`` "testnet = $0" invariant are all untouched.
* When > 0 **and** we are on testnet, ``price_usdc`` returns the symbolic amount.
* It is **never** applied on mainnet: the mainnet branch is completely unchanged, and
  feeding a symbolic value with ``is_mainnet=True`` is forbidden (raises) so a misuse
  fails closed instead of silently overriding the real mainnet price.

Wiring note (seam): callers that build the actual 402 amount (the payment middleware's
``tier_price`` callback and ``payment.pricing_402.payment_requirements``) hold the
``Settings`` and should forward ``settings.testnet_symbolic_price_usdc`` into the
``symbolic_testnet_usdc`` argument so the opt-in reaches the on-the-wire amount. Those
files are owned by other modules; until they forward it, the default ($0) is in effect
— see "Remaining TODOs" in the build note. The base (no-argument) call path stays $0,
which is exactly what ``safety.guard_network`` asserts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agentdata.compute.tiers import Tier

if TYPE_CHECKING:  # avoid a config <-> pricing import cycle at runtime
    from agentdata.config import Settings

# Mainnet target prices in USDC. CHANGING THESE OR GOING LIVE = escalate to human.
MAINNET_PRICE_USDC = {
    Tier.QUOTE: 0.008,
    Tier.RISK: 0.02,
    Tier.DEEP: 0.04,
}

DEFAULT_TIER = Tier.RISK
PRICE_FLOOR_USDC = 0.008  # we do not race to the bottom (CLAUDE.md §16)


def _testnet_price(symbolic_testnet_usdc: float) -> float:
    """Resolve the testnet per-call price: $0 by default, symbolic only if opt-in.

    The symbolic amount is a single, deliberate opt-in (``TESTNET_SYMBOLIC_PRICE_USDC``
    > 0). A zero / negative / unset value yields the historical $0. Negative values are
    clamped to 0 defensively (the env parser already does this, but keep this function
    safe in isolation).
    """
    return symbolic_testnet_usdc if symbolic_testnet_usdc > 0.0 else 0.0


def price_usdc(
    tier: Tier,
    *,
    is_mainnet: bool,
    symbolic_testnet_usdc: float = 0.0,
) -> float:
    """Per-call price for ``tier`` in USDC.

    * Mainnet: the fixed target price (unchanged; escalation-gated).
    * Testnet: ``$0`` by default, or the opt-in symbolic amount when
      ``symbolic_testnet_usdc > 0``.

    ``symbolic_testnet_usdc`` must NOT be combined with ``is_mainnet=True``: the
    symbolic amount is strictly a testnet device, so a non-zero value on mainnet is a
    programming error and fails closed rather than overriding the real price.
    """
    if is_mainnet:
        if symbolic_testnet_usdc > 0.0:
            raise ValueError(
                "TESTNET_SYMBOLIC_PRICE_USDC is testnet-only and must never be applied "
                "on mainnet. Refusing to override the real mainnet price with a symbolic "
                "amount (CLAUDE.md §0/§14; safety.guard_network invariant)."
            )
        return MAINNET_PRICE_USDC[tier]
    return _testnet_price(symbolic_testnet_usdc)


def price_string(
    tier: Tier,
    *,
    is_mainnet: bool,
    symbolic_testnet_usdc: float = 0.0,
) -> str:
    """x402-style dollar price string, e.g. ``"$0.02"`` (``"$0"`` on testnet by default).

    With an opt-in testnet symbolic amount this becomes e.g. ``"$0.001"`` on testnet.
    The ``:g`` format keeps it compact and matches what the x402 EVM exact scheme's
    ``parse_price`` accepts.
    """
    return (
        f"${price_usdc(tier, is_mainnet=is_mainnet, symbolic_testnet_usdc=symbolic_testnet_usdc):g}"
    )


def price_usdc_for_settings(tier: Tier, settings: "Settings") -> float:
    """Settings-aware per-call price: the single accessor callers should use.

    Resolves the price from one ``Settings``: mainnet => the fixed target price;
    testnet => ``$0`` by default, or ``settings.testnet_symbolic_price_usdc`` when
    the founder opted in (> 0). This is the seam that carries the OPT-IN symbolic
    amount to the on-the-wire 402 / ``/pricing`` / discovery metadata, so the
    documented testnet fallback (``TESTNET_SYMBOLIC_PRICE_USDC``) actually takes
    effect — while the default (0.0) keeps testnet at $0 (listing #1 invariant).

    The symbolic value is never forwarded on mainnet: ``price_usdc`` raises if a
    non-zero symbolic amount is combined with ``is_mainnet=True``, so we only pass
    it through off mainnet (fails closed, never silently overrides a real price).
    """
    symbolic = 0.0 if settings.is_mainnet else settings.testnet_symbolic_price_usdc
    return price_usdc(tier, is_mainnet=settings.is_mainnet, symbolic_testnet_usdc=symbolic)


def price_string_for_settings(tier: Tier, settings: "Settings") -> str:
    """Settings-aware dollar price string (e.g. ``"$0"``, ``"$0.001"``, ``"$0.02"``)."""
    symbolic = 0.0 if settings.is_mainnet else settings.testnet_symbolic_price_usdc
    return price_string(tier, is_mainnet=settings.is_mainnet, symbolic_testnet_usdc=symbolic)


def pricing_table_for_settings(settings: "Settings") -> dict:
    """Settings-aware machine-readable pricing for ``/pricing`` and discovery.

    Reflects the opt-in testnet symbolic amount when set; otherwise identical to
    ``pricing_table(is_mainnet=...)`` ($0 on testnet).
    """
    symbolic = 0.0 if settings.is_mainnet else settings.testnet_symbolic_price_usdc
    return pricing_table(is_mainnet=settings.is_mainnet, symbolic_testnet_usdc=symbolic)


def pricing_table(*, is_mainnet: bool, symbolic_testnet_usdc: float = 0.0) -> dict:
    """Machine-readable pricing for discovery artifacts.

    Defaults to the historical table ($0 on testnet) so callers that only know the
    network mode — including ``safety.guard_network`` — keep seeing the base invariant.
    Pass ``symbolic_testnet_usdc`` to reflect the opt-in testnet amount.
    """
    return {
        "currency": "USDC",
        "default_tier": DEFAULT_TIER.value,
        "network": "mainnet" if is_mainnet else "testnet",
        "tiers": {
            t.value: {
                "price": price_usdc(
                    t, is_mainnet=is_mainnet, symbolic_testnet_usdc=symbolic_testnet_usdc
                ),
                "price_string": price_string(
                    t, is_mainnet=is_mainnet, symbolic_testnet_usdc=symbolic_testnet_usdc
                ),
            }
            for t in Tier
        },
    }
