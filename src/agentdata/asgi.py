"""Combined ASGI app for production: REST (FastAPI) + MCP (streamable-http) on one port.

This is the single entry point for the Render deployment (CEO handoff 2026-06-16):
``uvicorn agentdata.asgi:app --host 0.0.0.0 --port $PORT``. It serves the existing
FastAPI REST surface (``/health``, ``/pricing``, ``/v1/liquidity/exit-cost``,
``/metrics``, ``/llms.txt``, ``/docs/api.md``) AND the MCP server under ``/mcp`` from
one process / one ``$PORT``. No second server, no SSE (deprecated).

It reuses the existing app and server verbatim — zero duplicated logic:
  - REST app:  :data:`agentdata.api.app.app` (guard_network + opt-in x402 already wired)
  - MCP server: :func:`agentdata.mcp.get_mcp_server` (FastMCP, streamable_http_path="/mcp")

Why this module exists instead of mounting in api/app.py: keeping the mount + the MCP
session-manager lifespan here leaves the Phase 1/2/3 app and its 91 tests
byte-for-byte unchanged (TestClient targets ``agentdata.api.app:app`` directly). The
combined surface is the deployment artifact; the REST app stays the source of truth.

Critical wiring (confirmed by live introspection of mcp 1.27.2, not deduced):
  - ``FastMCP.streamable_http_app()`` returns a Starlette sub-app whose single Route is
    at ``streamable_http_path``. ``get_mcp_server()`` sets that to ``/mcp``; if we mounted
    that sub-app at ``/mcp`` the path would double to ``/mcp/mcp``. So we set the inner
    path to ``/`` on the instance and mount the sub-app at prefix ``/mcp`` — the public
    URL resolves to ``/mcp`` AND the parent app carries a top-level Mount at ``/mcp``
    (discoverable in ``app.routes``). server.py is left untouched (out of this file's
    scope); we only adjust this instance's setting before building the sub-app.
  - That sub-app carries its OWN lifespan (``self.session_manager.run()``), and Starlette
    does NOT propagate a mounted sub-app's lifespan. So we MUST run the session manager
    from the PARENT lifespan ourselves, or MCP requests hang. ``.session_manager`` raises
    if read before ``streamable_http_app()`` — hence the ordering below.
  - ``get_mcp_server()`` returns a fresh FastMCP each call and ``session_manager.run()``
    is single-use per instance: build the server ONCE at import, hold the reference.

Guardrails: the imported FastAPI app already ran ``guard_network(load_settings())`` at
import; nothing here weakens the mainnet lock or the x402 opt-in. The MCP tool re-runs
``load_settings()``/``guard_network()`` per call, so testnet stays the default.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI

from agentdata.api.app import app as rest_app
from agentdata.mcp import get_mcp_server

# Build the MCP server exactly ONCE (fresh instance per get_mcp_server() call, and
# session_manager.run() cannot be re-entered) and materialize its streamable-http
# ASGI sub-app. streamable_http_app() MUST be called before .session_manager is read.
_mcp = get_mcp_server()
# Inner route -> "/" so that mounting at "/mcp" resolves to exactly /mcp (no doubling).
_mcp.settings.streamable_http_path = "/"
_mcp_app = _mcp.streamable_http_app()  # Starlette; single Route at "/"


@contextlib.asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Run the MCP StreamableHTTPSessionManager for the parent app's lifetime.

    Mounted sub-apps don't get their lifespan run by Starlette, so we drive the
    session manager's task group here (canonical ``async with run(): yield`` recipe).
    Without this, requests to ``/mcp`` would hang.
    """
    async with _mcp.session_manager.run():
        yield


def _build_app() -> FastAPI:
    """Assemble the combined app: REST app's routes + MCP mounted at ``/mcp``.

    We can't pass ``lifespan=`` to the already-constructed REST app, so we attach our
    MCP lifespan to its router. The REST app has no prior lifespan (Phase 1/2/3), so
    there is nothing to chain; if one is ever added to api/app.py, compose it here.
    """
    rest_app.router.lifespan_context = _lifespan
    # Mount at "/mcp"; the sub-app's inner route is "/" => public path is exactly /mcp,
    # and rest_app.routes carries a Mount with path "/mcp" (structurally discoverable).
    rest_app.mount("/mcp", _mcp_app)
    return rest_app


app = _build_app()

__all__ = ["app"]
