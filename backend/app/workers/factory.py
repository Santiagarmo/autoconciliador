"""Parser registry / factory: maps a bank identifier to its Strategy.

Register concrete strategies here as they are implemented. Until real
statement PDFs are available, no bank parser is registered, so
``get_parser`` raises a clear error rather than returning a wrong parser.
"""
from __future__ import annotations

from app.workers.bancolombia_parser import BancolombiaParser
from app.workers.base import BankParserStrategy

# banco (UPPERCASE) -> strategy instance. Populated once concrete parsers
# are tuned against real anonymized statements.
_REGISTRY: dict[str, BankParserStrategy] = {}


def register_parser(parser: BankParserStrategy) -> None:
    """Register a strategy under its ``banco`` key (idempotent)."""
    _REGISTRY[parser.banco.upper()] = parser


def get_parser(banco: str) -> BankParserStrategy:
    """Return the strategy for ``banco`` or raise if none is registered."""
    key = banco.upper()
    try:
        return _REGISTRY[key]
    except KeyError:
        disponibles = sorted(_REGISTRY) or ["(ninguno registrado)"]
        raise ValueError(
            f"No hay parser registrado para banco '{banco}'. "
            f"Disponibles: {disponibles}."
        ) from None


register_parser(BancolombiaParser())
