"""Stable, documented response schema (additive-only changes going forward).

A clear, machine-readable schema is part of how an agent decides to pick us
(CLAUDE.md §10). Fields are typed and described; new fields may be added but
existing ones keep their meaning and name.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExitCostModel(BaseModel):
    size: float = Field(..., description="Sell size in human token units.")
    amount_out: float = Field(..., description="Output-token units received (fee incl.).")
    mid_price: float = Field(..., description="Marginal price (out per 1 in) at size 0.")
    exec_price: float = Field(..., description="Realized price = amount_out / size.")
    total_cost_bps: float = Field(..., description="Loss vs mid (fee + slippage), bps.")
    price_impact_bps: float = Field(..., description="Slippage only (fee excluded), bps.")
    fee_bps: float = Field(..., description="Pool fee component, bps.")


class RouteModel(BaseModel):
    best: ExitCostModel
    pool_id: str
    dex: str
    routed_split: bool = Field(..., description="True if cost is split across venues.")
    venues_considered: int


class FragilityModel(BaseModel):
    score: float = Field(..., description="0..100, higher = more fragile.")
    depth_score: float
    concentration_score: float
    convexity_score: float
    total_exit_liquidity: float
    venues: int


class DepegModel(BaseModel):
    deviation_bps: float
    dispersion_bps: float
    weighted_price: float
    total_liquidity: float
    score: float = Field(..., description="0..100, higher = more depeg risk.")


class CurvePoint(ExitCostModel):
    size_multiple: float


class MaxSizeEntry(BaseModel):
    max_cost_bps: float
    max_size: float


class CrossCheck(BaseModel):
    deepest_pool_id: str
    deepest_pool_cost_bps: float
    best_route_cost_bps: float


class ExitCostResponse(BaseModel):
    tier: str
    network: str = Field(..., description="testnet | mainnet")
    token: str
    size: float
    exit_cost: ExitCostModel
    route: RouteModel
    fragility: FragilityModel | None = None
    depeg: DepegModel | None = None
    exit_cost_curve: list[CurvePoint] | None = None
    max_size_before_cost: list[MaxSizeEntry] | None = None
    cross_check: CrossCheck | None = None
