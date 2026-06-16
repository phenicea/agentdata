"""Compute / normalize layer — the verifiable value-add.

Pure-Python, dependency-free, deterministic math so it can be unit-tested offline
and audited. No network access lives here; chain reads are injected from the
``chain`` layer as plain :class:`PoolState` values.
"""
