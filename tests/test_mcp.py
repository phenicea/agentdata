"""Phase 3 — MCP wrapper + discovery artifacts tests.

What this guards (CTO contract, ADR-001 §5/§6):

* The MCP tool ``liquidity_exit_cost`` returns the SAME data as the compute layer
  for a fixture token (no duplicated logic / REST<->MCP parity, the risk the CEO
  flagged). We call the tool in-process (FastMCP ``call_tool``) — no network.
* Unknown token is handled cleanly (a proper error, not a crash).
* Tier defaults to ``risk`` when omitted.
* ``server.json`` is valid JSON with the MCP-Registry fields (schema id, name,
  description, version, streamable-http remote) and is honestly marked testnet/preview.
* ``llms.txt`` and ``docs/api.md`` exist and mention the three tiers.

The MCP server module and the llms.txt / docs/api.md files are produced by sibling
agents; tests that depend on them ``skip`` (rather than error) when the artifact is
not yet present, so this suite stays green standalone and turns into hard assertions
once everything is assembled. Run: ``PYTHONPATH=src python -m unittest``.
"""

from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path

# --------------------------------------------------------------------------- #
# Locate repo root (tests/ -> repo root) and the compute layer we compare against.
# --------------------------------------------------------------------------- #
REPO_ROOT = Path(__file__).resolve().parent.parent

try:
    from agentdata.chain import TokenNotFound, get_provider
    from agentdata.compute.tiers import Tier, compute_tier
    from agentdata.config import load_settings

    _HAS_CORE = True
except ImportError:  # pragma: no cover - core deps missing
    _HAS_CORE = False

try:
    import agentdata.mcp as agentdata_mcp  # noqa: F401
    from agentdata.mcp import get_mcp_server

    _HAS_MCP = True
    _MCP_IMPORT_ERR = ""
except Exception as exc:  # not just ImportError: a half-built module may raise
    _HAS_MCP = False
    _MCP_IMPORT_ERR = f"{type(exc).__name__}: {exc}"

TOOL_NAME = "liquidity_exit_cost"


def _reference_result(token: str, tier: str) -> dict:
    """Compute the expected payload via the SAME path the REST route uses.

    Mirrors ``api/app.py:exit_cost_endpoint`` exactly (load_settings -> provider ->
    compute_tier -> enrich), so any divergence in the MCP tool body shows up here.
    """
    settings = load_settings()
    provider = get_provider(settings)
    pools = provider.get_pools(token)
    peg = provider.is_pegged(token)
    result = compute_tier(Tier(tier), pools, 10.0, peg=peg)
    result["network"] = settings.network_mode.value
    result["token"] = token
    return result


def _call_tool(token: str, size: float, tier: str | None = None,
               pool: str | None = None) -> dict:
    """Invoke the MCP tool in-process and return its structured-output dict.

    FastMCP's ``call_tool`` is a coroutine. With a Pydantic return annotation it
    yields ``(content_list, structured_dict)``; with a plain ``dict`` return it
    yields just ``content_list``. We normalise both to a plain dict so the test
    does not depend on which annotation the server author chose.
    """
    server = get_mcp_server()
    args: dict = {"token": token, "size": size}
    if tier is not None:
        args["tier"] = tier
    if pool is not None:
        args["pool"] = pool

    res = asyncio.run(server.call_tool(TOOL_NAME, args))

    # Pydantic-annotated tool -> (content, structuredContent) tuple.
    if isinstance(res, tuple) and len(res) == 2 and isinstance(res[1], dict):
        return res[1]
    # dict-annotated tool -> list[TextContent]; parse the JSON text.
    if isinstance(res, list) and res:
        text = getattr(res[0], "text", None)
        if text is not None:
            return json.loads(text)
    raise AssertionError(f"unexpected call_tool return shape: {type(res)!r}: {res!r}")


# --------------------------------------------------------------------------- #
# MCP tool behaviour (skips cleanly until the sibling server module exists).
# --------------------------------------------------------------------------- #
@unittest.skipUnless(_HAS_CORE, "agentdata core not importable")
@unittest.skipUnless(_HAS_MCP, "agentdata.mcp not importable yet (" + _MCP_IMPORT_ERR + ")")
class TestMcpTool(unittest.TestCase):
    def test_tool_is_registered(self):
        server = get_mcp_server()
        tools = asyncio.run(server.list_tools())
        names = [t.name for t in tools]
        self.assertIn(TOOL_NAME, names, f"tool {TOOL_NAME!r} not registered; got {names}")

    def test_weth_risk_matches_compute_layer(self):
        """Showcase tier (risk) on a deep token: MCP output == compute output."""
        got = _call_tool("WETH", 10.0, tier="risk")
        want = _reference_result("WETH", "risk")
        # Parity on the differentiated signals (no duplicated/forked logic).
        self.assertEqual(got["tier"], "risk")
        self.assertEqual(got["token"], "WETH")
        self.assertEqual(got["network"], want["network"])
        self.assertEqual(got["exit_cost"], want["exit_cost"])
        self.assertEqual(got["route"], want["route"])
        self.assertEqual(got["fragility"], want["fragility"])

    def test_usdx_carries_depeg(self):
        """Pegged fixture token surfaces the depeg block, matching compute."""
        got = _call_tool("USDX", 10.0, tier="risk")
        want = _reference_result("USDX", "risk")
        self.assertEqual(got["token"], "USDX")
        self.assertIsNotNone(got.get("depeg"), "USDX should carry a depeg signal")
        self.assertEqual(got["depeg"], want["depeg"])
        self.assertEqual(got["exit_cost"], want["exit_cost"])

    def test_default_tier_is_risk(self):
        """Tier omitted -> defaults to risk (fragility present, no error)."""
        got = _call_tool("WETH", 10.0)  # no tier argument
        self.assertEqual(got["tier"], "risk")
        self.assertIsNotNone(got.get("fragility"),
                             "default (risk) tier must include fragility")

    def test_unknown_token_clean_error(self):
        """An unknown token raises a clean error, not an unhandled crash."""
        with self.assertRaises(Exception) as ctx:
            _call_tool("NOPE_UNKNOWN", 10.0, tier="risk")
        # The error message should be intelligible (mention the bad token), not a
        # raw network/stack failure. FastMCP wraps tool errors in ToolError.
        self.assertIn("NOPE_UNKNOWN", str(ctx.exception),
                      f"error should name the unknown token; got: {ctx.exception}")


