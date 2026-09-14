from functools import lru_cache

from app.core.config import get_settings
from app.services.payments.base import CheckoutSession, PaymentEvent, PaymentProvider  # noqa: F401
from app.services.payments.fake import FakePaymentProvider


@lru_cache
def get_payment_provider(api_base_url: str = "") -> PaymentProvider:
    settings = get_settings()
    if settings.payment_provider == "stripe" and settings.stripe_secret_key:
        from app.services.payments.stripe_provider import StripePaymentProvider

        return StripePaymentProvider(settings.stripe_secret_key, settings.stripe_webhook_secret)
    return FakePaymentProvider(api_base_url)
