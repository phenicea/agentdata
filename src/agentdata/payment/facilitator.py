"""Facilitator client — thin wrapper over the official x402 facilitator.

The x402 *seller* path does NOT normally call verify/settle by hand: the
``PaymentMiddlewareASGI`` (see ``payment/middleware.py``) drives the facilitator
internally. This wrapper exists for the cases where manual control is wanted
(targeted unit tests, a future non-middleware flow, debugging) and to give the
rest of the codebase a small, dict-in / dict-out seam that does not leak the
SDK's pydantic types.

Confirmed against the locally installed package (x402 2.13.0) AND the live seller
docs (they agree):

    from x402.http import FacilitatorConfig, HTTPFacilitatorClientSync
    client = HTTPFacilitatorClientSync(FacilitatorConfig(url="https://x402.org/facilitator"))
    client.verify(payload: PaymentPayload, requirements: PaymentRequirements) -> VerifyResponse
    client.settle(payload: PaymentPayload, requirements: PaymentRequirements) -> SettleResponse

We use the *sync* client variant deliberately: this wrapper is synchronous and
returns plain dicts, which keeps it trivial to mock in unit tests (no network,
no funds) and avoids forcing async on callers.

Boundaries respected (CLAUDE.md §0/§14, mandate):
* Testnet-only by default — the URL/network come from ``Settings``; no mainnet
  value is hard-coded here.
* No private key anywhere. The facilitator only sees the payment payload (built
  client-side by the payer) and the public payment requirements. The receiving
  wallet's private key never touches this code or the repo.
* The SDK import is LAZY (inside methods), never at module top-level, so the app
  keeps importing fine even if the x402 extras are not installed.
"""

from __future__ import annotations

from typing import Any


class FacilitatorClient:
    """Synchronous wrapper around the x402 ``HTTPFacilitatorClientSync``.

    Args:
        url: Facilitator base URL. On testnet this is the free Base Sepolia
            facilitator ``https://x402.org/facilitator`` (see
            ``agentdata.config.FACILITATOR_URL``). No default is baked in — the
            caller passes the env/config-derived value so mainnet can never be
            reached by accident.
    """

    def __init__(self, url: str) -> None:
        if not url:
            raise ValueError(
                "FacilitatorClient requires an explicit facilitator URL "
                "(no default — testnet value comes from Settings.facilitator_url)."
            )
        self.url = url
        # Built lazily on first use so importing this module never requires the SDK.
        self._client: Any | None = None

    # -- internal ---------------------------------------------------------------

    def _get_client(self) -> Any:
        """Lazily build the official sync facilitator client (lazy SDK import)."""
        if self._client is None:
            # LAZY import: keep x402 out of module top-level (mandate).
            from x402.http import FacilitatorConfig, HTTPFacilitatorClientSync

            self._client = HTTPFacilitatorClientSync(FacilitatorConfig(url=self.url))
        return self._client

    @staticmethod
    def _to_requirements(requirements: dict) -> Any:
        """Coerce a plain dict into the SDK's ``PaymentRequirements`` model."""
        from x402.schemas import PaymentRequirements

        return PaymentRequirements.model_validate(requirements)

    @staticmethod
    def _to_payload(payment_payload: dict) -> Any:
        """Coerce a plain dict into the SDK's ``PaymentPayload`` model."""
        from x402.schemas import PaymentPayload

        return PaymentPayload.model_validate(payment_payload)

    @staticmethod
    def _to_dict(response: Any) -> dict:
        """Normalise an SDK pydantic response into a plain dict.

        Uses the model's serialization aliases, i.e. the x402 wire shape
        (camelCase: ``isValid``, ``invalidReason``, ``success`` ...). Callers
        should read these keys, not snake_case attribute names.
        """
        if hasattr(response, "model_dump"):
            return response.model_dump(mode="json")
        if isinstance(response, dict):
            return response
        # Defensive: never raise just because the SDK changed a return shape.
        return {"raw": str(response)}

    # -- public API (dict in / dict out, per internal contract) -----------------

    def verify(self, payment_payload: dict, requirements: dict) -> dict:
        """Verify a payment proof against the 402 requirements.

        POSTs to ``{url}/verify`` (handled by the SDK client). Returns the
        facilitator's verify response as a dict (notably ``is_valid``).
        """
        client = self._get_client()
        response = client.verify(
            self._to_payload(payment_payload),
            self._to_requirements(requirements),
        )
        return self._to_dict(response)

    def settle(self, payment_payload: dict, requirements: dict) -> dict:
        """Settle a verified payment on-chain via the facilitator.

        POSTs to ``{url}/settle`` (handled by the SDK client). Returns the
        facilitator's settle response as a dict (notably ``success`` and the
        on-chain ``transaction``).
        """
        client = self._get_client()
        response = client.settle(
            self._to_payload(payment_payload),
            self._to_requirements(requirements),
        )
        return self._to_dict(response)

    def close(self) -> None:
        """Release the underlying HTTP client, if one was created."""
        if self._client is not None:
            self._client.close()
            self._client = None
