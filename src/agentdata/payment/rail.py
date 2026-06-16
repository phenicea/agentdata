"""PaymentRail — a rail-agnostic seam over the payment flow (bloc A).

WHY THIS EXISTS
---------------
Today payment = x402 (HTTP 402, USDC on Base). Tomorrow it may be a different
rail (a session/batch protocol like MPP, a different facilitator, ...). The
business logic — "compute the exit-cost intelligence and serve it once paid" —
should not care *which* rail collects the money. This module defines that single
seam:

    price -> challenge -> verify -> settle

so the rest of the codebase can talk to *a rail* instead of to x402 directly.

WHAT THIS IS **NOT**
--------------------
* It does **not** re-implement the x402 middleware. The opt-in seller flow
  (``PaymentMiddlewareASGI``, mounted in ``app.py`` when ``X402_ENABLED=true``)
  remains the production path and is untouched. :class:`X402Rail` is a thin
  *delegating* facade over the x402 logic that already exists:
    - price        -> :func:`agentdata.api.pricing.price_string_for_settings`
    - challenge    -> :func:`agentdata.payment.pricing_402.payment_requirements`
    - verify       -> :meth:`agentdata.payment.facilitator.FacilitatorClient.verify`
    - settle       -> :meth:`agentdata.payment.facilitator.FacilitatorClient.settle`
* It does **not** flip any switch or change defaults. It holds no secrets, mounts
  no middleware, and on testnet the price is $0 exactly as everywhere else
  (single pricing source of truth). Mainnet stays locked behind ``guard_network``.

This is the minimal abstraction needed to keep the compute layer rail-agnostic.
Anything more (a real MPP adapter, session/batch settlement) is documented as a
future requirement in ``NOTES_RAILS.md`` — NOT built here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from agentdata.api.pricing import price_string_for_settings
from agentdata.compute.tiers import Tier
from agentdata.safety import guard_network

if TYPE_CHECKING:  # avoid import cost / cycles at runtime
    from agentdata.config import Settings


@runtime_checkable
class PaymentRail(Protocol):
    """The single interface the business logic uses to get paid.

    Four steps, deliberately small and rail-neutral. A concrete rail maps each
    onto its own mechanism (x402 maps them onto the EVM ``exact`` scheme +
    facilitator; an MPP adapter would map them onto sessions/batches — see
    ``NOTES_RAILS.md``).

    All methods are dict-in / dict-out (no rail-specific SDK types leak across
    the seam), so the caller and the tests stay decoupled from any one SDK.
    """

    name: str

    def price(self, tier: Tier, settings: "Settings") -> str:
        """The per-call price for ``tier`` as a human dollar string (e.g. ``"$0.02"``).

        Testnet => ``"$0"`` (or the opt-in symbolic amount). Read from the SINGLE
        pricing source of truth — a rail never invents prices.
        """
        ...

    def challenge(self, tier: Tier, settings: "Settings") -> dict:
        """The payment terms presented to the payer (the "you must pay X" message).

        For x402 this is the HTTP-402 ``payment requirements`` dict (scheme,
        network, asset, amount, pay_to). For another rail it is whatever that rail
        sends a client to initiate payment. Plain dict, no SDK types.
        """
        ...

    def verify(self, proof: dict, challenge: dict, settings: "Settings") -> dict:
        """Check a payment ``proof`` against an earlier ``challenge`` (no funds moved).

        Returns a dict the caller can read (x402 wire shape uses ``isValid``).
        Verification asserts the proof is well-formed and matches the terms; it is
        the gate the caller uses to decide whether to proceed to :meth:`settle`.
        """
        ...

    def settle(self, proof: dict, challenge: dict, settings: "Settings") -> dict:
        """Finalise a verified payment (on x402: settle on-chain via the facilitator).

        Returns a dict (x402 wire shape uses ``success`` + ``transaction``). Only
        called after a successful :meth:`verify`. The business logic serves its
        JSON response once this succeeds.
        """
        ...


class X402Rail:
    """:class:`PaymentRail` backed by the existing x402 logic — pure delegation.

    Each step forwards to code that already exists (pricing table, ``pricing_402``,
    ``FacilitatorClient``); none of it is reimplemented here, and the official
    ``PaymentMiddlewareASGI`` remains the mounted production path. This facade lets
    the business layer (and tests) drive the four-step flow without importing x402
    directly.

    Boundaries (inherited from the modules it delegates to, re-asserted here):
      * Testnet by default; ``guard_network`` runs on every challenge so a runtime
        mainnet flip without ``ALLOW_MAINNET`` fails closed.
      * Only the public ``pay_to`` address is ever used; no private key, no secret.
      * The x402 SDK is imported lazily inside the delegate modules, so importing
        this module never requires x402 to be installed.
    """

    name = "x402"

    def price(self, tier: Tier, settings: "Settings") -> str:
        # Single source of truth (testnet => "$0"). No price logic lives here.
        return price_string_for_settings(tier, settings)

    def challenge(self, tier: Tier, settings: "Settings") -> dict:
        # Defense in depth: a challenge is funds-adjacent, so re-assert the network
        # guard before producing payment terms (a runtime mainnet flip fails closed).
        guard_network(settings)
        # Delegate to the existing 402 terms builder — NOT a reimplementation.
        from agentdata.payment.pricing_402 import payment_requirements

        return payment_requirements(tier, settings)

    def verify(self, proof: dict, challenge: dict, settings: "Settings") -> dict:
        # Delegate to the thin facilitator wrapper (which the SDK middleware uses
        # internally too). No network/funds in tests — the client is mocked there.
        client = self._facilitator(settings)
        try:
            return client.verify(proof, challenge)
        finally:
            client.close()

    def settle(self, proof: dict, challenge: dict, settings: "Settings") -> dict:
        client = self._facilitator(settings)
        try:
            return client.settle(proof, challenge)
        finally:
            client.close()

    @staticmethod
    def _facilitator(settings: "Settings"):
        """Build the existing :class:`FacilitatorClient` from settings.

        Imported lazily so importing :mod:`rail` never pulls the x402 SDK. The URL
        comes from ``Settings`` (testnet facilitator by default) — no default baked
        in here, so mainnet can never be reached by accident.
        """
        from agentdata.payment.facilitator import FacilitatorClient

        return FacilitatorClient(settings.facilitator_url)


def get_rail(settings: "Settings") -> PaymentRail:
    """Return the active payment rail for ``settings``.

    Currently always x402 (the only rail we ship). This is the single place a
    future rail selection would happen (e.g. keyed off a ``PAYMENT_RAIL`` env), so
    callers depend on the :class:`PaymentRail` interface, not on ``X402Rail``.
    Adding a rail = add a branch here + a class implementing the Protocol; the
    business logic does not change. See ``NOTES_RAILS.md``.
    """
    return X402Rail()
