"""x402 payment layer (Phase 2) — OPT-IN, testnet-first.

This package wires the x402 seller flow on top of the Phase 1 endpoint. It is
inert unless explicitly enabled (env ``X402_ENABLED=true``, wired in app.py by the
integrator): when disabled nothing here touches the FastAPI app, so the Phase 1
test suite is untouched.

Public surface (assembled across the package's modules):

* :func:`payment_requirements` — build the x402 402 "payment requirements" for a
  tier (testnet => $0).
* ``FacilitatorClient`` — thin wrapper over the facilitator (added by its module).
* ``build_x402_middleware`` — opt-in middleware builder (added by its module).

Boundaries (non-negotiable): testnet by default, no mainnet value active without an
explicit reviewed flip; only the public ``PAY_TO_ADDRESS`` ever lives in env — the
wallet private key never appears in code or repo.
"""

from __future__ import annotations

# These three modules keep the x402 SDK import LAZY (inside functions/methods), so
# importing the package here never requires x402 to be installed — the Phase 1 app
# and tests load fine with payments off.
from .facilitator import FacilitatorClient
from .middleware import build_x402_middleware
from .pricing_402 import payment_requirements

__all__ = [
    "FacilitatorClient",
    "build_x402_middleware",
    "payment_requirements",
]
