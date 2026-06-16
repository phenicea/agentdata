# AgentData — deploy image (testnet / preview).
#
# Single Python ASGI process serving BOTH the FastAPI REST routes (/health,
# /pricing, /v1/liquidity/exit-cost, /llms.txt, /docs/api.md, /metrics) AND the
# MCP streamable-http endpoint (/mcp) on ONE port. The combined app is
# `agentdata.asgi:app` (FastAPI + mounted MCP sub-app with the MCP session
# manager wired into the parent lifespan — see SPEC). Render injects $PORT.
#
# Hard rules (CLAUDE.md §0/§14, ADR-001 §4): testnet only, no mainnet value
# active by default, NO secret/private key baked into the image. Only the PUBLIC
# PAY_TO_ADDRESS ever reaches runtime env, supplied by the platform — never here.

FROM python:3.11-slim

# Quieter, deterministic Python; no .pyc, unbuffered logs for the PaaS log stream.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install the project (incl. the `mcp` extra needed by agentdata.asgi) from
# pyproject. Copy only the build inputs first so the layer caches across edits
# to non-packaging files.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[mcp]"

# Discovery artifacts served verbatim by the app live at the repo root
# (llms.txt) and docs/ — ship them so /llms.txt and /docs/api.md resolve (200).
COPY llms.txt ./llms.txt
COPY docs ./docs

# Default network posture baked as a safety floor; the platform env (render.yaml)
# re-declares these explicitly. Mainnet stays locked: NETWORK_MODE=testnet and
# ALLOW_MAINNET is intentionally absent (the app refuses to start on mainnet
# without it — ADR-001 §4). No PAY_TO_ADDRESS / private key here.
ENV NETWORK_MODE=testnet \
    POOL_SOURCE=fixture \
    X402_ENABLED=false

# One uvicorn process, one port, REST + MCP. $PORT is provided by Render; default
# 8000 for local `docker run`. Shell form so $PORT expands at runtime.
CMD ["sh", "-c", "uvicorn agentdata.asgi:app --host 0.0.0.0 --port ${PORT:-8000}"]
