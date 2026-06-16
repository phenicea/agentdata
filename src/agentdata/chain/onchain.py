"""On-chain pool reader for Base (lazy ``web3``).

Sourcing is on-chain by design so that the *derived* metrics we sell are cleanly
redistributable (DECISION_LOG / ADR-001): we read public chain state, we don't
resell a vendor dataset.

Honesty / safety notes (CTO mandate — never ship a guessed signature):

* Contract addresses are **not hardcoded**. They are read from env and MUST be
  verified against live RPC before enabling (``onchain`` mode). See ADR-001 for
  the verification checklist (Aerodrome ``LpSugar`` struct layout, Uniswap v3
  ``QuoterV2`` address on Base).
* Aerodrome volatile/stable pools expose reserves, so they map directly onto the
  reserve-based :class:`PoolState` model. Uniswap v3 concentrated liquidity has no
  closed-form reserves — its quotes come from ``QuoterV2`` and are integrated as
  an external quote source (documented extension point below), not faked here.

This module intentionally refuses to run until it is explicitly configured, rather
than guessing. That refusal is the correct behavior for anything touching funds.
"""

from __future__ import annotations

import os

from agentdata.compute.amm import PoolKind, PoolState
from agentdata.config import Settings

# Minimal, standard ABI for a v2/stable-style pool that exposes reserves.
# (Documented interface; the deployed ADDRESS still must be verified per ADR-001.)
_RESERVES_ABI = [
    {
        "name": "getReserves",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [
            {"name": "_reserve0", "type": "uint256"},
            {"name": "_reserve1", "type": "uint256"},
            {"name": "_blockTimestampLast", "type": "uint256"},
        ],
    }
]


class OnChainPoolProvider:
    """Reads Base pools over RPC. Requires explicit, verified configuration."""

    def __init__(self, settings: Settings) -> None:
        if not settings.base_rpc_url:
            raise RuntimeError(
                "POOL_SOURCE=onchain requires BASE_RPC_URL. Refusing to guess an "
                "endpoint. Set it in the environment (see .env.example)."
            )
        self.settings = settings
        self._w3 = self._connect(settings.base_rpc_url)

    @staticmethod
    def _connect(rpc_url: str):
        try:
            from web3 import HTTPProvider, Web3  # lazy import
        except ImportError as exc:  # pragma: no cover - depends on optional dep
            raise RuntimeError(
                "onchain mode needs web3: pip install 'agentdata[.]' or 'web3>=6.20'."
            ) from exc
        w3 = Web3(HTTPProvider(rpc_url))
        if not w3.is_connected():
            raise RuntimeError(f"could not connect to Base RPC at {rpc_url!r}")
        return w3

    def get_pools(self, token: str) -> list[PoolState]:
        """Read reserve-based pools for ``token`` from a verified pool registry.

        Phase-1 on-chain wiring is gated until the pool registry (token -> pool
        addresses + kind + decimals) is populated from a verified source. Until
        then this refuses rather than returns guessed data. The verification step
        is ADR-001 (Aerodrome LpSugar enumeration / Uniswap v3 QuoterV2 address).
        """
        registry = _load_pool_registry()
        entries = registry.get(token.upper())
        if not entries:
            raise NotImplementedError(
                f"no verified pool registry entry for {token!r}. Populate the "
                "registry from live Aerodrome LpSugar / verified pool addresses "
                "before enabling onchain mode (ADR-001)."
            )
        return [self._read_reserve_pool(**e) for e in entries]

    def _read_reserve_pool(self, *, address: str, kind: str, fee_bps: float,
                           dec_in: int, dec_out: int, dex: str,
                           sell_is_token0: bool) -> PoolState:
        contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(address), abi=_RESERVES_ABI
        )
        r0, r1, _ = contract.functions.getReserves().call()
        # normalize wei -> human units; orient so token being sold is "in"
        if sell_is_token0:
            reserve_in = r0 / (10 ** dec_in)
            reserve_out = r1 / (10 ** dec_out)
        else:
            reserve_in = r1 / (10 ** dec_in)
            reserve_out = r0 / (10 ** dec_out)
        return PoolState(
            reserve_in=reserve_in,
            reserve_out=reserve_out,
            fee_bps=fee_bps,
            kind=PoolKind(kind),
            pool_id=address,
            dex=dex,
        )

    def is_pegged(self, token: str) -> float | None:
        pegged = os.getenv("PEGGED_TOKENS", "")  # e.g. "USDC:1.0,USDT:1.0"
        for item in filter(None, (s.strip() for s in pegged.split(","))):
            sym, _, ref = item.partition(":")
            if sym.upper() == token.upper():
                return float(ref) if ref else 1.0
        return None


def _load_pool_registry() -> dict:
    """Verified token -> pool-entry registry. Empty until populated (ADR-001)."""
    # Intentionally empty: no guessed addresses. Populated from a verified source
    # (live Aerodrome LpSugar enumeration) as part of the on-chain integration.
    return {}
