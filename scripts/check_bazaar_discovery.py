#!/usr/bin/env python3
"""Bazaar discovery checker — is our service visible in the x402 catalog?

WHAT THIS IS
------------
A standalone, founder-run, **read-only** script that queries an x402 facilitator's
discovery catalog (``GET {facilitator}/discovery/resources``) and reports whether
our service appears in it, matched by name and/or URL. It is the verification half
of the listing #2 (Bazaar) story: once the priced route declares the ``bazaar``
extension (see ``agentdata.payment.middleware``) and the service is deployed, a
facilitator that serves the discovery endpoint should list us — this script tells
the founder whether that has actually happened.

It performs NO payment, signs nothing, and needs NO key or wallet. It only does an
HTTP GET and parses JSON. It never targets mainnet funds in any way (discovery is a
read-only catalog lookup, independent of network mode).

WHY IT EXISTS / WHAT IS UNCONFIRMED (CTO spec, 2026-06-16)
---------------------------------------------------------
The default facilitator ``https://x402.org/facilitator`` does NOT currently serve
``/discovery/resources`` as JSON: live curl returns ``308 -> 404`` (an HTML page,
not a catalog). The Bazaar is described as "in early development" in the live docs.
So today this script is expected to report "endpoint not available / not supported"
against x402.org — that is a CORRECT, informative result, not a bug. It is built to
fail clearly and stay useful for when the endpoint (or a different facilitator, e.g.
CDP) actually serves the catalog. This is the open seam tracked by the CTO spec:
the *server-side* opt-in is in place, but "appears in the catalog" cannot be
demonstrated until a facilitator serves ``/discovery/resources``.

DISCOVERY MECHANICS (confirmed against x402 2.13.0)
---------------------------------------------------
The path our own SDK client would build is ``{facilitator_url}/discovery/resources``
(confirmed hard-coded in ``x402.extensions.bazaar.facilitator_client``). This script
queries that exact path so the check mirrors real discovery behavior. There is also
``/discovery/search``; we hit ``/discovery/resources`` (the catalog listing).

USAGE (founder, local)
----------------------
    python scripts/check_bazaar_discovery.py
    python scripts/check_bazaar_discovery.py --facilitator https://x402.org/facilitator
    python scripts/check_bazaar_discovery.py --name "Liquidity Exit Cost" \
        --url https://agentdata-liquidity-exit-cost.onrender.com
    python scripts/check_bazaar_discovery.py --json        # machine-readable result
    python scripts/check_bazaar_discovery.py --raw         # dump the catalog payload

Exit codes:
    0  our service was found in the catalog
    2  the catalog responded but our service is NOT (yet) listed
    3  the discovery endpoint is absent / not supported / unreachable / not JSON
    1  a usage or unexpected error

This file is a script, not part of the importable app package, so it never affects
the seller app's lazy-import discipline or the existing test suite. It uses only the
Python standard library (``urllib``) — no third-party HTTP client, no x402 SDK, no
key. That keeps it runnable anywhere with zero install and zero funds risk.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

# --- our service identity (defaults; overridable via flags) -------------------
# These mirror the discovery artifacts already in the repo so a default run checks
# for the right thing without any arguments:
#   * server.json  -> name "io.github.phenicea/agentdata-liquidity-exit-cost",
#                     title "AgentData - Executable Liquidity / Exit-Cost",
#                     remote url ".../mcp"
#   * llms.txt     -> base URL https://agentdata-liquidity-exit-cost.onrender.com
#   * payment SPEC -> bazaar service_name "Liquidity Exit Cost"
# Matching is case-insensitive substring on either field, so any of these forms
# (the short service name, the MCP name, the title) will match if the facilitator
# echoes it. The shortest, most stable token is used as the default --name.
DEFAULT_SERVICE_NAME = "Liquidity Exit Cost"
DEFAULT_SERVICE_URL = "https://agentdata-liquidity-exit-cost.onrender.com"

# Default facilitator — the free testnet one (agentdata.config FACILITATOR_URL).
# NOTE: as of 2026-06-16 this host returns 404/HTML for /discovery/resources.
DEFAULT_FACILITATOR = "https://x402.org/facilitator"

# Path the real x402 bazaar client builds (confirmed in the SDK source).
DISCOVERY_PATH = "/discovery/resources"

# Be a polite, identifiable, read-only client.
USER_AGENT = "agentdata-bazaar-discovery-check/1.0 (read-only)"
DEFAULT_TIMEOUT_SECONDS = 20


class DiscoveryError(Exception):
    """A clear, user-facing failure (bad URL, unreachable, non-JSON, etc.)."""


class EndpointUnsupported(DiscoveryError):
    """The discovery endpoint is absent / not supported / not JSON.

    Separated so the CLI can exit with the dedicated code 3: this is the EXPECTED
    outcome against x402.org today, and must be distinguishable from "responded but
    we are not listed" (code 2) and from a real error.
    """


# --- HTTP (stdlib only, read-only GET) ---------------------------------------
def _build_discovery_url(facilitator: str) -> str:
    """Compose ``{facilitator}/discovery/resources`` robustly.

    Accepts a facilitator base with or without a trailing slash, and tolerates a
    facilitator value that already includes the discovery path. Requires an
    http(s) scheme so we never silently hit something unexpected.
    """
    from urllib.parse import urlsplit, urlunsplit

    facilitator = facilitator.strip()
    parts = urlsplit(facilitator)
    if parts.scheme not in ("http", "https"):
        raise DiscoveryError(
            f"--facilitator must be an http(s) URL: got {facilitator!r}. "
            f"Example: {DEFAULT_FACILITATOR}"
        )
    path = parts.path.rstrip("/")
    if not path.endswith(DISCOVERY_PATH):
        path = path + DISCOVERY_PATH
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _fetch_catalog(url: str, *, timeout: float) -> Any:
    """GET ``url`` and parse JSON. Read-only; no auth, no body, no key.

    Raises :class:`EndpointUnsupported` for the "not a catalog" outcomes (404/410,
    a redirect to HTML, or a 200 that isn't JSON) and :class:`DiscoveryError` for
    transport-level problems. Returns the parsed JSON on success.
    """
    import urllib.error
    import urllib.request

    request = urllib.request.Request(
        url,
        method="GET",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.getcode()
            content_type = (response.headers.get("Content-Type") or "").lower()
            raw = response.read()
    except urllib.error.HTTPError as exc:
        # An HTTP status >= 400. 404/405/410/501 == "not supported here".
        if exc.code in (404, 405, 410, 501):
            raise EndpointUnsupported(
                f"The facilitator does not serve a discovery catalog at this path "
                f"(HTTP {exc.code} for {url}). The x402 Bazaar discovery endpoint is "
                f"either not implemented by this facilitator or lives elsewhere. As "
                f"of 2026-06-16 the public x402.org facilitator returns 404 here "
                f"(Bazaar is still in early development) — this is expected."
            ) from exc
        raise DiscoveryError(
            f"The facilitator returned HTTP {exc.code} for {url}. "
            f"Reason: {exc.reason!r}."
        ) from exc
    except urllib.error.URLError as exc:
        raise DiscoveryError(
            f"Could not reach the facilitator at {url}: {exc.reason}. "
            f"Check the --facilitator URL and your network connection."
        ) from exc
    except (TimeoutError, OSError) as exc:  # socket timeout, DNS, etc.
        raise DiscoveryError(
            f"Network error contacting {url}: {exc}. "
            f"The facilitator may be slow or unreachable."
        ) from exc

    text = raw.decode("utf-8", errors="replace").strip()

    # A 200 that is HTML (e.g. a Next.js page after a redirect) is NOT a catalog.
    looks_like_html = text[:1].lower() in ("<",) or "text/html" in content_type
    if looks_like_html:
        raise EndpointUnsupported(
            f"The facilitator answered {status} at {url} but returned HTML, not a "
            f"JSON catalog. This is what the public x402.org facilitator does today "
            f"(it redirects /discovery/resources to a web page). Treating discovery "
            f"as not supported here."
        )

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise EndpointUnsupported(
            f"The facilitator answered {status} at {url} but the body is not valid "
            f"JSON ({exc}). Treating discovery as not supported here. "
            f"First bytes: {text[:120]!r}"
        ) from exc


# --- catalog parsing & matching ----------------------------------------------
def _extract_resources(catalog: Any) -> list[dict[str, Any]]:
    """Pull the list of resource entries out of a discovery payload.

    The exact envelope shape is NOT fully confirmed (no live catalog to introspect
    — CTO spec seam). We therefore accept the common shapes defensively:
      * a bare JSON array of resource objects, or
      * an object with a list under one of: ``resources``, ``items``, ``data``,
        ``results``.
    Anything else yields an empty list (caller reports "not listed", not a crash).
    """
    if isinstance(catalog, list):
        return [item for item in catalog if isinstance(item, dict)]
    if isinstance(catalog, dict):
        for key in ("resources", "items", "data", "results"):
            value = catalog.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _iter_strings(value: Any) -> list[str]:
    """Flatten a value into the list of string leaves it contains.

    Used to scan a resource entry's identifying fields without assuming exactly
    where the facilitator places the name/url (it may nest them under ``resource``,
    ``metadata``, ``bazaar.info``, etc.). Bounded recursion over dict/list only.
    """
    out: list[str] = []

    def walk(node: Any, depth: int) -> None:
        if depth > 6:
            return
        if isinstance(node, str):
            out.append(node)
        elif isinstance(node, dict):
            for child in node.values():
                walk(child, depth + 1)
        elif isinstance(node, list):
            for child in node:
                walk(child, depth + 1)

    walk(value, 0)
    return out


def _entry_matches(entry: dict[str, Any], *, name: str, url: str) -> str | None:
    """Return a short reason string if ``entry`` identifies our service, else None.

    Matching is intentionally lenient and field-agnostic: we look at the preferred
    identifying fields first (name/serviceName/title and resource/url), then fall
    back to scanning all string leaves. A case-insensitive substring match on the
    name OR the url (normalized) counts as a hit. Lenient matching is safer here:
    a false "found" is obvious to the founder, while the real risk is missing a
    real listing because the field name differed from what we guessed.
    """
    needle_name = name.strip().lower()
    needle_url = _normalize_url(url)

    # Preferred, cheap checks on well-known fields.
    for key in ("name", "serviceName", "service_name", "title"):
        field = entry.get(key)
        if isinstance(field, str) and needle_name and needle_name in field.lower():
            return f"name match on field {key!r} ({field!r})"
    for key in ("resource", "url", "websiteUrl", "website_url", "endpoint"):
        field = entry.get(key)
        if isinstance(field, str) and needle_url and needle_url in _normalize_url(field):
            return f"url match on field {key!r} ({field!r})"

    # Fallback: scan every string leaf (covers nested / unexpected placements).
    for leaf in _iter_strings(entry):
        low = leaf.lower()
        if needle_name and needle_name in low:
            return f"name match (nested) on {leaf!r}"
        if needle_url and needle_url in _normalize_url(leaf):
            return f"url match (nested) on {leaf!r}"
    return None


def _normalize_url(value: str) -> str:
    """Lowercase, strip scheme and trailing slash for tolerant URL comparison.

    So ``https://host.com/x/`` and ``http://HOST.com/x`` compare equal as
    ``host.com/x``. Non-strings / empties normalize to ``""`` (never matches).
    """
    if not isinstance(value, str):
        return ""
    text = value.strip().lower()
    for prefix in ("https://", "http://"):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    return text.rstrip("/")


# --- orchestration ------------------------------------------------------------
def check(
    *,
    facilitator: str,
    name: str,
    url: str,
    timeout: float,
) -> dict[str, Any]:
    """Run the discovery check. Returns a structured result dict.

    Keys: ``found`` (bool), ``facilitator``, ``discovery_url``, ``name``, ``url``,
    ``total_resources`` (int), ``matches`` (list of {reason, entry}). Raises
    :class:`EndpointUnsupported` / :class:`DiscoveryError` on failures so the CLI
    can map them to dedicated exit codes.
    """
    discovery_url = _build_discovery_url(facilitator)
    catalog = _fetch_catalog(discovery_url, timeout=timeout)
    resources = _extract_resources(catalog)

    matches: list[dict[str, Any]] = []
    for entry in resources:
        reason = _entry_matches(entry, name=name, url=url)
        if reason:
            matches.append({"reason": reason, "entry": entry})

    return {
        "found": bool(matches),
        "facilitator": facilitator,
        "discovery_url": discovery_url,
        "name": name,
        "url": url,
        "total_resources": len(resources),
        "matches": matches,
    }


def _print_human(result: dict[str, Any]) -> None:
    print(f"[discovery] facilitator : {result['facilitator']}")
    print(f"[discovery] queried     : {result['discovery_url']}")
    print(f"[discovery] looking for  : name={result['name']!r} url={result['url']!r}")
    print(f"[discovery] catalog size : {result['total_resources']} resource(s)")
    if result["found"]:
        print(f"[discovery] RESULT      : FOUND ({len(result['matches'])} match(es))")
        for match in result["matches"]:
            print(f"[discovery]   - {match['reason']}")
        print("[discovery] DONE        : our service IS listed in the bazaar catalog")
    else:
        print("[discovery] RESULT      : NOT FOUND")
        print(
            "[discovery] note        : the catalog responded but our service is not "
            "(yet) listed. If the service was just deployed / the bazaar extension "
            "just enabled, allow time for the facilitator to index it, then retry."
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_bazaar_discovery",
        description=(
            "Read-only check: query a facilitator's x402 bazaar discovery catalog "
            "(GET {facilitator}/discovery/resources) and report whether our service "
            "appears in it. No key, no payment, no mainnet — a plain HTTP GET."
        ),
        epilog=(
            "Exit codes: 0 found, 2 catalog responded but not listed, 3 endpoint "
            "absent/unsupported/unreachable/not JSON, 1 usage/unexpected error."
        ),
    )
    parser.add_argument(
        "--facilitator",
        default=DEFAULT_FACILITATOR,
        help=f"Facilitator base URL (default: {DEFAULT_FACILITATOR}). The script "
        f"appends {DISCOVERY_PATH}.",
    )
    parser.add_argument(
        "--name",
        default=DEFAULT_SERVICE_NAME,
        help=f"Service name to match (case-insensitive substring; default: "
        f"{DEFAULT_SERVICE_NAME!r}).",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_SERVICE_URL,
        help=f"Service URL to match (scheme/trailing-slash insensitive; default: "
        f"{DEFAULT_SERVICE_URL}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"HTTP timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS}).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the structured result as JSON (machine-readable).",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Also dump the raw catalog payload fetched from the facilitator.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = check(
            facilitator=args.facilitator,
            name=args.name,
            url=args.url,
            timeout=args.timeout,
        )
    except EndpointUnsupported as exc:
        # Expected against x402.org today — a clear, non-error-looking message.
        if args.json:
            print(json.dumps({"found": False, "supported": False, "reason": str(exc)}))
        else:
            print(f"[discovery] UNSUPPORTED  : {exc}", file=sys.stderr)
        return 3
    except DiscoveryError as exc:
        if args.json:
            print(json.dumps({"found": False, "error": str(exc)}))
        else:
            print(f"[discovery] ERROR        : {exc}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:  # pragma: no cover
        print("\n[discovery] aborted", file=sys.stderr)
        return 130

    if args.raw and not args.json:
        # Re-fetch to show the payload only on explicit request (keeps default
        # output clean). Failures here are non-fatal to the already-computed result.
        try:
            payload = _fetch_catalog(result["discovery_url"], timeout=args.timeout)
            print("[discovery] raw catalog :")
            print(json.dumps(payload, indent=2, sort_keys=True))
        except DiscoveryError as exc:  # pragma: no cover - best-effort dump
            print(f"[discovery] raw catalog : <unavailable: {exc}>", file=sys.stderr)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_human(result)

    return 0 if result["found"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
