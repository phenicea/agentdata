"""Edge-case / error hardening for the on-chain provider (block C).

Covers, with NO network access (everything stubbed/monkeypatched):

* RPC down / unreachable -> clear ``ChainError`` at connect time (raised or False).
* token unknown (registry populated but token absent) -> ``TokenNotFound``.
* registry empty (feature not wired yet) -> ``NotImplementedError`` (501 path).
* empty / uninitialized pool (zero reserves) -> clear ``ChainError``, no crash.
* contract call reverts / RPC drops mid-read -> clear ``ChainError``, no crash.
* malformed getReserves() response -> clear ``ChainError``.
* bad pool address in registry -> clear ``ChainError``.
* malformed PEGGED_TOKENS entry -> treated as "not pegged", no crash.

These assert the provider degrades to actionable errors instead of leaking raw
``web3`` tracebacks or crashing the request. The provider's public exception
contract (``TokenNotFound`` / ``NotImplementedError``) is preserved so the API
layer keeps answering 404 / 501 exactly as before.
"""

from __future__ import annotations

import os
import unittest

from agentdata.chain import onchain
from agentdata.chain.onchain import ChainError, OnChainPoolProvider
from agentdata.chain.provider import TokenNotFound
from agentdata.compute.amm import PoolKind, PoolState
from agentdata.config import NetworkMode, PoolSource, Settings


def _settings(rpc_url: str = "http://localhost:0") -> Settings:
    return Settings(
        network_mode=NetworkMode.TESTNET,
        pool_source=PoolSource.ONCHAIN,
        base_rpc_url=rpc_url,
        pay_to_address="0x0000000000000000000000000000000000000000",
        facilitator_url="https://x402.org/facilitator",
        chain_id="eip155:84532",
    )


# --------------------------------------------------------------------------- #
# Fakes — a tiny web3 stand-in so we never touch the network.
# --------------------------------------------------------------------------- #
class _FakeReservesFn:
    def __init__(self, behavior):
        self._behavior = behavior

    def call(self):
        if isinstance(self._behavior, Exception):
            raise self._behavior
        return self._behavior


class _FakeContract:
    def __init__(self, behavior):
        self.functions = type("F", (), {})()
        self.functions.getReserves = lambda: _FakeReservesFn(behavior)


class _FakeEth:
    def __init__(self, behavior):
        self._behavior = behavior

    def contract(self, *, address, abi):
        return _FakeContract(self._behavior)


class _FakeW3:
    """Just enough of a web3 instance for ``_read_reserve_pool``."""

    def __init__(self, behavior, *, checksum_raises: bool = False):
        self.eth = _FakeEth(behavior)
        self._checksum_raises = checksum_raises

    def to_checksum_address(self, address):
        if self._checksum_raises:
            raise ValueError(f"not a valid address: {address!r}")
        return address


def _provider_with(behavior, *, checksum_raises: bool = False) -> OnChainPoolProvider:
    """Build a provider without running ``__init__`` (no network)."""
    prov = OnChainPoolProvider.__new__(OnChainPoolProvider)
    prov.settings = _settings()
    prov._w3 = _FakeW3(behavior, checksum_raises=checksum_raises)
    return prov


_ENTRY = dict(
    address="0xcDAC0d6c6C59727a65F871236188350531885C43",
    kind="volatile",
    fee_bps=30.0,
    dec_in=18,
    dec_out=6,
    dex="aerodrome",
    sell_is_token0=True,
)


# --------------------------------------------------------------------------- #
# Connect-time failures (RPC down / unreachable).
# --------------------------------------------------------------------------- #
class TestConnectErrors(unittest.TestCase):
    def test_missing_rpc_url_refuses(self):
        s = _settings(rpc_url="")
        with self.assertRaises(RuntimeError) as ctx:
            OnChainPoolProvider(s)
        self.assertIn("BASE_RPC_URL", str(ctx.exception))

    def test_rpc_unreachable_is_clean_chain_error(self):
        """is_connected() that *raises* (dead host) -> ChainError, not a traceback."""

        class _Boom:
            def is_connected(self):
                raise OSError("connection refused")

        self._patch_web3(_Boom())
        with self.assertRaises(ChainError) as ctx:
            OnChainPoolProvider(_settings())
        self.assertIn("could not reach Base RPC", str(ctx.exception))

    def test_rpc_returns_not_connected_is_clean_chain_error(self):
        """is_connected() returning False -> ChainError with actionable message."""

        class _Down:
            def is_connected(self):
                return False

        self._patch_web3(_Down())
        with self.assertRaises(ChainError) as ctx:
            OnChainPoolProvider(_settings())
        self.assertIn("could not connect to Base RPC", str(ctx.exception))

    def test_chain_error_is_runtimeerror(self):
        # Existing callers treat RuntimeError as a config failure; ChainError must
        # remain compatible with that.
        self.assertTrue(issubclass(ChainError, RuntimeError))

    # -- helpers ----------------------------------------------------------- #
    def _patch_web3(self, fake_w3):
        import web3 as _web3

        original = _web3.Web3
        _web3.Web3 = lambda provider: fake_w3
        self.addCleanup(lambda: setattr(_web3, "Web3", original))