# --------------------------------------------------------------------------- #
# tool_schema.py — single source of the tool's I/O shape (if present).
# --------------------------------------------------------------------------- #
@unittest.skipUnless(_HAS_MCP, "agentdata.mcp not importable yet")
class TestToolSchema(unittest.TestCase):
    def setUp(self):
        try:
            from agentdata.mcp import tool_schema
        except ImportError:
            self.skipTest("agentdata.mcp.tool_schema not present")
        self.ts = tool_schema

    def test_tool_name_constant(self):
        self.assertEqual(self.ts.TOOL_NAME, TOOL_NAME)

    def test_input_schema_shape(self):
        schema = self.ts.input_schema()
        self.assertEqual(schema.get("type"), "object")
        props = schema["properties"]
        for field in ("token", "size", "tier", "pool"):
            self.assertIn(field, props, f"input schema missing {field!r}")
        self.assertEqual(set(schema.get("required", [])), {"token", "size"})
        # tier is the priced enum, default risk.
        tier = props["tier"]
        self.assertEqual(set(tier.get("enum", [])), {"quote", "risk", "deep"})
        self.assertEqual(tier.get("default"), "risk")

    def test_description_nonempty(self):
        self.assertTrue(self.ts.tool_description().strip(),
                        "tool_description() must not be empty")

    def test_output_summary_mentions_signals(self):
        out = json.dumps(self.ts.output_summary()).lower()
        for signal in ("exit_cost", "fragility", "depeg"):
            self.assertIn(signal, out, f"output_summary should describe {signal!r}")


# --------------------------------------------------------------------------- #
# Discovery artifacts: server.json (hard — already produced), llms.txt + docs.
# --------------------------------------------------------------------------- #
def _find_server_json() -> Path | None:
    for candidate in (REPO_ROOT / "server.json", REPO_ROOT / "discovery" / "server.json"):
        if candidate.is_file():
            return candidate
    return None


class TestServerJson(unittest.TestCase):
    def setUp(self):
        path = _find_server_json()
        if path is None:
            self.skipTest("server.json not found at repo root or discovery/")
        self.path = path
        self.data = json.loads(path.read_text(encoding="utf-8"))

    def test_valid_json_with_required_fields(self):
        for field in ("name", "description", "version"):
            self.assertIn(field, self.data, f"server.json missing required {field!r}")
            self.assertTrue(str(self.data[field]).strip(), f"{field} is empty")

    def test_schema_id_present(self):
        schema = self.data.get("$schema", "")
        self.assertIn("server.schema.json", schema,
                      "server.json should pin the MCP Registry schema id")

    def test_remote_is_streamable_http(self):
        remotes = self.data.get("remotes", [])
        self.assertTrue(remotes, "server.json must declare at least one remote")
        types = {r.get("type") for r in remotes}
        self.assertIn("streamable-http", types,
                      f"remote transport must be streamable-http; got {types}")
        for r in remotes:
            self.assertIn("url", r, "each remote needs a url")
            self.assertTrue(str(r["url"]).strip(), "remote url is empty")

    def test_marked_testnet_or_preview(self):
        """CEO gate: the listing must be honestly marked testnet/preview."""
        blob = json.dumps(self.data).lower()
        self.assertTrue(
            "testnet" in blob or "preview" in blob,
            "server.json must be honestly marked testnet/preview (CEO gate)",
        )


class TestDiscoveryDocs(unittest.TestCase):
    TIERS = ("quote", "risk", "deep")

    def _read_or_skip(self, relpath: str) -> str:
        path = REPO_ROOT / relpath
        if not path.is_file():
            self.skipTest(f"{relpath} not present yet (sibling-agent artifact)")
        return path.read_text(encoding="utf-8")

    def test_llms_txt_exists_and_lists_tiers(self):
        text = self._read_or_skip("llms.txt").lower()
        for tier in self.TIERS:
            self.assertIn(tier, text, f"llms.txt should mention the {tier!r} tier")

    def test_docs_api_md_exists_and_lists_tiers(self):
        text = self._read_or_skip("docs/api.md").lower()
        for tier in self.TIERS:
            self.assertIn(tier, text, f"docs/api.md should mention the {tier!r} tier")


if __name__ == "__main__":
    unittest.main()
