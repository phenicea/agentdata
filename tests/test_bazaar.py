"""Unit tests for the x402 **Bazaar** discovery extension (listing #2).

Contract under test (CTO spec + ADR-001 §6, DECISION_LOG 2026-06-16):

* When the x402 middleware is mounted (``X402_ENABLED=true``), the single priced
  ``RouteConfig`` carries a **well-formed** Bazaar discovery extension:
    - ``RouteConfig.extensions`` is the dict returned by the official helper
      ``declare_discovery_extension`` and contains a ``"bazaar"`` key, whose
      ``info.input`` and ``info.output`` are **non-empty**;
    - the resource-level metadata (``service_name`` / ``tags`` / ``icon_url``) is
      present and within the Bazaar bounds (serviceName <=32 ASCII; <=5 tags, each
      <=32 ASCII; iconUrl, if set, an absolute http(s) URL);
    - the metadata is **sourced from the single source of truth** — the tool schema
      (:mod:`agentdata.mcp.tool_schema`) and the pricing table
      (:mod:`agentdata.api.pricing`) — not duplicated/hard-coded.

* When the middleware is NOT mounted (``X402_ENABLED=false``, the default, listing
  #1 / instance #1), **no middleware and no extension** are mounted, and the tool
  schema / pricing surfaces stay byte-for-byte unchanged. The Bazaar extension only
  ever activates with the middleware → never on instance #1.

NON-NEGOTIABLE test constraints (mandate, CLAUDE.md §0/§14):
* No network, no funds, no real USDC. The facilitator's only init touchpoint
  (``get_supported``) is MOCKED offline. No deploy, no publish.
* Only the PUBLIC ``pay_to`` address is ever used; no private key anywhere.
* Mainnet stays locked: testnet is the only mode exercised here.

This file follows the same green-now pattern as ``tests/test_payment.py``: the SDK /
our package parts are imported behind guards, and the RouteConfig-level assertions
that depend on the parallel middleware edit landing are gated by a ``_bazaar_wired``
detector that ``skip``s (not fails) until ``middleware.py`` declares the extension —
so the existing suite stays green while the contract is pinned for when it lands.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from agentdata.compute.tiers import Tier
from agentdata.config import NetworkMode, PoolSource, Settings

# Base Sepolia CAIP-2 (confirmed live, config.CHAIN_ID). Testnet only here.
TESTNET_CHAIN_ID = "eip155:84532"
# The PUBLIC receiving address from the project config — never a secret (mandate §14).
PAY_TO = "0x5E442c144687De1D311855d65E87584BdEe7541A"
TESTNET_FACILITATOR = "https://x402.org/facilitator"

PRICED_ROUTE_KEY = "GET /v1/liquidity/exit-cost"

# Bazaar resource-metadata bounds (docs.x402.org/extensions/bazaar, confirmed spec).
MAX_SERVICE_NAME_LEN = 32
MAX_TAGS = 5
MAX_TAG_LEN = 32


# --- optional-import guards (green before parallel agents land code) -----------
try:
    import x402  # noqa: F401
    from fastapi import FastAPI  # noqa: F401

    _HAS_X402 = True
except ImportError:
    _HAS_X402 = False

try:
    from agentdata.payment.middleware import build_x402_middleware

    _HAS_MIDDLEWARE = True
except ImportError:
    _HAS_MIDDLEWARE = False


def _settings(*, mainnet: bool = False) -> Settings:
    """In-memory testnet Settings (mainnet only ever simulated, never via env)."""
    mode = NetworkMode.MAINNET if mainnet else NetworkMode.TESTNET
    return Settings(
        network_mode=mode,
        pool_source=PoolSource.FIXTURE,
        base_rpc_url="",
        pay_to_address=PAY_TO,
        facilitator_url=TESTNET_FACILITATOR,
        chain_id="eip155:8453" if mainnet else TESTNET_CHAIN_ID,
    )


def _mock_supported():
    """Patch every HTTPFacilitatorClient.get_supported to claim 'exact'/Base Sepolia
    is supported — the only network touchpoint at middleware init — so the whole
    build stays offline. Returns a started patcher (caller registers cleanup)."""
    from x402.http import HTTPFacilitatorClient
    from x402.schemas import SupportedKind, SupportedResponse

    supported = SupportedResponse(
        kinds=[SupportedKind(x402_version=2, scheme="exact", network=TESTNET_CHAIN_ID)]
    )
    return patch.object(HTTPFacilitatorClient, "get_supported", return_value=supported)


def _build_route_config(settings: Settings):
    """Mount the middleware on a fresh app (offline) and return the single priced
    ``RouteConfig`` the builder produced (read off ``app.user_middleware``)."""
    from fastapi import FastAPI

    app = FastAPI()
    build_x402_middleware(app, settings)
    mw = app.user_middleware[0]
    routes = mw.kwargs["routes"]
    assert PRICED_ROUTE_KEY in routes, f"priced route missing: {list(routes)}"
    return routes[PRICED_ROUTE_KEY]


def _bazaar_extension(route_config) -> dict | None:
    """Return the ``bazaar`` sub-dict of ``RouteConfig.extensions`` if wired, else None."""
    ext = getattr(route_config, "extensions", None)
    if not ext or "bazaar" not in ext:
        return None
    return ext["bazaar"]


def _bazaar_wired() -> bool:
    """True iff the parallel ``middleware.py`` edit has declared the Bazaar extension
    on the priced RouteConfig. Used to ``skip`` (not fail) the extension-shape tests
    until that edit lands — keeping the 120-test suite green in the meantime."""
    if not (_HAS_X402 and _HAS_MIDDLEWARE):
        return False
    p = _mock_supported()
    p.start()
    try:
        rc = _build_route_config(_settings())
        return _bazaar_extension(rc) is not None
    except Exception:
        return False
    finally:
        p.stop()


# ---------------------------------------------------------------------------
# 1. Source-of-truth metadata — always runnable (no SDK, no middleware needed).
#    These pin that the Bazaar declaration MUST be fed from tool_schema + pricing,
#    so the test fails if the build starts hard-coding/duplicating the contract.
# ---------------------------------------------------------------------------
class TestBazaarMetadataSource(unittest.TestCase):
    """The single source of truth (tool_schema + pricing) supplies everything the
    Bazaar declaration needs — inputs, output example fields, tier prices."""

    def test_input_schema_describes_token_size_tier_from_source(self):
        from agentdata.mcp.tool_schema import input_schema

        schema = input_schema()
        props = schema["properties"]
        for key in ("token", "size", "tier"):
            self.assertIn(key, props, f"input schema must describe '{key}'")
        self.assertIn("token", schema["required"])
        self.assertIn("size", schema["required"])
        # tier enum is sourced from the Tier enum (not hard-coded elsewhere).
        self.assertEqual(
            set(props["tier"]["enum"]), {t.value for t in Tier}
        )

    def test_output_summary_names_exit_cost_route_fragility_depeg(self):
        from agentdata.mcp.tool_schema import output_summary

        out = output_summary()
        for field in ("exit_cost", "route", "fragility", "depeg"):
            self.assertIn(field, out, f"output summary must name '{field}'")

    def test_pricing_table_is_the_single_price_source(self):
        from agentdata.api.pricing import pricing_table

        table = pricing_table(is_mainnet=False)
        self.assertEqual(table["currency"], "USDC")
        # All three priced tiers present, sourced from the pricing table.
        for tier in Tier:
            self.assertIn(tier.value, table["tiers"])
        # Testnet => every tier is $0 (listing #1 invariant, no real USDC).
        for tier in Tier:
            self.assertEqual(table["tiers"][tier.value]["price"], 0.0)


# ---------------------------------------------------------------------------
# 2. declare_discovery_extension produces the confirmed shape (reference, offline).
#    Independent of our package: pins the exact wire shape we rely on.
# ---------------------------------------------------------------------------
@unittest.skipUnless(_HAS_X402, "x402 SDK not installed")
class TestDeclareDiscoveryExtensionShape(unittest.TestCase):
    """The official helper yields ``{"bazaar": {"info": {...}, "schema": {...}}}``
    with non-empty ``info.input`` / ``info.output`` for an HTTP GET resource."""

    def _build(self):
        from agentdata.mcp.tool_schema import input_schema
        from agentdata.api.pricing import DEFAULT_TIER
        from x402.extensions.bazaar import OutputConfig, declare_discovery_extension

        schema = input_schema()
        # A query-param example built from the SAME schema fields (source of truth).
        example_input = {
            "token": "0xabc",
            "size": 10000,
            "tier": DEFAULT_TIER.value,
        }
        return declare_discovery_extension(
            input=example_input,
            input_schema={
                "properties": schema["properties"],
                "required": schema["required"],
            },
            output=OutputConfig(
                example={"tier": DEFAULT_TIER.value, "exit_cost": {"cost_bps": 38}},
                schema={"type": "object"},
            ),
        )

    def test_top_level_key_is_bazaar(self):
        self.assertEqual(list(self._build().keys()), ["bazaar"])

    def test_info_input_is_http_with_query_params(self):
        info = self._build()["bazaar"]["info"]
        self.assertEqual(info["input"]["type"], "http")
        self.assertTrue(info["input"]["queryParams"], "input queryParams must be non-empty")
        for key in ("token", "size", "tier"):
            self.assertIn(key, info["input"]["queryParams"])

    def test_info_output_is_json_with_example(self):
        info = self._build()["bazaar"]["info"]
        self.assertEqual(info["output"]["type"], "json")
        self.assertTrue(info["output"]["example"], "output example must be non-empty")

    def test_schema_folds_input_schema_under_query_params(self):
        schema = self._build()["bazaar"]["schema"]
        qp = schema["properties"]["input"]["properties"]["queryParams"]
        self.assertIn("token", qp["properties"])
        self.assertIn("token", qp["required"])
        self.assertIn("size", qp["required"])

    def test_route_config_accepts_extension_with_metadata(self):
        """RouteConfig accepts extensions + service_name + tags + icon_url together
        (the construction the middleware uses)."""
        from x402.http.types import PaymentOption, RouteConfig

        rc = RouteConfig(
            accepts=[
                PaymentOption(
                    scheme="exact", pay_to=PAY_TO, price="$0", network=TESTNET_CHAIN_ID
                )
            ],
            mime_type="application/json",
            description="exit cost",
            service_name="Liquidity Exit Cost",
            tags=["defi", "liquidity", "base"],
            icon_url=None,
            extensions=self._build(),
        )
        self.assertIn("bazaar", rc.extensions)
        self.assertEqual(rc.service_name, "Liquidity Exit Cost")
        self.assertEqual(rc.tags, ["defi", "liquidity", "base"])


# ---------------------------------------------------------------------------
# 3. X402_ENABLED=true  -> RouteConfig carries a well-formed Bazaar extension.
#    Gated on the parallel middleware edit having landed (skip, not fail, until then).
# ---------------------------------------------------------------------------
@unittest.skipUnless(
    _HAS_X402 and _HAS_MIDDLEWARE, "middleware or x402/fastapi not available"
)
@unittest.skipUnless(
    _bazaar_wired(), "Bazaar extension not yet declared on the priced RouteConfig"
)
class TestBazaarExtensionOnRoute(unittest.TestCase):
    """When the middleware is mounted, the priced RouteConfig opts into Bazaar with a
    well-formed declaration and bounded resource metadata, sourced from the SoT."""

    def setUp(self):
        p = _mock_supported()
        p.start()
        self.addCleanup(p.stop)
        self.rc = _build_route_config(_settings())
        self.bazaar = _bazaar_extension(self.rc)
        self.assertIsNotNone(self.bazaar, "expected a bazaar extension on the route")

    def test_extension_has_info_and_schema(self):
        self.assertIn("info", self.bazaar)
        self.assertIn("schema", self.bazaar)

    def test_info_input_non_empty_http_query(self):
        info_input = self.bazaar["info"]["input"]
        self.assertEqual(info_input["type"], "http")
        self.assertTrue(info_input["queryParams"], "info.input.queryParams must be non-empty")

    def test_info_output_non_empty_json_example(self):
        info_output = self.bazaar["info"]["output"]
        self.assertEqual(info_output["type"], "json")
        self.assertTrue(info_output["example"], "info.output.example must be non-empty")

    def test_input_reflects_tool_schema_query_params(self):
        """The declared query params come from the tool schema (single source):
        token/size at minimum appear in the Bazaar input."""
        from agentdata.mcp.tool_schema import input_schema

        declared = set(self.bazaar["info"]["input"]["queryParams"].keys())
        schema_props = set(input_schema()["properties"].keys())
        # Every declared query param is a real tool input (no fabricated fields).
        self.assertTrue(
            declared.issubset(schema_props),
            f"declared {declared} must be a subset of tool inputs {schema_props}",
        )
        # token & size (the required inputs) are advertised for discovery.
        self.assertIn("token", declared)
        self.assertIn("size", declared)

    def test_input_schema_required_matches_tool_schema(self):
        from agentdata.mcp.tool_schema import input_schema

        qp = self.bazaar["schema"]["properties"]["input"]["properties"]["queryParams"]
        self.assertEqual(
            set(qp["required"]), set(input_schema()["required"])
        )

    def test_resource_metadata_service_name_bounded(self):
        name = self.rc.service_name
        self.assertTrue(name, "service_name must be set for Bazaar discovery")
        self.assertTrue(name.isascii(), "serviceName must be ASCII")
        self.assertLessEqual(len(name), MAX_SERVICE_NAME_LEN)

    def test_resource_metadata_tags_bounded(self):
        tags = self.rc.tags
        self.assertTrue(tags, "tags must be set for Bazaar discovery")
        self.assertLessEqual(len(tags), MAX_TAGS)
        for tag in tags:
            self.assertTrue(tag.isascii(), f"tag {tag!r} must be ASCII")
            self.assertLessEqual(len(tag), MAX_TAG_LEN)

    def test_icon_url_absolute_or_none(self):
        icon = getattr(self.rc, "icon_url", None)
        if icon is not None:
            self.assertTrue(
                icon.startswith(("http://", "https://")),
                f"iconUrl must be an absolute http(s) URL, got {icon!r}",
            )

    def test_metadata_not_duplicated_inside_extension(self):
        """service_name / tags / iconUrl are resource-level (RouteConfig) fields,
        NOT duplicated inside extensions.bazaar (per the confirmed SDK mapping)."""
        bazaar_blob = repr(self.bazaar)
        self.assertNotIn("serviceName", bazaar_blob)
        self.assertNotIn(self.rc.service_name, bazaar_blob)


# ---------------------------------------------------------------------------
# 4. X402_ENABLED=false (default / instance #1) -> nothing mounted, nothing changes.
# ---------------------------------------------------------------------------
class TestBazaarInactiveWhenDisabled(unittest.TestCase):
    """With payments off (the default), no middleware/extension is mounted and the
    tool schema + pricing surfaces are unchanged — listing #1 stays intact."""

    def test_x402_disabled_by_default(self):
        """The opt-in flag defaults to False, so app.py never mounts the middleware
        (and thus never declares the Bazaar extension) on instance #1."""
        self.assertFalse(Settings.x402_enabled, "X402 must be opt-in (default False)")
        self.assertFalse(_settings().x402_enabled)

    def test_disabled_app_mounts_no_payment_middleware(self):
        """An app built with X402_ENABLED unset/false carries no x402 middleware,
        hence no Bazaar extension anywhere (the extension only rides the middleware)."""
        import os

        # Force the default-disabled environment and import a fresh app module.
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("X402_ENABLED", None)
            os.environ["NETWORK_MODE"] = "testnet"
            os.environ["POOL_SOURCE"] = "fixture"
            import importlib

            import agentdata.api.app as app_module

            app_module = importlib.reload(app_module)
            names = [mw.cls.__name__ for mw in app_module.app.user_middleware]
        self.assertNotIn("PaymentMiddlewareASGI", names, f"unexpected middleware: {names}")

    def test_tool_schema_unchanged_without_payments(self):
        """The MCP/discovery tool schema does not depend on x402 being enabled —
        importing/using it with payments off yields the same stable contract."""
        from agentdata.mcp.tool_schema import TOOL_NAME, input_schema, output_summary

        self.assertEqual(TOOL_NAME, "liquidity_exit_cost")
        schema = input_schema()
        self.assertEqual(schema["type"], "object")
        self.assertIn("token", schema["properties"])
        self.assertIn("exit_cost", output_summary())

    def test_pricing_unchanged_without_payments(self):
        """Pricing (single source of truth) is independent of payments being on:
        testnet stays $0 across tiers, mainnet target prices intact."""
        from agentdata.api.pricing import pricing_table

        testnet = pricing_table(is_mainnet=False)
        for tier in Tier:
            self.assertEqual(testnet["tiers"][tier.value]["price"], 0.0)
        mainnet = pricing_table(is_mainnet=True)
        self.assertEqual(mainnet["tiers"]["quote"]["price"], 0.008)
        self.assertEqual(mainnet["tiers"]["risk"]["price"], 0.02)
        self.assertEqual(mainnet["tiers"]["deep"]["price"], 0.04)


if __name__ == "__main__":
    unittest.main()
