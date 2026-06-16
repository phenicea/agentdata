"""AMM math — pure, deterministic, dependency-free.

Two pool families are modelled, matching what we read on Base:

* ``VOLATILE`` — constant-product ``x * y = k`` (Uniswap v2 / Aerodrome volatile).
* ``STABLE``   — the Solidly/Aerodrome stable invariant ``x^3*y + x*y^3 = k``.

Conventions
-----------
All amounts here are **float, in human (decimal-normalized) units** of each token,
e.g. 1.0 == one whole token. On-chain integer/wei math is the chain layer's job;
this module is the auditable model. Results are reported relative to the pool's
marginal (mid) price, so unit scaling cancels out.

For a sell of ``size`` units of the *input* token we report:

* ``amount_out``      — units of the output token actually received (fee included).
* ``mid_price``       — marginal price (output per 1 input) ignoring fee, at size 0.
* ``exec_price``      — realized price = amount_out / size.
* ``total_cost_bps``  — what the seller loses vs mid (fee + slippage), in bps.
* ``price_impact_bps``— slippage only (same trade with fee = 0).
* ``fee_bps``         — the pool fee component, in bps.

These are the primitives the exit-cost / fragility tiers are built on.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

BPS = 10_000.0


class PoolKind(str, Enum):
    VOLATILE = "volatile"  # constant product x*y=k
    STABLE = "stable"      # solidly stable x^3y + xy^3 = k


@dataclass(frozen=True)
class PoolState:
    """A snapshot of a single pool, normalized so that we sell ``token_in``.

    ``reserve_in``  : reserve of the token being sold (human units).
    ``reserve_out`` : reserve of the token received (human units).
    ``fee_bps``     : pool swap fee in basis points (e.g. 30 == 0.30%).
    ``kind``        : VOLATILE or STABLE.
    ``pool_id``     : opaque address/identifier (for reporting only).
    ``dex``         : source dex label (for reporting only).
    """

    reserve_in: float
    reserve_out: float
    fee_bps: float
    kind: PoolKind
    pool_id: str = ""
    dex: str = ""

    def __post_init__(self) -> None:
        if self.reserve_in <= 0 or self.reserve_out <= 0:
            raise ValueError("reserves must be positive")
        if self.fee_bps < 0 or self.fee_bps >= BPS:
            raise ValueError("fee_bps must be in [0, 10000)")


# --------------------------------------------------------------------------- #
# Marginal (mid) price
# --------------------------------------------------------------------------- #
def mid_price(pool: PoolState) -> float:
    """Marginal price of ``token_in`` in units of ``token_out`` (fee-free)."""
    x, y = pool.reserve_in, pool.reserve_out
    if pool.kind is PoolKind.VOLATILE:
        # k = x*y -> dk/dx = y, dk/dy = x -> price = y/x
        return y / x
    # STABLE: k = x^3 y + x y^3 -> price = (3x^2 y + y^3) / (x^3 + 3 x y^2)
    return (3 * x * x * y + y**3) / (x**3 + 3 * x * y * y)


# --------------------------------------------------------------------------- #
# Stable-curve helpers (Solidly invariant)
# --------------------------------------------------------------------------- #
def _stable_k(x: float, y: float) -> float:
    return x**3 * y + x * y**3


def _stable_get_y(x_new: float, k: float, y_guess: float) -> float:
    """Solve ``_stable_k(x_new, y) == k`` for y via Newton's method."""
    y = y_guess
    for _ in range(255):
        f = _stable_k(x_new, y)            # current invariant value
        d = 3 * x_new * y * y + x_new**3   # d f / dy = 3 x y^2 + x^3
        if d == 0:
            break
        if f < k:
            dy = (k - f) / d
            y += dy
        else:
            dy = (f - k) / d
            y -= dy
        if abs(dy) <= y * 1e-15 or abs(dy) <= 1e-18:
            break
    return y


# --------------------------------------------------------------------------- #
# Amount out for a given sell size
# --------------------------------------------------------------------------- #
def amount_out(pool: PoolState, size: float, *, apply_fee: bool = True) -> float:
    """Units of ``token_out`` received for selling ``size`` units of ``token_in``."""
    if size < 0:
        raise ValueError("size must be >= 0")
    if size == 0:
        return 0.0
    x, y = pool.reserve_in, pool.reserve_out
    fee = pool.fee_bps / BPS if apply_fee else 0.0
    dx = size * (1.0 - fee)

    if pool.kind is PoolKind.VOLATILE:
        # dy = y * dx / (x + dx)
        return (y * dx) / (x + dx)

    # STABLE
    k = _stable_k(x, y)
    x_new = x + dx
    y_new = _stable_get_y(x_new, k, y)
    out = y - y_new
    return out if out > 0 else 0.0


# --------------------------------------------------------------------------- #
# Exit cost
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ExitCost:
    size: float
    amount_out: float
    mid_price: float
    exec_price: float
    total_cost_bps: float
    price_impact_bps: float
    fee_bps: float

    def as_dict(self) -> dict:
        return {
            "size": self.size,
            "amount_out": self.amount_out,
            "mid_price": self.mid_price,
            "exec_price": self.exec_price,
            "total_cost_bps": self.total_cost_bps,
            "price_impact_bps": self.price_impact_bps,
            "fee_bps": self.fee_bps,
        }


def exit_cost(pool: PoolState, size: float) -> ExitCost:
    """Size-aware cost of selling ``size`` of ``token_in`` into ``pool``."""
    if size <= 0:
        raise ValueError("size must be > 0")
    mid = mid_price(pool)
    out = amount_out(pool, size, apply_fee=True)
    out_nofee = amount_out(pool, size, apply_fee=False)

    exec_price = out / size
    # value the seller "should" get at mid, vs what they actually get
    total_cost_bps = (1.0 - (exec_price / mid)) * BPS
    impact_only = (1.0 - ((out_nofee / size) / mid)) * BPS
    return ExitCost(
        size=size,
        amount_out=out,
        mid_price=mid,
        exec_price=exec_price,
        total_cost_bps=total_cost_bps,
        price_impact_bps=impact_only,
        fee_bps=pool.fee_bps,
    )


def max_size_for_cost(pool: PoolState, max_cost_bps: float,
                      *, hi_hint: float | None = None) -> float:
    """Largest sell size whose ``total_cost_bps`` stays <= ``max_cost_bps``.

    Cost is monotonically increasing in size, so we bisect. Returns 0.0 if even an
    infinitesimal trade already exceeds the threshold (only possible when the fee
    alone is above the threshold).
    """
    if max_cost_bps <= 0:
        raise ValueError("max_cost_bps must be > 0")
    # fee is the floor cost for any positive size
    if pool.fee_bps >= max_cost_bps:
        return 0.0

    lo = 0.0
    hi = hi_hint if hi_hint is not None else pool.reserve_in
    # grow hi until it exceeds the threshold (bounded by a large multiple)
    for _ in range(64):
        if exit_cost(pool, hi).total_cost_bps >= max_cost_bps:
            break
        hi *= 2.0
    else:
        return hi  # threshold never reached within range; return best found

    for _ in range(100):
        mid_size = (lo + hi) / 2.0
        if mid_size <= 0:
            break
        if exit_cost(pool, mid_size).total_cost_bps <= max_cost_bps:
            lo = mid_size
        else:
            hi = mid_size
        if (hi - lo) <= lo * 1e-9:
            break
    return lo
