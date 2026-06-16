"""Discovery artifacts must be served and their advertised links must resolve.

An agent reads llms.txt / OpenAPI to decide whether to call us; a dead link there
costs us the selection. These tests lock the served surface.
"""

import unittest

try:
    from fastapi.testclient import TestClient

    from agentdata.api.app import app

    _HAS_API = True
except ImportError:
    _HAS_API = False


@unittest.skipUnless(_HAS_API, "fastapi not installed")
class TestDiscoveryRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_llms_txt_served_plaintext(self):
        r = self.client.get("/llms.txt")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.headers["content-type"].startswith("text/plain"))
        self.assertIn("liquidity_exit_cost", r.text)

    def test_api_docs_md_link_resolves(self):
        # llms.txt advertises /docs/api.md — it must not be a 404
        r = self.client.get("/docs/api.md")
        self.assertEqual(r.status_code, 200)
        self.assertIn("exit-cost", r.text.lower())

    def test_openapi_served(self):
        r = self.client.get("/openapi.json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("/v1/liquidity/exit-cost", r.json()["paths"])

    def test_pricing_served(self):
        r = self.client.get("/pricing")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.json()["tiers"]), {"quote", "risk", "deep"})

    def test_swagger_docs_not_shadowed(self):
        # FastAPI Swagger UI at /docs must still work alongside /docs/api.md
        self.assertEqual(self.client.get("/docs").status_code, 200)


if __name__ == "__main__":
    unittest.main()
