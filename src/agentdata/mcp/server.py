"""MCP server wrapper — exposes the endpoint as the ``liquidity_exit_cost`` tool.

This is the Phase 3 discovery surface (CLAUDE.md §5/§9, ADR-001 §5). It reuses the
EXACT same compute path as the REST route in :mod:`agentdata.api.app`
(``load_settings`` -> ``get_provider`` -> ``get_pools`` / ``is_pegged`` ->
``compute_tier`` -> ``ExitCostResponse``) so the MCP and HTTP surfaces can never
diverge — same logic, same response model, same numbers.

Built on the high-level FastMCP API (``mcp`` 1.27.2, transport streamable-http):
annotating the tool ``-> ExitCostResponse`` (the existing pydantic model) gives MCP
a structured outputSchema for free and guarantees REST/MCP parity. Per-parameter
descriptions are authored via ``Annotated[..., Field(...)]`` so the inputSchema is
agent-readable (and Bazaar-ready).

Payment (x402) stays on the HTTP/REST surface (ADR-001 §5): the MCP tool only
exposes compute + machine-readable pricing metadata, it does not duplicate the
payment middleware. Testnet stays the default: the tool calls ``load_settings()``
on every invocation, so ``guard_network()`` runs each time and the mainnet lock is
inherited; on testnet prices are forced to $0.
"""

from __future__ import annotations

import time
from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, INVALID_PARAMS, ErrorData
from pydantic import Field

from agentdata.api.pricing import pricing_table
from agentdata.api.schemas import ExitCostResponse
from agentdata.chain import TokenNotFound, get_provider
from agentdata.compute.tiers import Tier, compute_tier
from agentdata.config import load_settings
from agentdata.monitoring import METRICS

# Imported here so the server module is the single source of the tool name; the
# discovery artifacts (server.json, llms.txt) and tests read it from tool_schema.
from .tool_schema import TOOL_NAME, tool_description


def _pricing_meta() -> dict:
    """Machine-readable per-tier pricing for the tool metadata.

    Read from the single pricing source of truth (api.pricing), never hardcoded.
    Reflects the current network mode (testnet => $0 across the board).
    """
    return pricing_table(is_mainnet=load_settings().is_mainnet)


def get_mcp_server() -> FastMCP:
    """Build and return the MCP server with the ``liquidity_exit_cost`` tool.

    Remote/deployable server: host ``0.0.0.0`` and the MCP endpoint at ``/mcp``
    (streamable-http). The returned object exposes ``streamable_http_app()`` (an
    ASGI Starlette app) for the integrator to serve/mount, and
    ``run(transport="streamable-http")`` for a standalone process.
    """
    mcp = FastMCP(
        name="agentdata-liquidity",
        instructions=(
            "Size-aware exit cost, depeg risk, and liquidity fragility for a token "
            "on Base. Deterministic on-chain AMM math. Testnet/preview."
        ),
        host="0.0.0.0",
        port=8000,
        streamable_http_path="/mcp",
    )

    @mcp.tool(name=TOOL_NAME, description=tool_description())
    def liquidity_exit_cost(
        token: Annotated[
            str,
            Field(description="Token symbol/address to exit (sell), e.g. 'WETH'."),
        ],
        size: Annotated[
            float,
            Field(gt=0, description="Sell size in human token units (> 0)."),
        ],
        tier: Annotated[
            Literal["quote", "risk", "deep"],
            Field(
                description=(
                    "Pricing/compute tier. 'quote' = best-route exit cost only; "
                    "'risk' (default) adds fragility + depeg; 'deep' adds a "
                    "multi-size exit-cost curve and cross-check."
                ),
            ),
        ] = "risk",
        pool: Annotated[
            str | None,
            Field(description="Optional: restrict the computation to a single pool id."),
        ] = None,
    ) -> ExitCostResponse:
        """Compute exit cost / depeg / fragility — SAME path as the REST endpoint."""
        started = time.perf_counter()
        # Tier is constrained to the Literal at the schema level, but resolve
        # defensively so an invalid value fails closed with a clean MCP error.
        try:
            tier_enum = Tier(str(tier).lower())
        except ValueError as exc:
            METRICS.record(str(tier), (time.perf_counter() - started) * 1000.0, error=True)
            raise McpError(
                ErrorData(code=INVALID_PARAMS, message=f"unknown tier {tier!r}")
            ) from exc

        tier_label = tier_enum.value
        error = True
        try:
            # load_settings() re-runs guard_network() => mainnet stays locked here too.
            settings = load_settings()
            provider = get_provider(settings)

            try:
                pools = provider.get_pools(token)
            except TokenNotFound as exc:
                raise McpError(
                    ErrorData(code=INVALID_PARAMS, message=str(exc))
                ) from exc
            except NotImplementedError as exc:
                # On-chain registry not yet populated (addresses unverified).
                raise McpError(
                    ErrorData(code=INTERNAL_ERROR, message=str(exc))
                ) from exc

            if pool is not None:
                pools = [p for p in pools if p.pool_id == pool]
                if not pools:
                    raise McpError(
                        ErrorData(
                            code=INVALID_PARAMS,
                            message=f"pool {pool!r} not found for {token!r}",
                        )
                    )

            peg = provider.is_pegged(token)
            try:
                result = compute_tier(tier_enum, pools, size, peg=peg)
            except ValueError as exc:
                raise McpError(
                    ErrorData(code=INVALID_PARAMS, message=str(exc))
                ) from exc

            result["network"] = settings.network_mode.value
            result["token"] = token
            response = ExitCostResponse(**result)
            error = False
            return response
        finally:
            latency_ms = (time.perf_counter() - started) * 1000.0
            # Feed the uptime/latency counters that arm the listing-#1 trigger.
            METRICS.record(tier_label, latency_ms, error=error)

    return mcp


def main() -> None:
    """Run the MCP server as a standalone process (streamable-http transport).

    Entry point for ``python -m agentdata.mcp.server``. ``load_settings()`` runs on
    every tool call and re-applies ``guard_network()``, so starting here inherits the
    mainnet lock (testnet stays the default). This only starts a long-lived server;
    it is never invoked on import.
    """
    get_mcp_server().run(transport="streamable-http")


__all__ = ["get_mcp_server", "main"]


if __name__ == "__main__":  # pragma: no cover - process entry point, not run in tests
    main()
