"""In-memory metrics. Process-local and dependency-free.

Good enough for testnet and single-instance dev. For multi-instance / production
this is the seam to swap for a real backend (Prometheus, etc.) — same call sites.
"""

from __future__ import annotations

import threading
import time
from bisect import insort
from dataclasses import dataclass, field


def _percentile(samples: list[float], pct: float) -> float:
    if not samples:
        return 0.0
    k = (len(samples) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(samples) - 1)
    frac = k - lo
    return samples[lo] * (1 - frac) + samples[hi] * frac


@dataclass
class _TierStat:
    calls: int = 0
    errors: int = 0
    _latencies_ms: list[float] = field(default_factory=list)  # kept sorted

    def record(self, latency_ms: float, *, error: bool) -> None:
        self.calls += 1
        if error:
            self.errors += 1
        insort(self._latencies_ms, latency_ms)
        # cap memory: keep a bounded reservoir of the most relevant samples
        if len(self._latencies_ms) > 10_000:
            del self._latencies_ms[0]

    def snapshot(self) -> dict:
        return {
            "calls": self.calls,
            "errors": self.errors,
            "error_rate": (self.errors / self.calls) if self.calls else 0.0,
            "latency_p50_ms": round(_percentile(self._latencies_ms, 0.50), 3),
            "latency_p95_ms": round(_percentile(self._latencies_ms, 0.95), 3),
        }


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tiers: dict[str, _TierStat] = {}
        self._started = time.monotonic()

    def record(self, tier: str, latency_ms: float, *, error: bool) -> None:
        with self._lock:
            self._tiers.setdefault(tier, _TierStat()).record(latency_ms, error=error)

    def snapshot(self) -> dict:
        with self._lock:
            per_tier = {t: s.snapshot() for t, s in self._tiers.items()}
            total_calls = sum(s.calls for s in self._tiers.values())
            total_errors = sum(s.errors for s in self._tiers.values())
        return {
            "uptime_seconds": round(time.monotonic() - self._started, 1),
            "total_calls": total_calls,
            "total_errors": total_errors,
            "error_rate": (total_errors / total_calls) if total_calls else 0.0,
            "per_tier": per_tier,
        }


# Process-wide singleton.
METRICS = Metrics()
