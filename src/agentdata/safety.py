"""Network safety guard — the ADR-001 §4 mainnet guardrail.

The project's hardest rule: testnet first, and mainnet (real prices / real USDC)
is a reviewed human escalation, never an accident. Defaults already put us on
testnet, but defaults are not defense in depth. This guard makes it *impossible*
to start the app on mainnet without a separate, explicit authorization flag, and
asserts that off-mainnet pricing is genuinely free.

Called at app startup (see ``api/app.py``). Raising here is the correct, loud
failure — far better than silently serving real-money payment terms.
"""

from __future__ import annotations

from agentdata.config import Settings


def guard_network(settings: Settings) -> None:
    """Refuse to run on mainnet without explicit authorization; assert testnet is free.

    Raises ``RuntimeError`` if:
    * ``NETWORK_MODE=mainnet`` but ``ALLOW_MAINNET`` is not set, or
    * we are off mainnet yet any tier price is non-zero (testnet must be $0).
    """
    if settings.is_mainnet and not settings.allow_mainnet:
        raise RuntimeError(
            "Refusing to start on MAINNET. Real prices / real USDC are a reviewed "
            "human escalation (CLAUDE.md §0/§14, ADR-001 §4). Set ALLOW_MAINNET=true "
            "ONLY after sign-off + a review of the funds-touching code. Default is "
            "testnet for a reason."
        )

    if not settings.is_mainnet:
        # Defense in depth: off-mainnet pricing must be free. Lazy import avoids a
        # config <-> pricing import cycle.
        from agentdata.api.pricing import pricing_table

        table = pricing_table(is_mainnet=False)
        nonzero = {t: v["price"] for t, v in table["tiers"].items() if v["price"] != 0.0}
        if nonzero:
            raise RuntimeError(
                f"testnet pricing invariant violated (must be $0): {nonzero}"
            )
