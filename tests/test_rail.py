"""Unit tests for the rail-agnostic payment seam (``agentdata.payment.rail``).

NON-NEGOTIABLE test constraints (mandate + CLAUDE.md §0/§14):
* No network, no funds, no real USDC. The facilitator is always MOCKED.
* Testnet stays the default; mainnet pricing is only ever *simulated* in-memory by
  building a ``Settings`` with ``NetworkMode.MAINNET`` + ``allow_mainnet=True``,
  never by flipping global config.
* The rail is pure DELEGATION over the existing x402 logic — we assert that it
  forwards to ``pricing_402.payment_requirements`` and ``FacilitatorClient`` and
  reads the single pricing source of truth, NOT that it reimplements anything.

These tests skip cleanly if the x402 EVM extra is absent (the challenge step needs
``parse_price`` to resolve atomic amounts), mirroring the ``_HAS_*`` guards used by
``tests/test_payment.py`` so the suite stays green offline.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from agentdata.compute.tiers import Tier
from agentdata.config import NetworkMode, PoolSource, Settings
from agentdata.payment.rail import PaymentRail, X402Rail, get_rail

# Base Sepolia / Base mainnet CAIP-2 ids (confirmed live, see config.CHAIN_ID).
TESTNET_CHAIN_ID = "eip155:84532"
MAINNET_CHAIN_ID = "eip155:8453"

# A throwaway *public* receiving address. Never a secret; private keys never appear
# in code or tests (mandate §14).
PAY_TO = "0xDEAD000000000000000000000000000000000000"
TESTNET_FACILITATOR = "https://x402.org/facilitator"

EXPECTED_MAINNET_PRICE = {Tier.QUOTE: 0.008, Tier.RISK: 0.02, Tier.DEEP: 0.04}


def _settings(mainnet: bool) -> Settings:
    """Build a Settings object in-memory; testnet unless a test simulates mainnet.

    Mainnet simulation sets ``allow_mainnet=True`` so the rail's ``guard_network``
    call does not refuse it (we are deliberately exercising the mainnet *price*
    path here, fully offline, with no real funds — the guard's purpose is to stop
    accidental mainnet, not a test that opts in explicitly in memory).
    """
    mode = NetworkMode.MAINNET if mainnet else NetworkMode.TESTNET
    return Settings(
        network_mode=mode,
        pool_source=PoolSource.FIXTURE,
        base_rpc_url="",
        pay_to_address=PAY_TO,
        facilitator_url=TESTNET_FACILITATOR,
        chain_id=MAINNET_CHAIN_ID if mainnet else TESTNET_CHAIN_ID,
        allow_mainnet=mainnet,
    )


try:
    import x402  # noqa: F401

    _HAS_X402 = True
except ImportError:
    _HAS_X402 = False


def _amount_of(challenge: dict):
    for key in ("amount", "price", "maxAmountRequired", "max_amount_required"):
        if key in challenge:
            return challenge[key]
    raise AssertionError(f"no amount field in challenge: {challenge}")


class TestRailInterface(unittest.TestCase):
    """The seam itself: X402Rail is a PaymentRail; get_rail returns one."""

    def test_x402rail_satisfies_protocol(self):
        # runtime_checkable Protocol: structural conformance, no network.
        self.assertIsInstance(X402Rail(), PaymentRail)

    def test_get_rail_returns_a_payment_rail(self):
        rail = get_rail(_settings(mainnet=False))
        self.assertIsInstance(rail, PaymentRail)

    def test_default_rail_is_x402(self):
        # Only rail we ship; selector defaults to it (no behavior change).
        self.assertEqual(get_rail(_settings(mainnet=False)).name, "x402")


class TestRailPrice(unittest.TestCase):
    """price() delegates to the SINGLE pricing source of truth — never invents prices."""

    def test_testnet_price_is_free_every_tier(self):
        rail = X402Rail()
        settings = _settings(mainnet=False)
        for tier in Tier:
            self.assertEqual(rail.price(tier, settings), "$0", f"tier {tier}")

    def test_mainnet_price_matches_pricing_table_per_tier(self):
        rail = X402Rail()
        settings = _settings(mainnet=True)
        for tier, dollars in EXPECTED_MAINNET_PRICE.items():
            self.assertEqual(rail.price(tier, settings), f"${dollars:g}", f"tier {tier}")

    def test_price_reads_the_single_source_of_truth(self):
        # Assert delegation: price() forwards to api.pricing, not a local table.
        rail = X402Rail()
        settings = _settings(mainnet=False)
        with patch(
            "agentdata.payment.rail.price_string_for_settings", return_value="$SENTINEL"
        ) as mocked:
            self.assertEqual(rail.price(Tier.RISK, settings), "$SENTINEL")
        mocked.assert_called_once_with(Tier.RISK, settings)


@unittest.skipUnless(_HAS_X402, "x402[evm] not installed (challenge needs parse_price)")
class TestRailChallenge(unittest.TestCase):
    """challenge() delegates to pricing_402.payment_requirements (the existing 402 terms)."""

    def test_challenge_is_the_402_payment_requirements(self):
        rail = X402Rail()
        settings = _settings(mainnet=False)
        ch = rail.challenge(Tier.RISK, settings)
        self.assertEqual(ch["scheme"], "exact")
        self.assertEqual(ch["network"], TESTNET_CHAIN_ID)
        self.assertEqual(ch["pay_to"], PAY_TO)

    def test_testnet_challenge_amount_is_zero(self):
        rail = X402Rail()
        ch = rail.challenge(Tier.QUOTE, _settings(mainnet=False))
        self.assertEqual(str(_amount_of(ch)).lstrip("$"), "0")

    def test_challenge_delegates_not_reimplements(self):
        # Assert delegation to the existing builder (no rewrite of the middleware).
        rail = X402Rail()
        settings = _settings(mainnet=False)
        sentinel = {"scheme": "exact", "delegated": True}
        with patch(
            "agentdata.payment.pricing_402.payment_requirements", return_value=sentinel
        ) as mocked:
            result = rail.challenge(Tier.RISK, settings)
        self.assertEqual(result, sentinel)
        mocked.assert_called_once_with(Tier.RISK, settings)

    def test_challenge_guards_mainnet_without_authorization(self):
        # The funds-adjacent step re-asserts guard_network: a mainnet flip without
        # ALLOW_MAINNET fails closed (no payment terms produced).
        unauthorized = Settings(
            network_mode=NetworkMode.MAINNET,
            pool_source=PoolSource.FIXTURE,
            base_rpc_url="",
            pay_to_address=PAY_TO,
            facilitator_url=TESTNET_FACILITATOR,
            chain_id=MAINNET_CHAIN_ID,
            allow_mainnet=False,  # not authorized
        )
        with self.assertRaises(RuntimeError):
            X402Rail().challenge(Tier.RISK, unauthorized)


class TestRailVerifySettle(unittest.TestCase):
    """verify()/settle() delegate to the FacilitatorClient wrapper — always MOCKED.

    We patch the rail's ``_facilitator`` factory to return a stub, so no network and
    no funds are ever touched; we only assert the rail forwards proof+challenge and
    closes the client.
    """

    def _rail_with_stub_client(self):
        stub = MagicMock()
        stub.verify.return_value = {"isValid": True, "payer": "0xabc"}
        stub.settle.return_value = {"success": True, "transaction": "0xtx"}
        rail = X402Rail()
        patch.object(X402Rail, "_facilitator", staticmethod(lambda settings: stub)).start()
        self.addCleanup(patch.stopall)
        return rail, stub

    def test_verify_forwards_proof_and_challenge_then_closes(self):
        rail, stub = self._rail_with_stub_client()
        proof = {"proof": "ok"}
        challenge = {"scheme": "exact", "amount": "0"}
        result = rail.verify(proof, challenge, _settings(mainnet=False))
        self.assertTrue(result["isValid"])
        stub.verify.assert_called_once_with(proof, challenge)
        stub.close.assert_called_once()  # resource released, no lingering client

    def test_settle_forwards_proof_and_challenge_then_closes(self):
        rail, stub = self._rail_with_stub_client()
        proof = {"proof": "ok"}
        challenge = {"scheme": "exact", "amount": "0"}
        result = rail.settle(proof, challenge, _settings(mainnet=False))
        self.assertTrue(result["success"])
        stub.settle.assert_called_once_with(proof, challenge)
        stub.close.assert_called_once()

    def test_facilitator_uses_settings_url_no_baked_default(self):
        # The factory must build the client from Settings.facilitator_url, so mainnet
        # can never be reached by accident (no hard-coded URL in the rail).
        from agentdata.payment import facilitator as facilitator_mod

        with patch.object(facilitator_mod, "FacilitatorClient") as ctor:
            X402Rail._facilitator(_settings(mainnet=False))
        ctor.assert_called_once_with(TESTNET_FACILITATOR)


if __name__ == "__main__":
    unittest.main()
