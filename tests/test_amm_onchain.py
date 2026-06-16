"""AMM math vs the REAL deployed pools' own getAmountOut — network-gated.

This is the *independent* accuracy proof (our selling point): we call the deployed
Aerodrome ``Pool.getAmountOut`` on Base mainnet (read-only eth_call) and assert our
``amm.py`` reproduces it. The oracle is the pool contract's own swap math — NOT a
re-implementation of our formula — so a match really proves correctness (reserve
orientation, decimals, fee, curve), for both curves we implement:

* VOLATILE (constant product) and STABLE (Solidly x^3y + xy^3).

Skips cleanly when offline / no RPC, so the default suite stays deterministic.
Run the standalone proof with: ``python scripts/verify_amm_onchain.py``.

Note: Uniswap v3 / concentrated liquidity is intentionally NOT covered — amm.py
does not implement it (v3 would be sourced from QuoterV2, a planned extension), so
there is no v3 math of ours to verify here.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

try:
    import verify_amm_onchain as v

    _w3, _RPC = v.connect()
    _ONLINE = _w3 is not None
except Exception:  # noqa: BLE001 - any import/connect failure => skip (offline)
    _ONLINE = False
    _w3 = None


@unittest.skipUnless(_ONLINE, "no Base RPC reachable / web3 missing — on-chain proof skipped")
class TestAmmMatchesOnChainOracle(unittest.TestCase):
    """amm.py must match each deployed pool's getAmountOut within tolerance."""

    @classmethod
    def setUpClass(cls):
        cls.rows = v.verify(_w3)

    def test_rows_were_collected(self):
        # Guard against a vacuous pass: we must have actually compared something,
        # covering BOTH curve kinds.
        self.assertTrue(self.rows, "no on-chain comparison rows collected")
        labels = {r["label"] for r in self.rows}
        self.assertTrue(any("volatile" in l for l in labels), "volatile pool not checked")
        self.assertTrue(any("stable" in l for l in labels), "stable pool not checked")

    def test_amm_matches_onchain_within_tolerance(self):
        for r in self.rows:
            with self.subTest(pool=r["label"], size=r["size"]):
                self.assertLessEqual(
                    r["diff_bps"], v.TOLERANCE_BPS,
                    f"{r['label']} size={r['size']}: amm.py={r['ours']} vs "
                    f"onchain={r['onchain']} -> {r['diff_bps']:.4f} bps "
                    f"(> {v.TOLERANCE_BPS} bps tolerance)",
                )


if __name__ == "__main__":
    unittest.main()
