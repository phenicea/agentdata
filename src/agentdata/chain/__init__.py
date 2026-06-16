"""Chain layer — turns on-chain Base state into :class:`PoolState` values.

Two providers implement the same interface:

* :class:`FixturePoolProvider` — deterministic in-memory pools. Default for local
  dev and tests; needs no network and exposes no secrets.
* :class:`OnChainPoolProvider` — reads Base via RPC (Aerodrome ``LpSugar`` +
  Uniswap v3 ``QuoterV2``). Lazy-imports ``web3`` so the rest of the app runs
  without it installed. Contract addresses must be verified live before use.
"""

from .provider import (
    FixturePoolProvider,
    PoolProvider,
    TokenNotFound,
    get_provider,
)

__all__ = ["PoolProvider", "FixturePoolProvider", "TokenNotFound", "get_provider"]
