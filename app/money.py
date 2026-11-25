"""Money is stored as integer cents and exchanged with clients as decimal euros."""
from decimal import Decimal

_CENTS_PER_EURO = 100
_CENT = Decimal("0.01")


def to_cents(value: Decimal) -> int:
    """Convert euros to cents, refusing anything finer than a cent."""
    cents = value * _CENTS_PER_EURO
    if cents != cents.to_integral_value():
        raise ValueError(f"{value} has more than 2 decimal places")
    return int(cents)


def to_euros(cents: int) -> Decimal:
    """Convert cents to euros with exactly 2 decimal places."""
    return (Decimal(cents) / _CENTS_PER_EURO).quantize(_CENT)
