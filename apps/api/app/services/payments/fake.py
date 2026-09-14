"""Fake provider for development/tests: 'checkout' is a URL that confirms immediately."""

import json
import uuid

from app.services.payments.base import CheckoutSession, PaymentEvent


class FakePaymentProvider:
    name = "fake"

    def __init__(self, api_base_url: str = ""):
        self.api_base_url = api_base_url.rstrip("/")

    def create_checkout(
        self, *, booking_id, amount_cents, currency, description, success_url, cancel_url, customer_email
    ) -> CheckoutSession:
        ref = "fake_" + uuid.uuid4().hex[:16]
        url = f"{self.api_base_url}/webhooks/fake/{ref}?redirect={success_url}"
        return CheckoutSession(self.name, ref, url, {"amount_cents": amount_cents, "currency": currency})

    def parse_webhook(self, payload: bytes, signature: str | None) -> PaymentEvent | None:
        try:
            data = json.loads(payload or b"{}")
        except json.JSONDecodeError:
            return None
        ref = data.get("provider_ref")
        if not ref:
            return None
        return PaymentEvent(provider_ref=ref, succeeded=bool(data.get("succeeded", True)), raw=data)
