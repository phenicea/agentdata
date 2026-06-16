# AgentData — Executable Liquidity / Exit-Cost — API docs

> **Status: TESTNET / PREVIEW.** No real funds anywhere. On testnet every per-call price
> is forced to **$0** and the x402 flow runs in test funds only. The dollar figures in
> this document are the *mainnet target* prices — they are **not** active charges.
> Switching to mainnet is a separate, human-reviewed escalation (CLAUDE.md §0/§14).

This is plain markdown, readable without JS or auth, so an agent can read it directly to
decide whether and how to call the service.

## What this service does

One focused thing: given a token and a sell size, it returns the **size-aware exit cost**,
the **depeg risk** (for pegged assets), and the **liquidity fragility** of that token on
Base. The numbers are *computed and normalized* from on-chain AMM state (Aerodrome +
Uniswap v3), not raw prices. The math is deterministic and verifiable against an on-chain
swap quote, which is the accuracy moat.

Settlement is in USDC via the open [x402](https://x402.org) protocol (HTTP 402). The
payment is the authentication: no API key, no account, no subscription.

## Network and settlement

| | Testnet (default) | Mainnet (escalated, inactive) |
|---|---|---|
| Chain | Base Sepolia | Base |
| CAIP-2 | `eip155:84532` | `eip155:8453` |
| Facilitator | `https://x402.org/facilitator` | set at escalation, never defaulted |
| Per-call price | **$0** (all tiers) | target prices below |
| Asset | USDC | USDC |

The receiving address is supplied via the `PAY_TO_ADDRESS` environment variable (public
address only; private keys never live in the repo). The x402 payment surface is on the
REST/HTTP layer; the MCP tool exposes compute + pricing metadata, not the payment
middleware.

## Tiers and pricing

Single source of truth: `agentdata/api/pricing.py`. Currency: USDC. Default tier: `risk`.
Floor defended at $0.008 (no race to the bottom).

| Tier  | Param        | Contents                                                          | Testnet | Mainnet target |
|-------|--------------|------------------------------------------------------------------|---------|----------------|
| quote | `tier=quote` | best-route exit cost for one size                                | $0      | $0.008         |
| risk  | `tier=risk`  | exit cost + fragility (+ depeg for pegged assets) — **default**  | $0      | $0.02          |
| deep  | `tier=deep`  | risk + multi-size exit-cost curve + max-size-before-cost ladder  | $0      | $0.04          |

The live pricing table is served at `GET /pricing` and replicated into OpenAPI, the MCP
tool metadata, and `llms.txt` — all from this one source.

```json
// GET /pricing  (testnet)
{
  "currency": "USDC",
  "default_tier": "risk",
  "network": "testnet",
  "tiers": {
    "quote": { "price": 0.0, "price_string": "$0" },
    "risk":  { "price": 0.0, "price_string": "$0" },
    "deep":  { "price": 0.0, "price_string": "$0" }
  }
}
```

On mainnet the same shape carries `0.008 / 0.02 / 0.04` and `"$0.008" / "$0.02" / "$0.04"`.

## REST API

### `GET /v1/liquidity/exit-cost`

Size-aware exit cost (+ fragility/depeg by tier) for a token on Base.

**Query parameters**

| Name  | Type           | Required | Default | Description |
|-------|----------------|----------|---------|-------------|
| token | string         | yes      | —       | Token symbol or address to exit (sell). |
| size  | number (> 0)   | yes      | —       | Sell size in human token units. |
| tier  | enum           | no       | `risk`  | `quote` \| `risk` \| `deep`. |
| pool  | string         | no       | —       | Restrict the computation to a single pool id. |

**Responses**

- `200` — `ExitCostResponse` (see schema below).
- `400` — unknown tier, or invalid compute input (e.g. no pools to compute).
- `404` — token not known, or requested `pool` not found for the token.
- `501` — on-chain provider not yet configured (pool registry empty, ADR-001).

Versioned under `/v1/`; the response schema is additive-only within a version.

### Output schema (`ExitCostResponse`)

```jsonc
{
  "tier": "risk",                 // tier actually computed
  "network": "testnet",          // testnet | mainnet
  "token": "USDX",
  "size": 100000.0,

  "exit_cost": {                  // always present
    "size": 100000.0,
    "amount_out": 99720.0,        // output-token units received (fee incl.)
    "mid_price": 0.997,           // marginal price (out per 1 in) at size 0
    "exec_price": 0.9972,         // realized price = amount_out / size
    "total_cost_bps": 38.0,       // loss vs mid (fee + slippage), bps
    "price_impact_bps": 31.0,     // slippage only (fee excluded), bps
    "fee_bps": 7.0                // pool fee component, bps
  },

  "route": {                      // always present
    "best": { /* ExitCostModel, as exit_cost */ },
    "pool_id": "0xpoolD",
    "dex": "aerodrome-stable",
    "routed_split": false,        // true if cost is split across venues
    "venues_considered": 2
  },

  // present for tier=risk and tier=deep:
  "fragility": {
    "score": 27.0,                // 0..100, higher = more fragile
    "depth_score": 18.0,
    "concentration_score": 41.0,
    "convexity_score": 12.0,
    "total_exit_liquidity": 7982000.0,
    "venues": 2
  },

  // present for pegged tokens (tier=risk/deep) only:
  "depeg": {
    "deviation_bps": 30.0,
    "dispersion_bps": 4.0,
    "weighted_price": 0.997,
    "total_liquidity": 7982000.0,
    "score": 6.0                  // 0..100, higher = more depeg risk
  },

  // present for tier=deep only:
  "exit_cost_curve": [
    { "size_multiple": 0.25, /* ...ExitCostModel fields... */ },
    { "size_multiple": 0.5,  /* ... */ },
    { "size_multiple": 1.0,  /* ... */ },
    { "size_multiple": 2.0,  /* ... */ },
    { "size_multiple": 4.0,  /* ... */ }
  ],
  "max_size_before_cost": [
    { "max_cost_bps": 10.0,  "max_size": 12000.0 },
    { "max_cost_bps": 25.0,  "max_size": 31000.0 },
    { "max_cost_bps": 50.0,  "max_size": 64000.0 },
    { "max_cost_bps": 100.0, "max_size": 130000.0 }
  ],
  "cross_check": {
    "deepest_pool_id": "0xpoolD",
    "deepest_pool_cost_bps": 39.0,
    "best_route_cost_bps": 38.0
  }
}
```

Field-by-tier presence:

| Field                  | quote | risk | deep |
|------------------------|:-----:|:----:|:----:|
| `exit_cost`, `route`   |   ✓   |  ✓   |  ✓   |
| `fragility`            |       |  ✓   |  ✓   |
| `depeg` (pegged only)  |       |  ✓   |  ✓   |
| `exit_cost_curve`      |       |      |  ✓   |
| `max_size_before_cost` |       |      |  ✓   |
| `cross_check`          |       |      |  ✓   |

Notes: scores (`fragility.score`, `depeg.score`) are 0..100, higher = worse. Costs are in
bps and in output-token units. `depeg` only appears for tokens with a known peg.

### Helper endpoints (no payment)

| Endpoint     | Returns |
|--------------|---------|
| `GET /pricing` | Machine-readable pricing table (single source of truth). |
| `GET /health`  | `{ "status": "ok", "network": "...", "pool_source": "..." }`. |
| `GET /metrics` | Uptime, latency p50/p95 (global + per tier), error rate, calls per tier. |
| `GET /openapi.json` | Full OpenAPI spec. |

## Examples (curl)

Local defaults: `NETWORK_MODE=testnet`, `POOL_SOURCE=fixture` (deterministic demo tokens
`WETH`, `THIN`, `USDX`). Replace the host with the deployed base URL once available.

```bash
# Default tier (risk): full risk view of a healthy, deep token.
curl 'http://127.0.0.1:8000/v1/liquidity/exit-cost?token=WETH&size=10'

# quote tier: cheap single-size lookup.
curl 'http://127.0.0.1:8000/v1/liquidity/exit-cost?token=WETH&size=10&tier=quote'

# deep tier: liquidation ladder across sizes + cross-check.
curl 'http://127.0.0.1:8000/v1/liquidity/exit-cost?token=USDX&size=100000&tier=deep'

# Pegged stablecoin -> depeg signal appears in risk/deep.
curl 'http://127.0.0.1:8000/v1/liquidity/exit-cost?token=USDX&size=50000&tier=risk'

# Thin single-venue token -> high fragility score.
curl 'http://127.0.0.1:8000/v1/liquidity/exit-cost?token=THIN&size=20000&tier=risk'

# Restrict to a single pool.
curl 'http://127.0.0.1:8000/v1/liquidity/exit-cost?token=WETH&size=10&pool=0xpoolA'

# Pricing / health / metrics.
curl 'http://127.0.0.1:8000/pricing'
curl 'http://127.0.0.1:8000/health'
curl 'http://127.0.0.1:8000/metrics'
```

### x402 payment flow (testnet)

When the x402 middleware is enabled (`X402_ENABLED=true` + `PAY_TO_ADDRESS` set), an
unpaid call returns `HTTP 402` with payment terms (amount per the requested `tier`,
`pay_to`, network `eip155:84532`, asset USDC). The agent pays on-chain and replays the
request with the payment proof; the facilitator verifies/settles and the JSON is served.
On testnet the amount is $0, so the flow is exercised without real value.

## MCP tool

The same compute is exposed as a single MCP tool over **streamable-http**. The remote MCP
endpoint is advertised at `<base_url>/mcp`.

- **Tool:** `liquidity_exit_cost`
- **Inputs:** `token` (string, required), `size` (number > 0, required),
  `tier` (enum `quote`|`risk`|`deep`, default `risk`), `pool` (string, optional).
- **Output:** the same `ExitCostResponse` schema as the REST endpoint — REST/MCP parity is
  guaranteed because the tool runs the identical compute path
  (`get_provider` → `get_pools`/`is_pegged` → `compute_tier`).
- **Pricing:** per-tier prices are described in the tool metadata, read from the same
  pricing table — never hardcoded.

Discovery: a `server.json` (MCP Registry, remote streamable-http) and `package.json` are
shipped as ready-to-publish artifacts. The listing is marked testnet/preview.

## Status and guarantees

- **Testnet/preview.** All prices $0; no real USDC; mainnet is an inactive, escalated path.
- **Stable schema.** `/v1/` is additive-only; breaking changes go to `/v2/`.
- **Single-purpose, deterministic, on-chain-sourced.** Output is verifiable against an
  on-chain swap quote; data is cleanly redistributable.
- **Phase 1 + 2** (compute + x402 testnet, opt-in) are complete and tested. Phase 3
  (discoverability: MCP server + this doc + `llms.txt` + OpenAPI) is the current step.
