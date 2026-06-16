import unittest

try:
    from fastapi.testclient import TestClient

    from agentdata.api.app import app

    _HAS_API = True
except ImportError:  # fastapi/pydantic not installed
    _HAS_API = False


@unittest.skipUnless(_HAS_API, "fastapi not installed")
class TestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_pricing_testnet_is_zero(self):
        r = self.client.get("/pricing")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["network"], "testnet")
        self.assertEqual(body["tiers"]["risk"]["price"], 0.0)

    def test_quote_tier(self):
        r = self.client.get("/v1/liquidity/exit-cost", params={"token": "WETH", "size": 10, "tier": "quote"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["tier"], "quote")
        self.assertEqual(body["token"], "WETH")
        self.assertIsNone(body["fragility"])
        self.assertGreater(body["exit_cost"]["total_cost_bps"], 0)

    def test_risk_tier_default(self):
        r = self.client.get("/v1/liquidity/exit-cost", params={"token": "WETH", "size": 10})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["tier"], "risk")
        self.assertIsNotNone(body["fragility"])

    def test_pegged_token_has_depeg(self):
        r = self.client.get("/v1/liquidity/exit-cost", params={"token": "USDX", "size": 1000, "tier": "risk"})
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(r.json()["depeg"])

    def test_deep_tier(self):
        r = self.client.get("/v1/liquidity/exit-cost", params={"token": "WETH", "size": 10, "tier": "deep"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIsNotNone(body["exit_cost_curve"])
        self.assertIsNotNone(body["max_size_before_cost"])

    def test_unknown_token_404(self):
        r = self.client.get("/v1/liquidity/exit-cost", params={"token": "NOPE", "size": 1})
        self.assertEqual(r.status_code, 404)

    def test_unknown_tier_400(self):
        r = self.client.get("/v1/liquidity/exit-cost", params={"token": "WETH", "size": 1, "tier": "xxx"})
        self.assertEqual(r.status_code, 400)

    def test_bad_size_422(self):
        r = self.client.get("/v1/liquidity/exit-cost", params={"token": "WETH", "size": -1})
        self.assertEqual(r.status_code, 422)  # FastAPI query validation (gt=0)


if __name__ == "__main__":
    unittest.main()
