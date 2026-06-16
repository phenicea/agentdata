"""Liquidity fragility — how easily a token's exit liquidity breaks down.

Aggregates across all known pools for the token. A *fragile* token is one where
liquidity is shallow, concentrated in a single venue, and/or where exit cost
explodes as size grows. Deterministic, versioned, unit-tested.

Components (each normalized 0..100, higher == more fragile):

* ``depth``        — total exit-side reserves measured in multiples of the
                     reference size; few multiples == fragile.
* ``concentration``— Herfindahl-Hirschman index of liquidity across venues;
                     one dominant pool == fragile.
* ``convexity``    — how fast best-route cost grows from ref size to 2x ref;
                     steep growth == fragile.
"""

from __future__ import annotations

from dataclasses import dataclass

from .amm import PoolState
from .routing import best_route

# Versioned: any change to the score is a logged, deliberate decision.
FRAGILITY_WEIGHTS_V1 = {
    "depth": 0.45,
    "concentration": 0.25,
    "convexity": 0.30,
}
# Depth at/above this many reference-sizes of total liquidity -> depth risk 0.
DEPTH_SATURATION_MULTIPLE = 50.0


@dataclass(frozen=True)
class Fragility:
    score: float
    depth_score: float
    concentration_score: float
    convexity_score: float
    total_exit_liquidity: float
    venues: int

    def as_dict(self) -> dict:
        return {
            "score": self.score,
            "depth_score": self.depth_score,
            "concentration_score": self.concentration_score,
            "convexity_score": self.convexity_score,
            "total_exit_liquidity": self.total_exit_liquidity,
            "venues": self.venues,
        }


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def fragility(pools: list[PoolState], ref_size: float,
              *, weights: dict | None = None) -> Fragility:
    if not pools:
        raise ValueError("no pools provided")
    if ref_size <= 0:
        raise ValueError("ref_size must be > 0")
    w = weights or FRAGILITY_WEIGHTS_V1

    # Depth: total reserves of the token being sold, across venues.
    total_liq = sum(p.reserve_in for p in pools)
    multiples = total_liq / ref_size
    depth_score = _clamp((1.0 - min(multiples, DEPTH_SATURATION_MULTIPLE)
                          / DEPTH_SATURATION_MULTIPLE) * 100.0)

    # Concentration: HHI of liquidity shares (1/n .. 1.0) rescaled to 0..100.
    shares = [p.reserve_in / total_liq for p in pools]
    hhi = sum(s * s for s in shares)            # in [1/n, 1]
    n = len(pools)
    floor = 1.0 / n
    concentration_score = _clamp((hhi - floor) / (1.0 - floor) * 100.0) if n > 1 else 100.0

    # Convexity: best-route cost at 2x ref vs at ref. ratio 1 -> 0, ratio>=3 -> 100.
    c1 = best_route(pools, ref_size).best.total_cost_bps
    c2 = best_route(pools, 2.0 * ref_size).best.total_cost_bps
    ratio = (c2 / c1) if c1 > 0 else 1.0
    convexity_score = _clamp((ratio - 1.0) / (3.0 - 1.0) * 100.0)

    score = _clamp(
        w["depth"] * depth_score
        + w["concentration"] * concentration_score
        + w["convexity"] * convexity_score
    )
    return Fragility(
        score=score,
        depth_score=depth_score,
        concentration_score=concentration_score,
        convexity_score=convexity_score,
        total_exit_liquidity=total_liq,
        venues=n,
    )
