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

Edge-case hardening (block C)
-----------------------------
Every interaction with the chain can fail (RPC down/unreachable, slow timeout,
a contract that reverts, an empty/uninitialized pool). The provider turns those
into a single, clear :class:`ChainError` with an actionable message instead of
leaking a raw ``web3`` traceback or crashing the request. ``ChainError`` subclasses
``RuntimeError`` so existing callers that already treat ``RuntimeError`` as a
configuration failure keep working unchanged. The "registry not populated yet"
path stays a :class:`NotImplementedError` (callers map it to 501 / INTERNAL_ERROR),
and the "no pools for this token" path stays a :class:`TokenNotFound` (404 /
INVALID_PARAMS) — the public exception contract of the provider is preserved.
"""

from __future__ import annotations

import os

from agentdata.compute.amm import PoolKind, PoolState
from agentdata.chain.provider import TokenNotFound
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


class ChainError(RuntimeError):
    """A clear, caller-facing on-chain read failure.

    Raised for RPC connectivity problems, contract calls that revert, malformed
    responses, and empty/uninitialized pools. Subclasses :class:`RuntimeError`
    so existing ``except RuntimeError`` configuration-error handling still catches
    it, while giving callers a precise type to special-case if they want to.
    """


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
        # ``is_connected`` itself performs a network round-trip and can raise on a
        # dead host / DNS failure / refused connection. Treat any failure — raised
        # or a plain ``False`` — as a clean ChainError, never a leaked traceback.
        try:
            connected = w3.is_connected()
        except Exception as exc:  # noqa: BLE001 - web3 raises many transport types
            raise ChainError(
                f"could not reach Base RPC at {rpc_url!r}: {exc}. Check BASE_RPC_URL "
                "and network connectivity."
            ) from exc
        if not connected:
            raise ChainError(
                f"could not connect to Base RPC at {rpc_url!r} (no response). "
                "Check BASE_RPC_URL and network connectivity."
            )
        return w3

    def get_pools(self, token: str) -> list[PoolState]:
        """Read reserve-based pools for ``token`` from a verified pool registry.

        Phase-1 on-chain wiring is gated until the pool registry (token -> pool
        addresses + kind + decimals) is populated from a verified source. Until
        then this refuses rather than returns guessed data. The verification step
        is ADR-001 (Aerodrome LpSugar enumeration / Uniswap v3 QuoterV2 address).

        Failure modes (all clear, none crash the caller):

        * registry empty for *every* token -> ``NotImplementedError`` (feature not
          wired yet; callers map it to 501 / INTERNAL_ERROR);
        * registry populated but this token absent -> ``TokenNotFound`` (404);
        * RPC down / revert / empty pool while reading -> :class:`ChainError`.
        """
        if not token or not token.strip():
            raise TokenNotFound("token must be a non-empty symbol/address")

        registry = _load_pool_registry()
        if not registry:
            # The whole on-chain registry is still empty: this is "not wired yet",
            # not "unknown token". Keep it distinct so the API answers 501, not 404.
            raise NotImplementedError(
                "on-chain pool registry is empty. Populate it from live Aerodrome "
                "LpSugar / verified pool addresses before enabling onchain mode "
                "(ADR-001) — refusing to read guessed addresses."
            )

        entries = registry.get(token.upper())
        if not entries:
            raise TokenNotFound(
                f"no verified pool registry entry for {token!r}. Known tokens: "
                f"{sorted(registry)}."
            )
        return [self._read_reserve_pool(**e) for e in entries]

    def _read_reserve_pool(self, *, address: str, kind: str, fee_bps: float,
                           dec_in: int, dec_out: int, dex: str,
                           sell_is_token0: bool) -> PoolState:
        try:
            checksummed = self._w3.to_checksum_address(address)
        except Exception as exc:  # noqa: BLE001 - bad address shapes raise various
            raise ChainError(
                f"invalid pool address {address!r} in registry: {exc}."
            ) from exc

        contract = self._w3.eth.contract(address=checksummed, abi=_RESERVES_ABI)
        try:
            reserves = contract.functions.getReserves().call()
        except Exception as exc:  # noqa: BLE001 - RPC down / revert / decode errors
            raise ChainError(
                f"failed to read reserves from pool {address!r} on {dex!r}: {exc}. "
                "The RPC may be down/rate-limited, or the address may not be a "
                "reserve-style pool (verify per ADR-001)."
            ) from exc

        try:
            r0, r1, _ = reserves
        except (TypeError, ValueError) as exc:
            raise ChainError(
                f"unexpected getReserves() response from pool {address!r}: "
                f"{reserves!r}. Expected a (reserve0, reserve1, timestamp) tuple."
            ) from exc

        # Empty / uninitialized pool: zero (or negative) reserves can't be priced.
        # Catch it here with a clear message instead of letting PoolState raise a
        # generic "reserves must be positive" ValueError downstream.
        if r0 <= 0 or r1 <= 0:
            raise ChainError(
                f"pool {address!r} on {dex!r} is empty/uninitialized "
                f"(reserves {r0}, {r1}); cannot compute an exit cost."
            )

        # normalize wei -> human units; orient so token being sold is "in"
        if sell_is_token0:
            reserve_in = r0 / (10 ** dec_in)
            reserve_out = r1 / (10 ** dec_out)
        else:
            reserve_in = r1 / (10 ** dec_in)
            reserve_out = r0 / (10 ** dec_out)

        try:
            return PoolState(
                reserve_in=reserve_in,
                reserve_out=reserve_out,
                fee_bps=fee_bps,
                kind=PoolKind(kind),
                pool_id=address,
                dex=dex,
            )
        except ValueError as exc:
            # Bad registry data (unknown kind, out-of-range fee, etc.): surface it
            # as a clear ChainError rather than a bare ValueError from the model.
            raise ChainError(
                f"could not build PoolState for pool {address!r} on {dex!r}: {exc}."
            ) from exc

    def is_pegged(self, token: str) -> float | None:
        pegged = os.getenv("PEGGED_TOKENS", "")  # e.g. "USDC:1.0,USDT:1.0"
        for item in filter(None, (s.strip() for s in pegged.split(","))):
            sym, _, ref = item.partition(":")
            if sym.upper() == token.upper():
                try:
                    return float(ref) if ref else 1.0
                except ValueError:
                    # Malformed PEGGED_TOKENS entry: ignore this one rather than
                    # crashing the request; an unparseable peg is "not pegged".
                    return None
        return None


def _load_pool_registry() -> dict:
    """Verified token -> pool-entry registry. Empty until populated (ADR-001)."""
    # Intentionally empty: no guessed addresses. Populated from a verified source
    # (live Aerodrome LpSugar enumeration) as part of the on-chain integration.
    return {}
