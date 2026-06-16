import unittest

from agentdata.config import NetworkMode, PoolSource, Settings
from agentdata.safety import guard_network


def make(mode: NetworkMode, *, allow_mainnet: bool = False) -> Settings:
    chain = "eip155:8453" if mode is NetworkMode.MAINNET else "eip155:84532"
    return Settings(
        network_mode=mode,
        pool_source=PoolSource.FIXTURE,
        base_rpc_url="",
        pay_to_address="0xPUBLIC",
        facilitator_url="",
        chain_id=chain,
        x402_enabled=False,
        allow_mainnet=allow_mainnet,
    )


class TestNetworkGuard(unittest.TestCase):
    def test_testnet_passes(self):
        # should not raise
        guard_network(make(NetworkMode.TESTNET))

    def test_mainnet_without_authorization_refuses(self):
        with self.assertRaises(RuntimeError) as ctx:
            guard_network(make(NetworkMode.MAINNET, allow_mainnet=False))
        self.assertIn("MAINNET", str(ctx.exception))

    def test_mainnet_with_authorization_passes(self):
        # explicit human authorization -> allowed (no testnet pricing assert on mainnet)
        guard_network(make(NetworkMode.MAINNET, allow_mainnet=True))

    def test_default_settings_are_testnet_safe(self):
        from agentdata.config import load_settings

        # default env => testnet, guard must pass
        guard_network(load_settings())


if __name__ == "__main__":
    unittest.main()
