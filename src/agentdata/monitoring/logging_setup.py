"""Logging configuration — simple, env-driven, idempotent.

One function, :func:`configure_logging`, sets up the root logger with a single stream
handler and a compact line format. The level is read from the ``LOG_LEVEL`` env var
(default ``INFO``), so an operator can raise verbosity on the Render deployment without
a code change — same env-driven philosophy as :mod:`agentdata.config`.

Deliberately minimal (CLAUDE.md §0 "ne sur-construis pas"): no JSON logging, no file
rotation, no third-party logging deps. The structured per-request metrics already live
in :mod:`agentdata.monitoring.metrics` (the machine path); this is the human-readable
log path. If structured/JSON logs are ever needed, this is the single seam to swap.

The integrator calls :func:`configure_logging` once at startup (e.g. in the ASGI
entrypoint). It is safe to call more than once: it will not stack duplicate handlers.
"""

from __future__ import annotations

import logging
import os

DEFAULT_LEVEL = "INFO"
_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

# Marks the handler we installed so repeat calls reconfigure in place instead of
# appending another handler (which would duplicate every log line).
_HANDLER_TAG = "agentdata.logging_setup"


def resolve_level(raw: str | None = None) -> int:
    """Resolve a logging level int from a string (env value), tolerant of junk.

    Accepts standard names (``DEBUG``/``INFO``/``WARNING``/``ERROR``/``CRITICAL``,
    case-insensitive) and numeric strings (e.g. ``"10"``). Anything unrecognised
    falls back to :data:`DEFAULT_LEVEL` rather than raising — a bad ``LOG_LEVEL``
    must not crash startup.
    """
    if raw is None:
        raw = os.getenv("LOG_LEVEL", DEFAULT_LEVEL)
    candidate = raw.strip()
    if candidate.isdigit():
        return int(candidate)
    level = logging.getLevelName(candidate.upper())
    # getLevelName returns an int for known names, else the string "Level X".
    if isinstance(level, int):
        return level
    return logging.getLevelName(DEFAULT_LEVEL)  # -> INFO's int


def configure_logging(level: int | str | None = None) -> logging.Logger:
    """Configure the root logger once; return it.

    * ``level`` may be an int, a level name, or ``None`` (then read ``LOG_LEVEL`` env,
      default ``INFO``).
    * Idempotent: calling it again updates the level and reuses our single handler
      rather than adding duplicates.
    """
    if isinstance(level, int):
        resolved = level
    else:
        resolved = resolve_level(level)

    root = logging.getLogger()
    root.setLevel(resolved)

    handler = _find_our_handler(root)
    if handler is None:
        handler = logging.StreamHandler()
        handler.set_name(_HANDLER_TAG)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
        root.addHandler(handler)
    handler.setLevel(resolved)

    return root


def _find_our_handler(root: logging.Logger) -> logging.Handler | None:
    """Return the handler this module previously installed, if any."""
    for h in root.handlers:
        if getattr(h, "name", None) == _HANDLER_TAG:
            return h
    return None


def get_logger(name: str) -> logging.Logger:
    """Convenience accessor for a named child logger (e.g. ``get_logger(__name__)``)."""
    return logging.getLogger(name)
