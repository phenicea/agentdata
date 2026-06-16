"""Runtime configuration — driven entirely by environment variables.

The single most important switch is ``NETWORK_MODE``:

* ``testnet`` (default) — Base Sepolia, prices forced to 0, no real USDC anywhere.
* ``mainnet`` — Base mainnet, real prices. **Never the default.** Flipping this is
  a reviewed, escalated decision (CLAUDE.md §0/§14), not a code rewrite.

Nothing here holds secrets in code. The receiving wallet / RPC keys come from env.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class NetworkMode(str, Enum):
    TESTNET = "testnet"
    MAINNET = "mainnet"


class PoolSource(str, Enum):
    FIXTURE = "fixture"   # deterministic local pools — dev/offline, no network
    ONCHAIN = "onchain"   # read Base via RPC (Aerodrome Sugar + Uniswap v3)


# CAIP-2 network ids (confirmed live: docs.x402.org network-and-token-support).
CHAIN_ID = {
    NetworkMode.TESTNET: "eip155:84532",  # Base Sepolia
    NetworkMode.MAINNET: "eip155:8453",   # Base mainnet
}

# Free testnet facilitator (confirmed live: docs.x402.org quickstart-for-sellers).
FACILITATOR_URL = {
    NetworkMode.TESTNET: "https://x402.org/facilitator",
    NetworkMode.MAINNET: "",  # set deliberately at mainnet escalation, never defaulted
}


# Env values that count as "enabled" for boolean flags (case-insensitive).
_TRUTHY = {"true", "1", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    network_mode: NetworkMode
    pool_source: PoolSource
    base_rpc_url: str
    pay_to_address: str
    facilitator_url: str
    chain_id: str
    # OPT-IN switch for the x402 payment middleware. Default False => the middleware
    # is NOT mounted (app.py gates on this), so the Phase 1 app/tests stay untouched.
    x402_enabled: bool = False
    # Explicit, separate authorization to run on MAINNET (real prices / real USDC).
    # Default False => the app refuses to start on mainnet (ADR-001 §4 guardrail).
    # Flipping this is a reviewed human escalation (CLAUDE.md §0/§14), never accidental.
    allow_mainnet: bool = False

    @property
    def is_mainnet(self) -> bool:
        return self.network_mode is NetworkMode.MAINNET


def load_settings() -> Settings:
    mode = NetworkMode(os.getenv("NETWORK_MODE", "testnet").lower())
    source = PoolSource(os.getenv("POOL_SOURCE", "fixture").lower())
    settings = Settings(
        network_mode=mode,
        pool_source=source,
        base_rpc_url=os.getenv("BASE_RPC_URL", ""),
        pay_to_address=os.getenv("PAY_TO_ADDRESS", ""),
        facilitator_url=os.getenv("FACILITATOR_URL", FACILITATOR_URL[mode]),
        chain_id=CHAIN_ID[mode],
        x402_enabled=os.getenv("X402_ENABLED", "false").lower() in _TRUTHY,
        allow_mainnet=os.getenv("ALLOW_MAINNET", "false").lower() in _TRUTHY,
    )
    # Guard on EVERY load, not just at startup: endpoints re-read settings per
    # request, so a runtime NETWORK_MODE flip must fail closed here too (closes the
    # TOCTOU gap — env changed after import can't silently serve mainnet terms).
    from agentdata.safety import guard_network  # lazy: avoids config<->safety cycle

    guard_network(settings)
    return settings
