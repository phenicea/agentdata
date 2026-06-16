"""AgentData — executable-liquidity / exit-cost & fragility intelligence endpoint.

Endpoint #1: given a token/pool and a size, compute the size-aware cost of exiting
the position (price impact + fee), the depeg risk, and an aggregated liquidity
fragility score. Sourced on-chain (Base), redistributable by design.
"""

__version__ = "0.1.0"
