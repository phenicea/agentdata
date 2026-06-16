#!/usr/bin/env python3
"""E2E buyer harness — the x402 CLIENT side of the testnet flow (Phase 2).

WHAT THIS IS
------------
A standalone, founder-run script that plays the role of a paying AI agent against
our seller endpoint on **Base Sepolia testnet**: it issues a GET, receives the
``402 Payment Required``, lets the x402 SDK build + sign the EIP-3009 payment, and
replays the request automatically to unlock the JSON. It prints the final status,
the JSON body, and the settlement tx hash if the facilitator returns one.

The seller side (``agentdata.payment``) is already built; this is its counterpart
so the founder can validate ``402 -> pay -> serve`` end to end with a funded wallet.

NON-NEGOTIABLE BOUNDARIES (CLAUDE.md §0/§14, ADR-001 §4)
-------------------------------------------------------
* TESTNET ONLY. Network is pinned to Base Sepolia (``eip155:84532``). This harness
  never targets mainnet and never moves real USDC.
* PRIVATE KEY HYGIENE — CRITICAL. The buyer key is read **exclusively** from the
  ``PRIVATE_KEY`` environment variable at runtime, on the founder's machine. It is
  NEVER taken from a CLI argument, a file, a default, or a test, and it is NEVER
  printed or logged — not the key, and not (beyond the strict minimum) the address
  derived from it. The SDK signs in-process; the key stays in memory only.
* The buyer NEVER sets the amount. The amount, pay_to, nonce, and validity all
  come from OUR server's 402 (EIP-3009 typed data is built and signed entirely
  inside the SDK). If the seller emits ``$0`` (testnet default), that is what the
  SDK signs; if the facilitator rejects a zero-value authorization, the founder
  opts in to a symbolic amount **on the seller** (``TESTNET_SYMBOLIC_PRICE_USDC``)
  — not here. This client is amount-agnostic by protocol design.

USAGE (founder, local)
----------------------
    export PRIVATE_KEY=0x...            # testnet buyer key, env ONLY, never committed
    python scripts/e2e_buyer.py        # defaults to http://127.0.0.1:8000
    python scripts/e2e_buyer.py --url https://<host> --tier risk --token USDX --size 10000

The target URL may also come from ``E2E_TARGET_URL``. See ``docs/e2e-testnet.md``.

This file imports the x402 SDK (the buyer half: ``x402.client`` + the requests
HTTP client). It is a script, not part of the importable app package, so it never
affects the seller app's lazy-import discipline or the existing test suite.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

# Base Sepolia, CAIP-2 — pinned. Mirrors agentdata.config.CHAIN_ID[TESTNET].
# Hard-coded here on purpose: this harness is testnet-only and must not be
# repointable at mainnet by config drift.
TESTNET_NETWORK = "eip155:84532"

DEFAULT_URL = "http://127.0.0.1:8000"
DEFAULT_PATH = "/v1/liquidity/exit-cost"


class BuyerError(Exception):
    """A clear, user-facing failure (missing key, unexpected status, etc.)."""


def _load_private_key() -> str:
    """Read the buyer private key from ``PRIVATE_KEY`` — env ONLY.

    Returns the raw value (never logged). Raises :class:`BuyerError` with an
    actionable message if it is absent or obviously empty. The key is deliberately
    NOT accepted from any other source (CLI/file/default).
    """
    key = os.environ.get("PRIVATE_KEY")
    if not key or not key.strip():
        raise BuyerError(
            "PRIVATE_KEY is not set. Export your TESTNET buyer key in this shell "
            "before running, e.g.:\n"
            "    export PRIVATE_KEY=0x<your-base-sepolia-test-key>\n"
            "It is read from the environment only — never pass it as an argument, "
            "put it in a file, or commit it. Use a throwaway testnet wallet."
        )
    return key.strip()


def _build_target_url(base_url: str, *, tier: str, token: str, size: str, pool: str | None) -> str:
    """Compose the priced endpoint URL with query params.

    ``base_url`` may be a bare host (``http://127.0.0.1:8000``) or already include
    the path; we only append the path if it is absent so the founder can pass a
    full URL too.
    """
    from urllib.parse import urlencode, urlsplit, urlunsplit

    parts = urlsplit(base_url)
    if not parts.scheme:
        raise BuyerError(
            f"Target URL must include a scheme (http/https): got {base_url!r}. "
            f"Example: {DEFAULT_URL}"
        )
    path = parts.path if parts.path and parts.path != "/" else DEFAULT_PATH
    query: dict[str, str] = {"tier": tier, "token": token, "size": size}
    if pool:
        query["pool"] = pool
    return urlunsplit((parts.scheme, parts.netloc, path, urlencode(query), ""))


def _require_x402():
    """Import the buyer-side x402 SDK, with an actionable error if missing.

    Imports are confirmed to resolve in x402 2.13.0 (CTO spec / local
    introspection). Kept inside a function so ``--help`` works without the SDK.
    """
    try:
        from eth_account import Account
        from x402 import x402ClientSync
        from x402.http.clients import x402_requests
        from x402.mechanisms.evm import EthAccountSigner
        from x402.mechanisms.evm.exact.register import register_exact_evm_client
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise BuyerError(
            "The x402 buyer SDK is not installed (or an import path changed). "
            "Install the EVM extra in your local env:\n"
            "    pip install 'x402[evm]'\n"
            f"Underlying import error: {exc}"
        ) from exc
    return Account, x402ClientSync, x402_requests, EthAccountSigner, register_exact_evm_client


def _make_session(private_key: str):
    """Build a payment-capable ``requests.Session`` from the env private key.

    The key is turned into a ``LocalAccount`` in memory and handed to the SDK
    signer; EIP-3009 signing happens inside the SDK. Neither the key nor the
    derived address is printed here.
    """
    (
        Account,
        x402ClientSync,
        x402_requests,
        EthAccountSigner,
        register_exact_evm_client,
    ) = _require_x402()

    try:
        account = Account.from_key(private_key)
    except Exception as exc:
        # Do NOT echo the key or its prefix; the value itself is never surfaced.
        raise BuyerError(
            "PRIVATE_KEY is not a valid private key. Expected a 32-byte hex key "
            "(optionally 0x-prefixed). The value is not shown for safety."
        ) from exc

    client = x402ClientSync()
    # Pin the EVM "exact" scheme to Base Sepolia ONLY. The buyer will not sign for
    # any other network even if a 402 advertised one.
    register_exact_evm_client(client, EthAccountSigner(account), networks=TESTNET_NETWORK)
    session = x402_requests(client)
    return session


def _extract_tx_hash(response: Any) -> str | None:
    """Best-effort dig for a settlement tx hash from the unlocked response.

    The facilitator's settlement result is surfaced by the SDK in the
    ``X-PAYMENT-RESPONSE`` header (base64 JSON) on success. We decode it defensively
    and look for a transaction hash under common keys. Returns ``None`` (not an
    error) if no hash is exposed — a missing hash is not a failure of the flow.
    """
    header = None
    try:
        header = response.headers.get("X-PAYMENT-RESPONSE") or response.headers.get(
            "x-payment-response"
        )
    except Exception:
        header = None
    if not header:
        return None

    payload: Any = None
    # The header is typically base64-encoded JSON; fall back to raw JSON.
    import base64

    for decode in (lambda h: base64.b64decode(h).decode("utf-8"), lambda h: h):
        try:
            payload = json.loads(decode(header))
            break
        except Exception:
            continue
    if not isinstance(payload, dict):
        return None

    for key in ("transaction", "txHash", "tx_hash", "transactionHash", "hash"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def run(
    *,
    base_url: str,
    tier: str,
    token: str,
    size: str,
    pool: str | None,
) -> int:
    """Execute the buyer flow. Returns a process exit code (0 = success)."""
    private_key = _load_private_key()  # env only; raises a clear error if absent
    url = _build_target_url(base_url, tier=tier, token=token, size=size, pool=pool)

    # Note: the URL contains no secret; the key is never part of it.
    print(f"[buyer] target   : {url}")
    print(f"[buyer] network  : {TESTNET_NETWORK} (Base Sepolia, testnet only)")
    print("[buyer] signing  : EIP-3009 handled inside the x402 SDK; key from env, never logged")
    print("[buyer] GET -> expect 402 -> SDK pays + replays -> 200 ...")

    session = _make_session(private_key)
    # Drop the local reference; the SDK holds the in-memory account it needs.
    del private_key

    try:
        response = session.get(url, timeout=60)
    except Exception as exc:
        # Surface a readable message. Common testnet causes: server down, wrong URL,
        # insufficient test USDC / gas, or the facilitator rejecting the payment.
        message = str(exc)
        hint = _failure_hint(message)
        raise BuyerError(f"Request failed during the x402 flow: {message}{hint}") from exc

    status = response.status_code
    print(f"[buyer] status   : {status}")

    if status == 402:
        # Reaching here means the SDK could NOT complete payment (it normally pays
        # and replays automatically, yielding the final 200). Most often: no funds.
        body = _safe_body(response)
        raise BuyerError(
            "Still 402 after the payment attempt — the SDK could not settle. Likely "
            "causes:\n"
            "  - the buyer wallet has insufficient test USDC and/or Base Sepolia gas\n"
            "  - the facilitator rejected the authorization (e.g. a zero-value $0 "
            "transfer): opt in to a symbolic amount on the SELLER via "
            "TESTNET_SYMBOLIC_PRICE_USDC (see docs/e2e-testnet.md), then retry\n"
            f"Server said: {body}"
        )

    if status >= 400:
        body = _safe_body(response)
        raise BuyerError(f"Unexpected error status {status} from the server: {body}")

    if status != 200:
        body = _safe_body(response)
        raise BuyerError(f"Unexpected status {status} (wanted 200 after payment): {body}")

    # --- success: 200 after pay + replay ------------------------------------
    print("[buyer] result   : 200 OK (paid + unlocked)")
    body_json = _safe_json(response)
    if body_json is not None:
        print("[buyer] json     :")
        print(json.dumps(body_json, indent=2, sort_keys=True))
    else:
        print(f"[buyer] body     : {_safe_body(response)}")

    tx_hash = _extract_tx_hash(response)
    if tx_hash:
        print(f"[buyer] tx hash  : {tx_hash}")
        print(f"[buyer] explorer : https://sepolia.basescan.org/tx/{tx_hash}")
    else:
        print("[buyer] tx hash  : (not exposed by facilitator response — flow still OK)")

    print("[buyer] DONE     : 402 -> pay -> 200 verified on testnet")
    return 0


def _failure_hint(message: str) -> str:
    """Append a short, targeted hint for well-known failure substrings."""
    lowered = message.lower()
    if "connection" in lowered or "refused" in lowered or "max retries" in lowered:
        return (
            "\nHint: is the seller server running and reachable at this URL? "
            "Start it locally per docs/e2e-testnet.md."
        )
    if "insufficient" in lowered or "balance" in lowered or "funds" in lowered:
        return (
            "\nHint: fund the buyer wallet with Base Sepolia test USDC (Circle "
            "faucet) and test ETH for gas."
        )
    return ""


def _safe_body(response: Any) -> str:
    try:
        text = response.text
    except Exception:
        return "<unreadable body>"
    text = text.strip()
    return text if len(text) <= 2000 else text[:2000] + " ...[truncated]"


def _safe_json(response: Any) -> Any:
    try:
        return response.json()
    except Exception:
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="e2e_buyer",
        description=(
            "x402 buyer harness (TESTNET only). Reads PRIVATE_KEY from the "
            "environment (never an argument). Performs GET -> 402 -> pay (EIP-3009 "
            "via the x402 SDK) -> 200, then prints status, JSON, and tx hash."
        ),
    )
    # IMPORTANT: there is intentionally NO --private-key / --key flag. The key is
    # read from the environment exclusively (security mandate).
    parser.add_argument(
        "--url",
        default=os.environ.get("E2E_TARGET_URL", DEFAULT_URL),
        help=f"Seller base URL or full endpoint URL (default: {DEFAULT_URL}, "
        "or $E2E_TARGET_URL).",
    )
    parser.add_argument(
        "--tier",
        default=os.environ.get("E2E_TIER", "risk"),
        choices=["quote", "risk", "deep"],
        help="Pricing/compute tier to request (default: risk).",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("E2E_TOKEN", "USDX"),
        help="Token symbol/address to price an exit for (default: USDX, a fixture).",
    )
    parser.add_argument(
        "--size",
        default=os.environ.get("E2E_SIZE", "10000"),
        help="Exit size in human token units (default: 10000).",
    )
    parser.add_argument(
        "--pool",
        default=os.environ.get("E2E_POOL") or None,
        help="Optional: restrict to a single pool id.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(
            base_url=args.url,
            tier=args.tier,
            token=args.token,
            size=args.size,
            pool=args.pool,
        )
    except BuyerError as exc:
        # Clean, single-message failure (no traceback, no secret). Exit non-zero.
        print(f"[buyer] ERROR    : {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:  # pragma: no cover
        print("\n[buyer] aborted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
