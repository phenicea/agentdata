"""Depeg risk — how far an asset's on-chain price sits from its expected peg,
and how well-defended that peg is.

This is *information about* a pegged asset's market state (allowed), not a bet or
a prediction. Deterministic and unit-tested.

Inputs are per-pool implied prices of the asset vs its peg reference plus the
liquidity backing each quote. We report:

* ``deviation_bps``  — liquidity-weighted |price - peg| / peg, in bps.
* ``dispersion_bps`` — spread of implied prices across venues (max - min), in bps.
* ``score``          — 0..100, higher = more depeg risk.
"""

from __future__ import annotations

from dataclasses import dataclass

BPS = 10_000.0

# Versioned weights so a score change is always a deliberate, logged decision.
DEPEG_WEIGHTS_V1 = {
    "deviation": 0.6,    # how far off peg right now
    "dispersion": 0.25,  # disagreement between venues (fragmentation/instability)
    "thinness": 0.15,    # how little liquidity defends the peg
}
# Reference liquidity (in peg units) at/above which "thinness" risk -> 0.
DEPEG_THINNESS_FLOOR = 1_000_000.0


@dataclass(frozen=True)
class PegObservation:
    implied_price: float   # asset price in peg units (1.0 == perfectly pegged)
    liquidity: float       # liquidity backing this quote, in peg units


@dataclass(frozen=True)
class DepegRisk:
    deviation_bps: float
    dispersion_bps: float
    weighted_price: float
    total_liquidity: float
    score: float

    def as_dict(self) -> dict:
        return {
            "deviation_bps": self.deviation_bps,
            "dispersion_bps": self.dispersion_bps,
            "weighted_price": self.weighted_price,
            "total_liquidity": self.total_liquidity,
            "score": self.score,
        }


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def depeg_risk(observations: list[PegObservation], *, peg: float = 1.0,
               weights: dict | None = None) -> DepegRisk:
    if not observations:
        raise ValueError("no observations provided")
    if peg <= 0:
        raise ValueError("peg must be > 0")
    w = weights or DEPEG_WEIGHTS_V1

    total_liq = sum(o.liquidity for o in observations)
    if total_liq <= 0:
        raise ValueError("total liquidity must be > 0")

    weighted_price = sum(o.implied_price * o.liquidity for o in observations) / total_liq
    deviation_bps = abs(weighted_price - peg) / peg * BPS

    prices = [o.implied_price for o in observations]
    dispersion_bps = (max(prices) - min(prices)) / peg * BPS

    # Normalize each component to 0..100.
    # deviation: 100 bps (1%) off peg -> 100 risk points (clamped).
    dev_score = _clamp(deviation_bps)
    # dispersion: 100 bps spread across venues -> 100 risk points.
    disp_score = _clamp(dispersion_bps)
    # thinness: less liquidity than the floor -> proportional risk.
    thin_score = _clamp((1.0 - min(total_liq, DEPEG_THINNESS_FLOOR) / DEPEG_THINNESS_FLOOR) * 100.0)

    score = _clamp(
        w["deviation"] * dev_score
        + w["dispersion"] * disp_score
        + w["thinness"] * thin_score
    )
    return DepegRisk(
        deviation_bps=deviation_bps,
        dispersion_bps=dispersion_bps,
        weighted_price=weighted_price,
        total_liquidity=total_liq,
        score=score,
    )