# --------------------------------------------------------------------------- #
# Registry-state failures (empty registry vs unknown token).
# --------------------------------------------------------------------------- #
class TestRegistryStates(unittest.TestCase):
    def test_empty_registry_raises_not_implemented(self):
        prov = _provider_with(behavior=[1, 1, 0])
        # Default registry is intentionally empty -> "not wired yet" -> 501 path.
        with self.assertRaises(NotImplementedError) as ctx:
            prov.get_pools("WETH")
        self.assertIn("registry is empty", str(ctx.exception))

    def test_unknown_token_in_populated_registry_raises_token_not_found(self):
        prov = _provider_with(behavior=[1, 1, 0])
        self._populate({"WETH": [dict(_ENTRY)]})
        with self.assertRaises(TokenNotFound) as ctx:
            prov.get_pools("NOPE")
        self.assertIn("NOPE", str(ctx.exception))

    def test_blank_token_raises_token_not_found(self):
        prov = _provider_with(behavior=[1, 1, 0])
        with self.assertRaises(TokenNotFound):
            prov.get_pools("   ")

    def _populate(self, registry):
        original = onchain._load_pool_registry
        onchain._load_pool_registry = lambda: registry
        self.addCleanup(lambda: setattr(onchain, "_load_pool_registry", original))


# --------------------------------------------------------------------------- #
# Read-time failures (revert, RPC drop, empty pool, malformed data).
# --------------------------------------------------------------------------- #
class TestReadErrors(unittest.TestCase):
    def setUp(self):
        self._original = onchain._load_pool_registry
        onchain._load_pool_registry = lambda: {"WETH": [dict(_ENTRY)]}
        self.addCleanup(lambda: setattr(onchain, "_load_pool_registry", self._original))

    def test_contract_revert_is_clean_chain_error(self):
        prov = _provider_with(behavior=Exception("execution reverted"))
        with self.assertRaises(ChainError) as ctx:
            prov.get_pools("WETH")
        msg = str(ctx.exception)
        self.assertIn("failed to read reserves", msg)
        self.assertIn("RPC may be down", msg)

    def test_rpc_drop_mid_read_is_clean_chain_error(self):
        prov = _provider_with(behavior=ConnectionError("read timed out"))
        with self.assertRaises(ChainError):
            prov.get_pools("WETH")

    def test_empty_pool_zero_reserves_is_clean_chain_error(self):
        prov = _provider_with(behavior=[0, 0, 0])
        with self.assertRaises(ChainError) as ctx:
            prov.get_pools("WETH")
        self.assertIn("empty/uninitialized", str(ctx.exception))

    def test_one_sided_empty_pool_is_clean_chain_error(self):
        prov = _provider_with(behavior=[1000, 0, 0])
        with self.assertRaises(ChainError) as ctx:
            prov.get_pools("WETH")
        self.assertIn("empty/uninitialized", str(ctx.exception))

    def test_malformed_reserves_tuple_is_clean_chain_error(self):
        prov = _provider_with(behavior=[1, 2])  # missing timestamp
        with self.assertRaises(ChainError) as ctx:
            prov.get_pools("WETH")
        self.assertIn("unexpected getReserves()", str(ctx.exception))

    def test_bad_address_is_clean_chain_error(self):
        prov = _provider_with(behavior=[1, 1, 0], checksum_raises=True)
        with self.assertRaises(ChainError) as ctx:
            prov.get_pools("WETH")
        self.assertIn("invalid pool address", str(ctx.exception))

    def test_bad_registry_kind_is_clean_chain_error(self):
        bad = dict(_ENTRY, kind="not-a-kind")
        onchain._load_pool_registry = lambda: {"WETH": [bad]}
        prov = _provider_with(behavior=[1_000_000, 1_000_000, 0])
        with self.assertRaises(ChainError) as ctx:
            prov.get_pools("WETH")
        self.assertIn("could not build PoolState", str(ctx.exception))

    def test_healthy_pool_returns_poolstate(self):
        # Sanity: with good data and a working "RPC", we still get a valid PoolState
        # (the hardening must not break the happy path). WETH(18)/USDC(6) reserves.
        weth = 1692 * 10**18
        usdc = 3_008_000 * 10**6
        prov = _provider_with(behavior=[weth, usdc, 0])
        pools = prov.get_pools("WETH")
        self.assertEqual(len(pools), 1)
        p = pools[0]
        self.assertIsInstance(p, PoolState)
        self.assertEqual(p.kind, PoolKind.VOLATILE)
        self.assertAlmostEqual(p.reserve_in, 1692.0)
        self.assertAlmostEqual(p.reserve_out, 3_008_000.0)
        self.assertEqual(p.fee_bps, 30.0)


# --------------------------------------------------------------------------- #
# is_pegged robustness.
# --------------------------------------------------------------------------- #
class TestIsPegged(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("PEGGED_TOKENS")
        self.addCleanup(self._restore)

    def _restore(self):
        if self._saved is None:
            os.environ.pop("PEGGED_TOKENS", None)
        else:
            os.environ["PEGGED_TOKENS"] = self._saved

    def test_known_peg(self):
        os.environ["PEGGED_TOKENS"] = "USDC:1.0,USDT:1.0"
        prov = _provider_with(behavior=[1, 1, 0])
        self.assertEqual(prov.is_pegged("usdc"), 1.0)

    def test_peg_without_ref_defaults_to_one(self):
        os.environ["PEGGED_TOKENS"] = "DAI"
        prov = _provider_with(behavior=[1, 1, 0])
        self.assertEqual(prov.is_pegged("DAI"), 1.0)

    def test_unknown_token_is_not_pegged(self):
        os.environ["PEGGED_TOKENS"] = "USDC:1.0"
        prov = _provider_with(behavior=[1, 1, 0])
        self.assertIsNone(prov.is_pegged("WETH"))

    def test_malformed_peg_entry_does_not_crash(self):
        os.environ["PEGGED_TOKENS"] = "USDC:notanumber"
        prov = _provider_with(behavior=[1, 1, 0])
        self.assertIsNone(prov.is_pegged("USDC"))


if __name__ == "__main__":
    unittest.main()
