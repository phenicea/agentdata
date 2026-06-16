"""Pool providers and the selection factory."""

from __future__ import annotations

from typing import Protocol

from agentdata.compute.amm import PoolKind, PoolState
from agentdata.config import PoolSource, Settings


class TokenNotFound(Exception):
    """Raised when no pools are known for a requested token."""


class PoolProvider(Protocol):
    def get_pools(self, token: str) -> list[PoolState]:
        """Return all known exit pools for ``token`` (selling ``token``)."""
        ...

    def is_pegged(self, token: str) -> float | None:
        """Return the peg reference (e.g. 1.0) if ``token`` is a pegged asset."""
        ...


# --------------------------------------------------------------------------- #
# Fixture provider — deterministic, offline, used for dev + tests.
# --------------------------------------------------------------------------- #
_FIXTURES: dict[str, list[PoolState]] = {
    # A healthy, deep, diversified volatile token (e.g. a blue-chip vs USDC).
    "WETH": [
        PoolState(8_000.0, 24_000_000.0, 30, PoolKind.VOLATILE, "0xpoolA", "uniswap-v3"),
        PoolState(5_000.0, 15_000_000.0, 30, PoolKind.VOLATILE, "0xpoolB", "aerodrome-volatile"),
    ],
    # A thin, single-venue token — should score as fragile.
    "THIN": [
        PoolState(40_000.0, 38_000.0, 30, PoolKind.VOLATILE, "0xpoolC", "uniswap-v3"),
    ],
    # A pegged stablecoin pair (vs USDC), slightly off peg, for depeg signal.
    "USDX": [
        PoolState(5_000_000.0, 4_985_000.0, 4, PoolKind.STABLE, "0xpoolD", "aerodrome-stable"),
        PoolState(3_000_000.0, 2_997_000.0, 4, PoolKind.STABLE, "0xpoolE", "aerodrome-stable"),
    ],
}
_PEGGED = {"USDX": 1.0}


class FixturePoolProvider:
    def get_pools(self, token: str) -> list[PoolState]:
        key = token.upper()
        if key not in _FIXTURES:
            raise TokenNotFound(f"no fixture pools for token {token!r}")
        return list(_FIXTURES[key])

    def is_pegged(self, token: str) -> float | None:
        return _PEGGED.get(token.upper())


def get_provider(settings: Settings) -> PoolProvider:
    """Pick the provider for the current configuration."""
    if settings.pool_source is PoolSource.ONCHAIN:
        from .onchain import OnChainPoolProvider  # lazy: avoids web3 import in dev

        return OnChainPoolProvider(settings)
    return FixturePoolProvider()
