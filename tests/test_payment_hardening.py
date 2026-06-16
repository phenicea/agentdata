"""Regression tests for the post-audit hardening (TOCTOU + tier_price fallback)."""

import os
import unittest

from agentdata.api.pricing import DEFAULT_TIER, price_string
from agentdata.compute.tiers import Tier
from agentdata.payment.middleware import _tier_from_query


class TestTierResolution(unittest.TestCase):
    def test_known_tiers(self):
        self.assertIs(_tier_from_query("quote"), Tier.QUOTE)
        self.assertIs(_tier_from_query("deep"), Tier.DEEP)
        self.assertIs(_tier_from_query("RISK"), Tier.RISK)

    def test_unknown_or_missing_defaults_to_risk(self):
        self.assertIs(_tier_from_query("bogus"), DEFAULT_TIER)
        self.assertIs(_tier_from_query(None), DEFAULT_TIER)
        self.assertIs(_tier_from_query(""), DEFAULT_TIER)


class TestLoadSettingsGuardsRuntimeFlip(unittest.TestCase):
    """A runtime flip to mainnet must fail closed on the NEXT settings read."""

    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ("NETWORK_MODE", "ALLOW_MAINNET")}

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_runtime_mainnet_flip_is_refused(self):
        from agentdata.config import load_settings

        os.environ.pop("ALLOW_MAINNET", None)
        os.environ["NETWORK_MODE"] = "mainnet"
        with self.assertRaises(RuntimeError):
            load_settings()  # per-request read must refuse, closing the TOCTOU gap

    def test_testnet_load_is_free_and_ok(self):
        from agentdata.config import load_settings

        os.environ["NETWORK_MODE"] = "testnet"
        s = load_settings()
        self.assertFalse(s.is_mainnet)
        # testnet pricing invariant holds
        self.assertEqual(price_string(Tier.RISK, is_mainnet=s.is_mainnet), "$0")


if __name__ == "__main__":
    unittest.main()
