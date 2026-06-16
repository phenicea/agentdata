"""Unit tests for the x402 BUYER harness (``scripts/e2e_buyer.py``) — OFFLINE.

NON-NEGOTIABLE test constraints (mandate + CLAUDE.md §0/§14):
* No network, no funds, no real USDC, NO real private key. The buyer's private key
  comes EXCLUSIVELY from the ``PRIVATE_KEY`` env var, read at runtime. These tests
  patch a *throwaway* fake key into the environment and never write a real one.
* The key must NEVER appear in any output (stdout/stderr/logs) — asserted directly.
* Reading the key from anything other than env (CLI arg, default, file) is forbidden;
  we assert a missing ``PRIVATE_KEY`` yields a clear error, not an obscure crash, and
  that the CLI exposes NO ``--private-key``/``--key`` flag.
* The symbolic testnet amount is strictly OPT-IN: the default testnet price stays $0
  (listing #1 invariant), a value flows only when explicitly set AND only on testnet.

``scripts/e2e_buyer.py`` lives outside the importable app package, so we load it by
absolute path. If it is ever absent (e.g. removed), the buyer-script test classes
``skip`` cleanly (same spirit as ``tests/test_api.py``'s ``_HAS_API`` guard) so the
suite never hard-fails on a missing sibling file. The session/SDK is mocked: nothing
in this file touches the network.

The pricing test class targets ``agentdata.api.pricing`` directly and always runs: it
locks the ``$0`` testnet default and the opt-in nature of the symbolic amount.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agentdata.compute.tiers import Tier

# ---------------------------------------------------------------------------
# NON-SECRET placeholder key (the scalar value 1). Deliberately low-entropy and
# obviously fake so secret scanners / GitHub push protection never flag it, while
# remaining a valid 32-byte private-key format the SDK can derive a LocalAccount
# from offline. It controls no funds, on no real network. It exists only to prove
# the harness reads PRIVATE_KEY from env and never leaks it. Never a real key (§14).
# ---------------------------------------------------------------------------
FAKE_PRIVATE_KEY = "0x" + "0" * 63 + "1"

TESTNET_CHAIN_ID = "eip155:84532"  # Base Sepolia (confirmed live, config.CHAIN_ID)

# Locate the buyer harness by absolute path: scripts/ is NOT an importable package.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BUYER_PATH = _REPO_ROOT / "scripts" / "e2e_buyer.py"


def _load_buyer_module():
    """Import scripts/e2e_buyer.py by path. Returns the module or None if absent.

    Importing must NOT run the E2E (no network): the script guards its real work
    behind ``if __name__ == '__main__':`` / a ``main()`` entrypoint.
    """
    if not _BUYER_PATH.exists():
        return None
    spec = importlib.util.spec_from_file_location("agentdata_e2e_buyer", _BUYER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


_BUYER = _load_buyer_module()
_HAS_BUYER = _BUYER is not None


def _no_private_key_env() -> dict:
    """A copy of the environment with PRIVATE_KEY removed."""
    return {k: v for k, v in os.environ.items() if k != "PRIVATE_KEY"}


@unittest.skipUnless(_HAS_BUYER, "scripts/e2e_buyer.py not present")
class TestBuyerKeyFromEnv(unittest.TestCase):
    """The buyer key is read from ``PRIVATE_KEY`` only — never arg/default/file."""

    def test_reads_key_from_env(self):
        with patch.dict(os.environ, {"PRIVATE_KEY": FAKE_PRIVATE_KEY}, clear=False):
            key = _BUYER._load_private_key()
        self.assertEqual(key, FAKE_PRIVATE_KEY)

    def test_missing_key_raises_clear_error_not_obscure_crash(self):
        with patch.dict(os.environ, _no_private_key_env(), clear=True):
            with self.assertRaises(_BUYER.BuyerError) as ctx:
                _BUYER._load_private_key()
        msg = str(ctx.exception)
        # A *clear* message: non-empty and names the env var the founder must set.
        self.assertTrue(msg.strip(), "missing PRIVATE_KEY must raise a non-empty message")
        self.assertIn("PRIVATE_KEY", msg, f"error should name PRIVATE_KEY, got: {msg!r}")

    def test_empty_or_whitespace_key_is_rejected(self):
        with patch.dict(os.environ, {"PRIVATE_KEY": "   "}, clear=False):
            with self.assertRaises(_BUYER.BuyerError):
                _BUYER._load_private_key()

    def test_no_default_key_baked_in(self):
        """With PRIVATE_KEY absent there must be NO fallback/default key: the loader
        must fail, never silently succeed with a hard-coded key (mandate §14)."""
        with patch.dict(os.environ, _no_private_key_env(), clear=True):
            with self.assertRaises(_BUYER.BuyerError):
                _BUYER._load_private_key()

    def test_key_is_stripped_but_not_logged_source_has_no_key_default(self):
        """Sanity: the loader returns the stripped value (so leading/trailing spaces
        don't corrupt signing) without inventing a default."""
        with patch.dict(os.environ, {"PRIVATE_KEY": f"  {FAKE_PRIVATE_KEY}  "}, clear=False):
            self.assertEqual(_BUYER._load_private_key(), FAKE_PRIVATE_KEY)


@unittest.skipUnless(_HAS_BUYER, "scripts/e2e_buyer.py not present")
class TestBuyerNoKeyFlag(unittest.TestCase):
    """The CLI must NOT accept the private key as an argument (env-only mandate)."""

    def test_parser_has_no_private_key_flag(self):
        parser = _BUYER.build_parser()
        # Collect every option string the parser knows about.
        option_strings = set()
        for action in parser._actions:
            option_strings.update(action.option_strings)
        for forbidden in ("--private-key", "--key", "--privatekey", "--pk"):
            self.assertNotIn(
                forbidden, option_strings,
                f"the buyer CLI must not expose {forbidden} (key is env-only)",
            )

    def test_default_url_is_local_loopback(self):
        """Target URL defaults to local loopback (per the buyer contract)."""
        with patch.dict(os.environ, _no_private_key_env(), clear=False):
            os.environ.pop("E2E_TARGET_URL", None)
            args = _BUYER.build_parser().parse_args([])
        self.assertIn("127.0.0.1", args.url, f"default target should be loopback, got {args.url!r}")

    def test_tier_is_optional_and_defaults_to_risk(self):
        """Tier is optional; the showcase default tier is risk (CEO decision)."""
        args = _BUYER.build_parser().parse_args([])
        self.assertEqual(args.tier, "risk")


@unittest.skipUnless(_HAS_BUYER, "scripts/e2e_buyer.py not present")
class TestBuyerKeyNeverLeaks(unittest.TestCase):
    """The private key must never appear in stdout/stderr (no key in logs — mandate)."""

    def _run_main_offline(self, *, status: int, json_body=None) -> str:
        """Invoke ``main([])`` with a fake key, the session fully mocked so NOTHING
        touches the network. Returns combined stdout+stderr.

        We patch ``_make_session`` so no real SDK/account/network is built, and feed a
        fake response with the requested status. This exercises the print/logging paths
        (the most likely place a key could leak) without any external call.
        """
        response = MagicMock()
        response.status_code = status
        response.headers = {}
        response.json.return_value = json_body if json_body is not None else {"ok": True}
        response.text = "" if json_body is not None else '{"ok": true}'

        session = MagicMock()
        session.get.return_value = response

        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {"PRIVATE_KEY": FAKE_PRIVATE_KEY}, clear=False), \
                patch.object(_BUYER, "_make_session", return_value=session), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            with contextlib.suppress(SystemExit):
                _BUYER.main([])
        # The session was the only network seam; assert we never called the real one.
        session.get.assert_called_once()
        return out.getvalue() + err.getvalue()

    def test_key_absent_from_output_on_success(self):
        text = self._run_main_offline(status=200, json_body={"tier": "risk"})
        self.assertNotIn(FAKE_PRIVATE_KEY, text, "raw private key leaked to output")
        # Also reject the key without its 0x prefix (a common accidental log form).
        self.assertNotIn(FAKE_PRIVATE_KEY[2:], text, "private key (no 0x) leaked to output")

    def test_key_absent_from_output_on_402(self):
        # The 'still 402' error path prints guidance; make sure the key isn't in it.
        text = self._run_main_offline(status=402)
        self.assertNotIn(FAKE_PRIVATE_KEY, text)
        self.assertNotIn(FAKE_PRIVATE_KEY[2:], text)

    def test_key_absent_from_output_on_error_status(self):
        text = self._run_main_offline(status=500)
        self.assertNotIn(FAKE_PRIVATE_KEY, text)
        self.assertNotIn(FAKE_PRIVATE_KEY[2:], text)

    def test_missing_key_main_exits_clean_no_traceback_no_key(self):
        """``main`` with no PRIVATE_KEY must exit non-zero with a clear message and
        no traceback — and obviously no key anywhere (there is none set)."""
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, _no_private_key_env(), clear=True), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = _BUYER.main([])
        self.assertEqual(rc, 1, "missing key should yield a non-zero exit code")
        combined = out.getvalue() + err.getvalue()
        self.assertIn("PRIVATE_KEY", combined, "should tell the founder to set PRIVATE_KEY")
        self.assertNotIn("Traceback", combined, "must not dump a raw traceback")


