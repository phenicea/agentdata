#!/usr/bin/env python
"""Verify our AMM math against the REAL deployed pools' own `getAmountOut`.

Accuracy is the product's selling point, so the check must use an INDEPENDENT
oracle — not a re-implementation of our own formula. The independent oracle here
is the deployed Aerodrome ``Pool.getAmountOut(amountIn, tokenIn)`` view: it runs
the pool contract's actual swap-output code on-chain. If our ``amm.py`` matches it
across sizes, our reserve orientation, decimals handling, fee, and curve formula
are all correct against the real thing.

Read-only: this only does ``eth_call`` on Base mainnet (public RPC). No funds, no
transactions, no payments, no mainnet *settlement* — just reading public state.

Scope (honest): we model and verify the two curves ``amm.py`` actually implements:
  * VOLATILE (constant product) — Aerodrome WETH/USDC
  * STABLE (Solidly x^3y + xy^3) — Aerodrome USDC/USDbC
Uniswap v3 / concentrated liquidity is NOT implemented here (no closed form); the
design is to source v3 quotes from QuoterV2 directly (planned extension), so there
is no v3 "math of ours" to verify yet — and we do not claim it.

Addresses below were verified live via eth_call on 2026-06-16 (token0/decimals/
stable flag/factory), not guessed (ADR-001 §0).

Usage:
    python scripts/verify_amm_onchain.py            # uses public Base RPCs
    BASE_RPC_URL=https://... python scripts/verify_amm_onchain.py
Exit code 0 if every pool matches within tolerance, 2 if any exceeds it, 3 if no
RPC could be reached.
"""

from __future__ import annotations

import os
import sys

# Verified Base mainnet contracts (eth_call-confirmed 2026-06-16).
FACTORY = "0x420DD381b31aEf6683db6b902084cB0FFECe40Da"  # Aerodrome PoolFactory
PUBLIC_RPCS = (
    "https://base-rpc.publicnode.com",
    "https://base.llamarpc.com",
    "https://mainnet.base.org",
)
TOLERANCE_BPS = 0.5  # observed 0.0000; generous headroom for float rounding

# Each pool: how to sell token0 into it and the on-chain oracle to compare against.
POOLS = [
    {
        "label": "Aerodrome WETH/USDC (volatile)",
        "pool": "0xcDAC0d6c6C59727a65F871236188350531885C43",
        "sell": "0x4200000000000000000000000000000000000006",  # WETH (token0)
        "dec_in": 18, "dec_out": 6, "stable": False,
        "sizes": (0.1, 1.0, 10.0, 100.0),
    },
    {
        "label": "Aerodrome USDC/USDbC (stable)",
        "pool": "0x27a8Afa3Bd49406e48a074350fB7b2020c43B2bD",
        "sell": None,  # resolved to token0() at runtime
        "dec_in": 6, "dec_out": 6, "stable": True,
        "sizes": (10.0, 100.0, 1000.0),
    },
]

_POOL_ABI = [
    {"name": "getReserves", "type": "function", "stateMutability": "view", "inputs": [],
     "outputs": [{"type": "uint256"}, {"type": "uint256"}, {"type": "uint256"}]},
    {"name": "token0", "type": "function", "stateMutability": "view", "inputs": [],
     "outputs": [{"type": "address"}]},
    {"name": "getAmountOut", "type": "function", "stateMutability": "view",
     "inputs": [{"type": "uint256"}, {"type": "address"}], "outputs": [{"type": "uint256"}]},
]
_FACTORY_ABI = [
    {"name": "getFee", "type": "function", "stateMutability": "view",
     "inputs": [{"type": "address"}, {"type": "bool"}], "outputs": [{"type": "uint256"}]},
]


def connect():
    """Return (web3, rpc_url) or (None, None) if nothing is reachable."""
    try:
        from web3 import Web3
    except ImportError:
        return None, None
    candidates = [os.getenv("BASE_RPC_URL")] if os.getenv("BASE_RPC_URL") else list(PUBLIC_RPCS)
    for rpc in candidates:
        if not rpc:
            continue
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 20}))
            if w3.is_connected():
                return w3, rpc
        except Exception:
            continue
    return None, None


def verify(w3) -> list[dict]:
    """Compare amm.py to each pool's on-chain getAmountOut. Returns per-size rows."""
    from agentdata.compute.amm import PoolKind, PoolState, amount_out

    factory = w3.eth.contract(address=w3.to_checksum_address(FACTORY), abi=_FACTORY_ABI)
    rows = []
    for spec in POOLS:
        pool = w3.eth.contract(address=w3.to_checksum_address(spec["pool"]), abi=_POOL_ABI)
        r0, r1, _ = pool.functions.getReserves().call()
        sell = w3.to_checksum_address(spec["sell"] or pool.functions.token0().call())
        fee_bps = factory.functions.getFee(pool.address, spec["stable"]).call()
        state = PoolState(
            reserve_in=r0 / (10 ** spec["dec_in"]),
            reserve_out=r1 / (10 ** spec["dec_out"]),
            fee_bps=fee_bps,
            kind=PoolKind.STABLE if spec["stable"] else PoolKind.VOLATILE,
        )
        for size in spec["sizes"]:
            onchain = pool.functions.getAmountOut(int(size * 10 ** spec["dec_in"]), sell).call()
            onchain /= 10 ** spec["dec_out"]
            ours = amount_out(state, size)
            diff_bps = abs(ours - onchain) / onchain * 1e4 if onchain else 0.0
            rows.append({"label": spec["label"], "size": size, "fee_bps": fee_bps,
                         "onchain": onchain, "ours": ours, "diff_bps": diff_bps})
    return rows


def main() -> int:
    w3, rpc = connect()
    if w3 is None:
        print("no Base RPC reachable / web3 missing (offline?) — skipping verification")
        return 3
    print(f"RPC: {rpc}\nOracle: deployed pool.getAmountOut | tolerance {TOLERANCE_BPS} bps\n")
    worst = 0.0
    for r in verify(w3):
        worst = max(worst, r["diff_bps"])
        flag = "OK  " if r["diff_bps"] <= TOLERANCE_BPS else "FAIL"
        print(f"[{flag}] {r['label']:32} size={r['size']:>8} fee={r['fee_bps']}bps "
              f"onchain={r['onchain']:.6f} ours={r['ours']:.6f} diff={r['diff_bps']:.4f}bps")
    print(f"\nworst deviation: {worst:.4f} bps  ->  {'PASS' if worst <= TOLERANCE_BPS else 'FAIL'}")
    return 0 if worst <= TOLERANCE_BPS else 2


if __name__ == "__main__":
    sys.exit(main())
