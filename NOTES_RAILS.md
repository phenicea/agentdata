# NOTES_RAILS.md — payment rails beyond x402 (notes only, no implementation)

> Status: **notes / design seam only.** Nothing here is built. The only rail we
> ship is x402 (`src/agentdata/payment/`). This file records what a *second* rail
> — specifically an MPP-style adapter — would require, so the choice to abstract
> the flow (`PaymentRail` in `src/agentdata/payment/rail.py`) is justified and the
> future work is scoped. Do **not** add a dependency or write an adapter off this
> file: fetch the live SDK/docs first (CLAUDE.md §0 — never guess a signature).

## The seam that already exists

`PaymentRail` (in `rail.py`) abstracts the payment flow to four rail-neutral,
dict-in/dict-out steps:

```
price -> challenge -> verify -> settle
```

`X402Rail` implements it by **delegating** to the existing x402 logic
(`api.pricing`, `payment.pricing_402`, `payment.facilitator`); the official
`PaymentMiddlewareASGI` stays the mounted production path. The business/compute
layer (`compute/`, `compute/tiers.py`) is therefore rail-agnostic: it asks *a
rail* to get paid, not x402 specifically.

This is the entire point of the abstraction — adding a rail must NOT touch
`compute/` or the API response contract.

## What an MPP (or any session/batch) adapter would require

MPP-style rails differ from x402 mainly in **when** money moves: x402 settles
**per call** (one HTTP 402 → one on-chain settle), whereas a session/batch rail
opens a **session** (or channel), meters many calls against it, and settles
**once per session/batch**. That single difference drives everything below.

### 1. Fetch the live spec FIRST (no guessing)
Before any code:
- Confirm the **real protocol name, current spec version, and an official SDK**
  (PyPI/npm) — "MPP" here is a placeholder for "a metered/session/batch rail".
  Verify it actually exists and is maintained; capture the exact package name +
  version, same as ADR-001 §0 did for x402 2.13.0 / mcp 1.27.2.
- Confirm the **chain(s) / settlement asset** (USDC? which networks? CAIP-2 ids).
- Confirm **testnet support** — this rail must be testable on testnet with no real
  funds, exactly like x402 on Base Sepolia, or it does not get wired.

### 2. Mapping onto the `PaymentRail` four steps
| `PaymentRail` step | x402 (today) | MPP / session-batch adapter (future) |
|---|---|---|
| `price`     | dollar string from the single pricing table | **same** — prices stay in `api.pricing` (one source of truth); a rail never invents prices |
| `challenge` | per-call HTTP-402 payment requirements | **open / reference a session**: return session-open terms or a "charge against session X" reference instead of a one-shot 402 |
| `verify`    | facilitator `/verify` on one payment proof | verify the **session is open and has budget/allowance** for this call (not a single transfer proof) |
| `settle`    | facilitator `/settle` — on-chain, per call | **defer**: accrue the call against the session; real settlement happens on **session close / batch flush**, not per call |

The interface fits, but two things it does **not** currently model and an MPP
adapter would need:
- **Session lifecycle**: `open_session` / `close_session` (or `flush_batch`).
  Decision to make at implementation time: extend `PaymentRail` with optional
  session hooks, OR keep the 4 methods and hold session state inside the adapter
  (challenge opens-or-reuses, settle is a no-op until a separate flush). Prefer
  the latter first (smaller blast radius) unless the SDK forces explicit hooks.
- **Per-session state / idempotency**: which session a request belongs to, how
  much budget remains, replay/double-count protection. x402's per-call model has
  none of this; a batch rail must not double-charge a metered call.

### 3. Config & safety (must mirror what x402 already does)
- A `PAYMENT_RAIL` env selector wired into `get_rail()` (currently always returns
  `X402Rail`). Default stays `x402`. No behavior change unless explicitly set.
- Same guardrails: testnet by default, `guard_network` on the funds-adjacent path,
  mainnet locked behind `ALLOW_MAINNET`, **only the public address** in config —
  the private key never enters the repo (CLAUDE.md §14).
- Lazy SDK import inside the adapter (as `payment/*` does), so installing the new
  rail's SDK is optional and the Phase 1/2 app keeps importing without it.

### 4. Tests (offline, no funds — same discipline as `test_rail.py` / `test_payment.py`)
- New rail mocked end-to-end; no network, no real funds, testnet-only.
- Assert it satisfies the `PaymentRail` Protocol (structural check).
- Assert `price` still reads the single pricing table (testnet => `$0`).
- Assert session/batch accounting does not double-charge and is replay-safe.

## Explicitly out of scope (per founder rules)
- No real adapter, no SDK dependency, no settlement code in this pass.
- ACP / AP2 and other agent-commerce protocols: **notes only**, not evaluated or
  built here. If/when relevant, they get the same treatment as above (fetch live
  spec, map onto the four steps, mirror the safety/config/testnet discipline).
- Mainnet for any rail: human escalation, unchanged.
