"""Monitoring — uptime, latency (p50/p95), error rate, calls per tier.

These are the metrics that (a) gate the listing decisions (3-day / 7-day uptime in
the CEO plan) and (b) become the objective base of the reputation router later
(CLAUDE.md §13). Tracked from day one, even on testnet.
"""

from .metrics import METRICS, Metrics

__all__ = ["METRICS", "Metrics"]
