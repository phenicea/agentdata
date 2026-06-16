"""Deployment contract tests — the combined ASGI app + the MCP registry manifest.

These lock the things a human deployment depends on (CEO handoff, ADR-001 §6):

* ``agentdata.asgi:app`` is ONE ASGI app that serves the existing REST surface
  (``/health``, ``/pricing``, ``/v1/liquidity/exit-cost``) AND mounts the MCP
  streamable-http endpoint under ``/mcp`` on a single port.
* ``server.json`` is valid, carries the Phenicea namespace, the current registry
  ``$schema`` (2025-12-11), and ``name`` matches ``package.json``'s ``mcpName``
  (registry invariant).
* No mainnet value is active by default (testnet lock intact).

The MCP mount is checked structurally (route is present) and at the ASGI layer
(``/mcp`` does not 404) — no real MCP/network handshake is performed, so the test
stays offline and deterministic and does not depend on SDK session details.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient

    from agentdata.asgi import app as asgi_app

    _HAS_ASGI = True
    _ASGI_IMPORT_ERROR = ""
except Exception as exc:  # noqa: BLE001 - report why the combined app is unavailable
    _HAS_ASGI = False
    _ASGI_IMPORT_ERROR = repr(exc)


# Repo root = tests/ -> repo root. server.json / package.json live at the root.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SERVER_JSON = _REPO_ROOT / "server.json"
_PACKAGE_JSON = _REPO_ROOT / "package.json"

_EXPECTED_NAME = "io.github.phenicea/agentdata-liquidity-exit-cost"
_EXPECTED_SCHEMA = (
    "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
)


@unittest.skipUnless(_HAS_ASGI, f"agentdata.asgi not importable: {_ASGI_IMPORT_ERROR}")
class TestCombinedAsgiApp(unittest.TestCase):
    """The single deployed ASGI app must serve REST + MCP on one port."""

    @classmethod
    def setUpClass(cls):
        # TestClient runs the app lifespan (which wires the MCP session manager),
        # so the mount is exercised exactly as it will be under uvicorn on Render.
        cls.client = TestClient(asgi_app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def test_health_route_served(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_pricing_route_served(self):
        r = self.client.get("/pricing")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.json()["tiers"]), {"quote", "risk", "deep"})

    def test_exit_cost_route_served(self):
        r = self.client.get(
            "/v1/liquidity/exit-cost", params={"token": "WETH", "size": 10}
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["tier"], "risk")

    def test_mcp_mount_present_in_routes(self):
        # Structural check: a /mcp route exists somewhere on the combined app.
        # The MCP sub-app may be mounted at prefix "" (a Mount whose own routes
        # carry the /mcp path) OR exposed as a top-level /mcp route, so we walk
        # one level into any mounted sub-app. We do NOT assume a specific Starlette
        # route class, keeping this robust to the chosen mount strategy.
        def _collect_paths(routes) -> list[str]:
            found = []
            for route in routes:
                p = getattr(route, "path", None)
                if p is not None:
                    found.append(p)
                # A Mount exposes its inner routes; include them so a sub-app
                # whose route is /mcp (mounted at "") is still discovered.
                sub = getattr(route, "routes", None)
                if sub:
                    found.extend(getattr(r, "path", "") for r in sub)
            return found

        paths = _collect_paths(asgi_app.routes)
        self.assertTrue(
            any(p == "/mcp" or p.startswith("/mcp") for p in paths),
            f"no /mcp route found on the combined ASGI app; routes={paths}",
        )

    def test_mcp_endpoint_does_not_404(self):
        # ASGI-layer check (no MCP handshake): a mounted endpoint must respond with
        # something other than 404. A bare GET to a streamable-http MCP endpoint is
        # expected to be rejected (e.g. 400/405/406/415) — the point is only that
        # the route exists and is reachable, not that the handshake succeeds.
        r = self.client.get("/mcp")
        self.assertNotEqual(
            r.status_code, 404, "/mcp is not mounted (got 404 from the combined app)"
        )

    def test_no_mainnet_default(self):
        # The combined app must come up in testnet by default, no mainnet leak.
        r = self.client.get("/health")
        self.assertEqual(r.json()["network"], "testnet")


class TestServerManifest(unittest.TestCase):
    """server.json / package.json must satisfy the MCP registry invariants."""

    def test_server_json_is_valid_json(self):
        self.assertTrue(_SERVER_JSON.is_file(), "server.json missing at repo root")
        # Will raise (fail the test) if the manifest is not valid JSON.
        json.loads(_SERVER_JSON.read_text(encoding="utf-8"))

    def test_server_json_schema_is_current(self):
        data = json.loads(_SERVER_JSON.read_text(encoding="utf-8"))
        self.assertEqual(data.get("$schema"), _EXPECTED_SCHEMA)

    def test_server_json_namespace_is_phenicea(self):
        data = json.loads(_SERVER_JSON.read_text(encoding="utf-8"))
        name = data.get("name", "")
        self.assertEqual(name, _EXPECTED_NAME)
        self.assertTrue(
            name.startswith("io.github.phenicea/"),
            f"namespace must be io.github.phenicea/..., got {name!r}",
        )

    def test_name_matches_package_mcp_name(self):
        # Registry invariant: server.json.name === package.json.mcpName.
        self.assertTrue(_PACKAGE_JSON.is_file(), "package.json missing at repo root")
        server = json.loads(_SERVER_JSON.read_text(encoding="utf-8"))
        package = json.loads(_PACKAGE_JSON.read_text(encoding="utf-8"))
        self.assertEqual(server.get("name"), package.get("mcpName"))
        self.assertEqual(package.get("mcpName"), _EXPECTED_NAME)

    def test_remote_is_streamable_http_under_mcp(self):
        data = json.loads(_SERVER_JSON.read_text(encoding="utf-8"))
        remotes = data.get("remotes", [])
        self.assertTrue(remotes, "server.json must declare at least one remote")
        remote = remotes[0]
        self.assertEqual(remote.get("type"), "streamable-http")
        # URL is a deploy-time placeholder until the human supplies the host; we
        # only require the MCP path suffix so the wiring is correct once filled.
        self.assertTrue(
            str(remote.get("url", "")).rstrip("/").endswith("/mcp"),
            f"remote url must end with /mcp, got {remote.get('url')!r}",
        )


class TestNoMainnetDefault(unittest.TestCase):
    """Testnet lock: the default settings must never be mainnet-active."""

    def test_settings_default_to_testnet(self):
        # No env override in the test process => defaults must be testnet, payments
        # off, mainnet not authorized. Mirrors the deploy env (NETWORK_MODE=testnet,
        # no ALLOW_MAINNET).
        from agentdata.config import NetworkMode, load_settings

        settings = load_settings()
        self.assertIs(settings.network_mode, NetworkMode.TESTNET)
        self.assertFalse(settings.is_mainnet)
        self.assertFalse(settings.allow_mainnet)


if __name__ == "__main__":
    unittest.main()
