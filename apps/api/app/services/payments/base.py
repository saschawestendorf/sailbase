"""Payment provider abstraction. Providers only know about amounts and references."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CheckoutSession:
    provider: str
    provider_ref: str
    checkout_url: str
    raw: dict


@dataclass(frozen=True)
class PaymentEvent:
    """Normalised webhook event."""

    provider_ref: str
    succeeded: bool
    raw: dict


class PaymentProvider(Protocol):
    name: str

    def create_checkout(
        self,
        *,
        booking_id: str,
        amount_cents: int,
        currency: str,
        description: str,
        success_url: str,
        cancel_url: str,
        customer_email: str,
    ) -> CheckoutSession: ...

    def parse_webhook(self, payload: bytes, signature: str | None) -> PaymentEvent | None: ...
