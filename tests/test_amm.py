import math
import unittest

from agentdata.compute.amm import (
    PoolKind,
    PoolState,
    _stable_k,
    amount_out,
    exit_cost,
    max_size_for_cost,
    mid_price,
)


def vol(x, y, fee_bps=30):
    return PoolState(x, y, fee_bps, PoolKind.VOLATILE, pool_id="v", dex="uni-v2")


def stab(x, y, fee_bps=4):
    return PoolState(x, y, fee_bps, PoolKind.STABLE, pool_id="s", dex="aero-stable")


class TestConstantProduct(unittest.TestCase):
    def test_mid_price(self):
        self.assertAlmostEqual(mid_price(vol(1000, 2000)), 2.0)

    def test_amount_out_matches_closed_form(self):
        p = vol(1000, 1000, fee_bps=30)
        size = 1.0
        dx = size * (1 - 0.003)
        expected = (1000 * dx) / (1000 + dx)
        self.assertAlmostEqual(amount_out(p, size), expected, places=12)

    def test_zero_size_returns_zero(self):
        self.assertEqual(amount_out(vol(1000, 1000), 0.0), 0.0)

    def test_price_impact_no_fee(self):
        # size=1 into 1000/1000: dy(no fee) = 1000/1001 -> impact ~ 9.99 bps
        p = vol(1000, 1000, fee_bps=30)
        ec = exit_cost(p, 1.0)
        self.assertAlmostEqual(ec.price_impact_bps, (1 - (1000 / 1001)) * 1e4, places=6)
        # total cost is impact + fee, and larger than impact alone
        self.assertGreater(ec.total_cost_bps, ec.price_impact_bps)
        self.assertAlmostEqual(ec.fee_bps, 30.0)

    def test_cost_monotonic_in_size(self):
        p = vol(1_000_000, 1_000_000)
        costs = [exit_cost(p, s).total_cost_bps for s in (10, 100, 1000, 10000)]
        self.assertEqual(costs, sorted(costs))

    def test_max_size_for_cost_hits_threshold(self):
        p = vol(1_000_000, 1_000_000, fee_bps=30)
        target = 80.0
        s = max_size_for_cost(p, target)
        self.assertGreater(s, 0)
        self.assertAlmostEqual(exit_cost(p, s).total_cost_bps, target, places=2)

    def test_max_size_zero_when_fee_above_threshold(self):
        p = vol(1000, 1000, fee_bps=50)
        self.assertEqual(max_size_for_cost(p, 30.0), 0.0)


class TestStable(unittest.TestCase):
    def test_invariant_preserved_after_trade(self):
        p = stab(1_000_000, 1_000_000, fee_bps=0)
        size = 50_000.0
        k0 = _stable_k(p.reserve_in, p.reserve_out)
        out = amount_out(p, size, apply_fee=False)
        x_new = p.reserve_in + size
        y_new = p.reserve_out - out
        k1 = _stable_k(x_new, y_new)
        self.assertTrue(math.isclose(k0, k1, rel_tol=1e-9))

    def test_mid_price_balanced_is_one(self):
        self.assertAlmostEqual(mid_price(stab(1_000_000, 1_000_000)), 1.0, places=9)

    def test_stable_less_slippage_than_volatile_near_balance(self):
        size = 20_000.0
        v_cost = exit_cost(vol(1_000_000, 1_000_000, fee_bps=0), size).price_impact_bps
        s_cost = exit_cost(stab(1_000_000, 1_000_000, fee_bps=0), size).price_impact_bps
        # the whole point of the stable curve: flatter near the peg
        self.assertLess(s_cost, v_cost)

    def test_small_stable_trade_low_cost(self):
        ec = exit_cost(stab(10_000_000, 10_000_000, fee_bps=4), 1000.0)
        # fee floor ~4 bps + negligible impact
        self.assertLess(ec.total_cost_bps, 6.0)
        self.assertGreaterEqual(ec.total_cost_bps, 4.0)


class TestValidation(unittest.TestCase):
    def test_bad_reserves(self):
        with self.assertRaises(ValueError):
            vol(0, 1000)

    def test_bad_fee(self):
        with self.assertRaises(ValueError):
            PoolState(1, 1, 10_000, PoolKind.VOLATILE)

    def test_negative_size(self):
        with self.assertRaises(ValueError):
            amount_out(vol(1, 1), -1)


if __name__ == "__main__":
    unittest.main()
