import unittest

from agentdata.compute.amm import PoolKind, PoolState
from agentdata.compute.fragility import fragility
from agentdata.compute.routing import best_route


def vol(x, y, fee_bps=30, pid="p"):
    return PoolState(x, y, fee_bps, PoolKind.VOLATILE, pool_id=pid, dex="uni-v2")


class TestRouting(unittest.TestCase):
    def test_best_route_picks_cheapest(self):
        deep = vol(10_000_000, 10_000_000, pid="deep")
        thin = vol(50_000, 50_000, pid="thin")
        r = best_route([thin, deep], 10_000)
        self.assertEqual(r.pool.pool_id, "deep")
        self.assertEqual(r.best.total_cost_bps, min(c.total_cost_bps for c in r.per_pool))

    def test_no_pools_raises(self):
        with self.assertRaises(ValueError):
            best_route([], 1.0)


class TestFragility(unittest.TestCase):
    def test_deep_diversified_is_low(self):
        pools = [vol(10_000_000, 10_000_000, pid=f"p{i}") for i in range(4)]
        f = fragility(pools, ref_size=1000)
        self.assertLess(f.score, 30.0)

    def test_single_thin_pool_is_high(self):
        f = fragility([vol(20_000, 20_000)], ref_size=5000)
        self.assertEqual(f.concentration_score, 100.0)  # n == 1
        self.assertGreater(f.score, 50.0)

    def test_concentration_detects_dominant_pool(self):
        balanced = [vol(1_000_000, 1_000_000, pid="a"), vol(1_000_000, 1_000_000, pid="b")]
        skewed = [vol(1_950_000, 1_950_000, pid="a"), vol(50_000, 50_000, pid="b")]
        self.assertLess(
            fragility(balanced, 1000).concentration_score,
            fragility(skewed, 1000).concentration_score,
        )

    def test_depth_decreases_fragility(self):
        shallow = fragility([vol(100_000, 100_000), vol(100_000, 100_000)], 5000).depth_score
        deep = fragility([vol(50_000_000, 50_000_000), vol(50_000_000, 50_000_000)], 5000).depth_score
        self.assertGreater(shallow, deep)

    def test_bad_ref_size(self):
        with self.assertRaises(ValueError):
            fragility([vol(1, 1)], 0)


if __name__ == "__main__":
    unittest.main()
