"""Tier orchestration — maps the three priced tiers to computations.

* ``QUOTE`` (0.008$) — best-route exit cost for one size.
* ``RISK``  (0.02$, default) — exit cost + fragility + (optional) depeg.
* ``DEEP``  (0.04$) — risk + multi-size exit-cost curve + max-size thresholds.

Pricing lives in :mod:`agentdata.api.pricing` (single source of truth); this
module only decides *what is computed* per tier.
"""

from __future__ import annotations

from enum import Enum

from .amm import PoolState, exit_cost, max_size_for_cost, mid_price
from .depeg import PegObservation, depeg_risk
from .fragility import fragility
from .routing import best_route

# Cost thresholds (bps) reported by the DEEP tier's "max size before cost > T".
DEEP_COST_LADDER_BPS = (10.0, 25.0, 50.0, 100.0)
# Size multipliers for the DEEP tier's exit-cost curve.
DEEP_SIZE_LADDER = (0.25, 0.5, 1.0, 2.0, 4.0)


class Tier(str, Enum):
    QUOTE = "quote"
    RISK = "risk"
    DEEP = "deep"


def _peg_observations(pools: list[PoolState]) -> list[PegObservation]:
    """Derive peg observations from pools (token priced in the out-asset)."""
    return [
        PegObservation(implied_price=mid_price(p), liquidity=p.reserve_out)
        for p in pools
    ]


def compute_tier(tier: Tier, pools: list[PoolState], size: float,
                 *, peg: float | None = None) -> dict:
    """Run the computation set for ``tier`` and return a plain dict."""
    if not pools:
        raise ValueError("no pools provided")

    route = best_route(pools, size)
    result: dict = {
        "tier": tier.value,
        "size": size,
        "exit_cost": route.best.as_dict(),
        "route": route.as_dict(),
    }
    if tier is Tier.QUOTE:
        return result

    # RISK and DEEP add fragility (+ optional depeg).
    result["fragility"] = fragility(pools, ref_size=size).as_dict()
    if peg is not None:
        result["depeg"] = depeg_risk(_peg_observations(pools), peg=peg).as_dict()

    if tier is Tier.RISK:
        return result

    # DEEP: exit-cost curve + max-size-before-threshold ladder + cross-check.
    curve = []
    for m in DEEP_SIZE_LADDER:
        s = size * m
        curve.append({"size_multiple": m, **best_route(pools, s).best.as_dict()})
    result["exit_cost_curve"] = curve

    pool = route.pool
    result["max_size_before_cost"] = [
        {"max_cost_bps": t, "max_size": max_size_for_cost(pool, t)}
        for t in DEEP_COST_LADDER_BPS
    ]
    # Cross-check: best-route cost vs the single deepest pool, to flag routing edge.
    deepest = max(pools, key=lambda p: p.reserve_in)
    result["cross_check"] = {
        "deepest_pool_id": deepest.pool_id,
        "deepest_pool_cost_bps": exit_cost(deepest, size).total_cost_bps,
        "best_route_cost_bps": route.best.total_cost_bps,
    }
    return result
