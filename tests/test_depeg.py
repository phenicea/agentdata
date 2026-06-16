import unittest

from agentdata.compute.depeg import PegObservation, depeg_risk


class TestDepeg(unittest.TestCase):
    def test_perfect_peg_low_score(self):
        obs = [PegObservation(1.0, 2_000_000), PegObservation(1.0, 3_000_000)]
        r = depeg_risk(obs, peg=1.0)
        self.assertAlmostEqual(r.deviation_bps, 0.0, places=6)
        self.assertAlmostEqual(r.dispersion_bps, 0.0, places=6)
        self.assertLess(r.score, 1.0)

    def test_depeg_raises_deviation_and_score(self):
        obs = [PegObservation(0.97, 2_000_000)]
        r = depeg_risk(obs, peg=1.0)
        self.assertAlmostEqual(r.deviation_bps, 300.0, places=3)
        self.assertGreater(r.score, 50.0)

    def test_dispersion_across_venues(self):
        obs = [PegObservation(1.0, 1_000_000), PegObservation(0.99, 1_000_000)]
        r = depeg_risk(obs, peg=1.0)
        self.assertAlmostEqual(r.dispersion_bps, 100.0, places=3)

    def test_thin_liquidity_adds_risk(self):
        thick = depeg_risk([PegObservation(1.0, 2_000_000)], peg=1.0).score
        thin = depeg_risk([PegObservation(1.0, 1_000)], peg=1.0).score
        self.assertGreater(thin, thick)

    def test_liquidity_weighting(self):
        # price dominated by the deep venue
        obs = [PegObservation(0.90, 9_000_000), PegObservation(1.10, 1_000_000)]
        r = depeg_risk(obs, peg=1.0)
        self.assertLess(r.weighted_price, 0.95)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            depeg_risk([], peg=1.0)


if __name__ == "__main__":
    unittest.main()
