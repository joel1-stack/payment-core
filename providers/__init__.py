"""
Provider registry. Factory to get the right provider by name.
"""
from decimal import Decimal
from .base import PaymentProvider, CrossDeviceAuthRequest, CrossDeviceAuthResponse
from .mock_provider import MockProvider
from .mpesa_provider import MpesaProvider
from .stripe_provider import StripeProvider


_registry: dict[str, type[PaymentProvider]] = {}


def register_provider(provider_cls: type[PaymentProvider]):
    _registry[provider_cls.name] = provider_cls


def get_provider(name: str, **kwargs) -> PaymentProvider:
    cls = _registry.get(name)
    if not cls:
        raise ValueError(f"Unknown provider: {name}. Available: {list(_registry.keys())}")
    return cls(**kwargs)


def list_providers() -> list[str]:
    return list(_registry.keys())


# Auto-register on import
register_provider(MockProvider)
register_provider(MpesaProvider)
register_provider(StripeProvider)
