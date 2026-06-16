"""MCP server wrapper for the executable-liquidity / exit-cost endpoint (Phase 3).

Exposes the same compute path as the REST API as a single MCP tool
(``liquidity_exit_cost``), over the streamable-http transport. The tool's identity
and schema live in :mod:`agentdata.mcp.tool_schema` (single source of truth, reused
by the server, ``server.json`` and ``llms.txt``).

``get_mcp_server`` is implemented by :mod:`agentdata.mcp.server` (separate file). It
is re-exported lazily here so importing this package does not require the ``mcp`` SDK
until the server is actually built.
"""

from __future__ import annotations

from .tool_schema import (
    TOOL_NAME,
    input_schema,
    output_summary,
    tool_description,
)

__all__ = [
    "TOOL_NAME",
    "tool_description",
    "input_schema",
    "output_summary",
    "get_mcp_server",
    "main",
]


def __getattr__(name: str):
    # Lazy re-export: defer to server.py (which imports the `mcp` SDK) only when
    # `get_mcp_server`/`main` are actually requested. Keeps `import agentdata.mcp`
    # cheap and SDK-free for callers that just need the schema (server.json / llms.txt
    # gen).
    if name in ("get_mcp_server", "main"):
        from . import server

        return getattr(server, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
