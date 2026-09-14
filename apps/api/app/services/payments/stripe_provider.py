"""Stripe Checkout implementation. Imported lazily so the SDK is optional at runtime."""

from app.services.payments.base import CheckoutSession, PaymentEvent


class StripePaymentProvider:
    name = "stripe"

    def __init__(self, secret_key: str, webhook_secret: str):
        import stripe

        stripe.api_key = secret_key
        self._stripe = stripe
        self._webhook_secret = webhook_secret

    def create_checkout(
        self, *, booking_id, amount_cents, currency, description, success_url, cancel_url, customer_email
    ) -> CheckoutSession:
        session = self._stripe.checkout.Session.create(
            mode="payment",
            customer_email=customer_email or None,
            line_items=[
                {
                    "price_data": {
                        "currency": currency.lower(),
                        "unit_amount": amount_cents,
                        "product_data": {"name": description},
                    },
                    "quantity": 1,
                }
            ],
            metadata={"booking_id": booking_id},
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return CheckoutSession(self.name, session.id, session.url or "", dict(session))

    def parse_webhook(self, payload: bytes, signature: str | None) -> PaymentEvent | None:
        try:
            event = self._stripe.Webhook.construct_event(payload, signature or "", self._webhook_secret)
        except Exception:  # invalid signature / payload
            return None
        obj = event["data"]["object"]
        if event["type"] == "checkout.session.completed":
            return PaymentEvent(obj["id"], obj.get("payment_status") == "paid", dict(obj))
        if event["type"] in ("checkout.session.expired", "checkout.session.async_payment_failed"):
            return PaymentEvent(obj["id"], False, dict(obj))
        return None
