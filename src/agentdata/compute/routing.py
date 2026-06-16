"""Routing across venues — pick the cheapest pool to exit a given size.

MVP scope: we evaluate each pool independently and select the single best venue
for the requested size (lowest total cost). True split routing across pools is a
later enhancement and is flagged as such in the output (``routed_split=False``).
"""

from __future__ import annotations

from dataclasses import dataclass

from .amm import ExitCost, PoolState, exit_cost


@dataclass(frozen=True)
class BestRoute:
    best: ExitCost
    pool: PoolState
    per_pool: list[ExitCost]
    routed_split: bool = False

    def as_dict(self) -> dict:
        return {
            "best": self.best.as_dict(),
            "pool_id": self.pool.pool_id,
            "dex": self.pool.dex,
            "routed_split": self.routed_split,
            "venues_considered": len(self.per_pool),
        }


def best_route(pools: list[PoolState], size: float) -> BestRoute:
    """Return the single cheapest pool to exit ``size`` of ``token_in``."""
    if not pools:
        raise ValueError("no pools provided")
    per_pool = [exit_cost(p, size) for p in pools]
    # lowest total cost == best execution for the seller
    idx = min(range(len(per_pool)), key=lambda i: per_pool[i].total_cost_bps)
    return BestRoute(best=per_pool[idx], pool=pools[idx], per_pool=per_pool)
