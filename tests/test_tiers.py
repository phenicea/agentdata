import unittest

from agentdata.compute.amm import PoolKind, PoolState
from agentdata.compute.tiers import (
    DEEP_COST_LADDER_BPS,
    DEEP_SIZE_LADDER,
    Tier,
    compute_tier,
)


def vol(x, y, fee_bps=30, pid="p"):
    return PoolState(x, y, fee_bps, PoolKind.VOLATILE, pool_id=pid, dex="uni-v2")


POOLS = [vol(5_000_000, 5_000_000, pid="a"), vol(2_000_000, 2_000_000, pid="b")]


class TestTiers(unittest.TestCase):
    def test_quote_is_minimal(self):
        r = compute_tier(Tier.QUOTE, POOLS, 10_000)
        self.assertIn("exit_cost", r)
        self.assertIn("route", r)
        self.assertNotIn("fragility", r)
        self.assertNotIn("depeg", r)

    def test_risk_adds_fragility(self):
        r = compute_tier(Tier.RISK, POOLS, 10_000)
        self.assertIn("fragility", r)
        self.assertNotIn("depeg", r)  # no peg given

    def test_risk_with_peg_adds_depeg(self):
        r = compute_tier(Tier.RISK, POOLS, 10_000, peg=1.0)
        self.assertIn("depeg", r)
        self.assertIn("score", r["depeg"])

    def test_deep_adds_curve_and_ladders(self):
        r = compute_tier(Tier.DEEP, POOLS, 10_000)
        self.assertEqual(len(r["exit_cost_curve"]), len(DEEP_SIZE_LADDER))
        self.assertEqual(len(r["max_size_before_cost"]), len(DEEP_COST_LADDER_BPS))
        self.assertIn("cross_check", r)
        # curve cost grows with size
        costs = [pt["total_cost_bps"] for pt in r["exit_cost_curve"]]
        self.assertEqual(costs, sorted(costs))

    def test_deep_max_size_ladder_monotonic(self):
        r = compute_tier(Tier.DEEP, POOLS, 10_000)
        sizes = [e["max_size"] for e in r["max_size_before_cost"]]
        # higher tolerated cost -> larger allowed size
        self.assertEqual(sizes, sorted(sizes))

    def test_empty_pools_raise(self):
        with self.assertRaises(ValueError):
            compute_tier(Tier.QUOTE, [], 1.0)


if __name__ == "__main__":
    unittest.main()