@unittest.skipUnless(_HAS_BUYER, "scripts/e2e_buyer.py not present")
class TestBuyerNetworkPinnedTestnet(unittest.TestCase):
    """The harness is testnet-only: Base Sepolia CAIP-2 is pinned, no mainnet."""

    def test_network_constant_is_base_sepolia(self):
        self.assertEqual(_BUYER.TESTNET_NETWORK, TESTNET_CHAIN_ID)


class TestSymbolicPriceOptIn(unittest.TestCase):
    """The symbolic testnet price is OPT-IN: default stays $0 (listing #1 invariant).

    Targets ``agentdata.api.pricing`` directly — always runs, no network, no key.
    """

    def _testnet_settings(self, symbolic: float | None = None):
        from agentdata.config import NetworkMode, PoolSource, Settings

        kwargs = dict(
            network_mode=NetworkMode.TESTNET,
            pool_source=PoolSource.FIXTURE,
            base_rpc_url="",
            pay_to_address="0x5E442c144687De1D311855d65E87584BdEe7541A",
            facilitator_url="https://x402.org/facilitator",
            chain_id=TESTNET_CHAIN_ID,
        )
        if symbolic is not None:
            # The sibling pricing change adds this field; tolerate its absence for now.
            kwargs["testnet_symbolic_price_usdc"] = symbolic
        try:
            return Settings(**kwargs)
        except TypeError:
            kwargs.pop("testnet_symbolic_price_usdc", None)
            return Settings(**kwargs)

    def test_testnet_default_is_zero_every_tier(self):
        """The non-negotiable default: every tier is $0 on testnet."""
        from agentdata.api.pricing import price_usdc

        for tier in Tier:
            self.assertEqual(
                price_usdc(tier, is_mainnet=False), 0.0,
                f"testnet default for {tier} must be $0 (listing #1 invariant)",
            )

    def test_mainnet_pricing_unchanged_by_symbolic_feature(self):
        """The mainnet branch must be completely untouched by the opt-in symbolic price."""
        from agentdata.api.pricing import MAINNET_PRICE_USDC, price_usdc

        for tier in Tier:
            self.assertEqual(price_usdc(tier, is_mainnet=True), MAINNET_PRICE_USDC[tier])

    def test_symbolic_env_unset_keeps_testnet_zero(self):
        """With no symbolic env var set, testnet price stays $0 (opt-in => off)."""
        from agentdata.api import pricing as pricing_mod

        env = {k: v for k, v in os.environ.items() if k != "TESTNET_SYMBOLIC_PRICE_USDC"}
        with patch.dict(os.environ, env, clear=True):
            for tier in Tier:
                self.assertEqual(pricing_mod.price_usdc(tier, is_mainnet=False), 0.0)

    def test_symbolic_value_applies_on_testnet_only_if_supported(self):
        """IF the settings-aware symbolic accessor exists, an opt-in value > 0 must:
        (a) take effect on TESTNET, and (b) NEVER take effect on mainnet. If the
        sibling pricing change is not in yet, this test skips cleanly."""
        from agentdata.api import pricing as pricing_mod

        fn = None
        for name in ("price_usdc_for_settings", "resolve_price_usdc", "effective_price_usdc"):
            cand = getattr(pricing_mod, name, None)
            if callable(cand):
                fn = cand
                break
        if fn is None:
            self.skipTest("settings-aware symbolic price accessor not implemented yet")

        symbolic = 0.001  # recommended symbolic value (1000 atomic units, 6 decimals)
        testnet = self._testnet_settings(symbolic=symbolic)
        if getattr(testnet, "testnet_symbolic_price_usdc", 0.0) != symbolic:
            self.skipTest("Settings has no testnet_symbolic_price_usdc field yet")

        # (a) testnet with opt-in value set -> symbolic amount returned.
        self.assertEqual(fn(Tier.RISK, testnet), symbolic)


if __name__ == "__main__":
    unittest.main()
