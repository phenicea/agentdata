# AgentData — Executable Liquidity (endpoint #1)

A pay-per-call data endpoint for AI agents: **size-aware exit cost, depeg risk, and
liquidity fragility** for a token on Base. Not raw prices — *computed, normalized,
decision-grade* intelligence an agent needs before it acts. Settled in USDC via
[x402](https://x402.org) (Phase 2). Sourced on-chain, so the derived data is
cleanly redistributable.

> Strategy, values, and roadmap live in [`CLAUDE.md`](./CLAUDE.md). Decisions are
> logged in [`decisions/DECISION_LOG.md`](./decisions/DECISION_LOG.md) and
> [`decisions/adr/`](./decisions/adr/).

## What it answers

> "If I try to exit this position right now, what does it actually cost me, how
> much can I move before slippage blows past X bps, and how fragile is that
> liquidity?"

Three priced tiers (single source of truth in `agentdata/api/pricing.py`):

| Tier  | Contents                                                        | Mainnet price |
|-------|-----------------------------------------------------------------|---------------|
| quote | best-route exit cost for one size                               | $0.008        |
| risk  | exit cost + fragility (+ depeg for pegged assets) — **default** | $0.02         |
| deep  | risk + multi-size exit-cost curve + max-size-before-cost ladder | $0.04         |

Testnet forces every price to **$0** (the 402 flow is still exercised end-to-end).

## Layout

```
src/agentdata/
  config.py            # env-driven; NETWORK_MODE testnet|mainnet (testnet default)
  compute/             # the value-add: pure, deterministic, unit-tested math
    amm.py             #   constant-product + Solidly stable curve, exit cost
    routing.py         #   cheapest-venue selection
    depeg.py           #   depeg deviation / dispersion / score
    fragility.py       #   depth + concentration + convexity -> fragility score
    tiers.py           #   quote / risk / deep orchestration
  chain/               # on-chain Base reads (Aerodrome / Uniswap), web3 lazy
    provider.py        #   FixturePoolProvider (default) + factory
    onchain.py         #   OnChainPoolProvider (env-gated, no guessed addresses)
  api/                 # FastAPI JSON layer + pricing + stable schema
  monitoring/          # uptime, latency p50/p95, error rate, calls per tier
tests/                 # unittest (stdlib for compute; fastapi for api)
```

## Run it (local, no funds, no network)

```bash
pip install -e .            # or: pip install fastapi pydantic 'uvicorn[standard]'
uvicorn agentdata.api.app:app --reload
# then:
curl 'http://127.0.0.1:8000/v1/liquidity/exit-cost?token=WETH&size=10&tier=risk'
curl 'http://127.0.0.1:8000/pricing'
curl 'http://127.0.0.1:8000/metrics'
```

Defaults: `NETWORK_MODE=testnet`, `POOL_SOURCE=fixture` (deterministic demo pools
`WETH`, `THIN`, `USDX`). See `.env.example`.

## Test

```bash
# compute core needs no dependencies:
PYTHONPATH=src python -m unittest discover -s tests
```

## Status

- **Phase 1 (local endpoint): done.** compute + chain seam + API + monitoring, 42
  tests green.
- **Phase 2 (x402 testnet): next.** Payment middleware in front of the API, free
  testnet facilitator on Base Sepolia. No real USDC; mainnet is an escalated human
  decision (CLAUDE.md §0/§14).
- On-chain mode requires a verified pool registry before use (ADR-001) — the code
  refuses to run on guessed contract addresses rather than fake data.
