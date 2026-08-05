"""Modelli dati normalizzati del catalogo.

Sono l'unico "contratto" fra il livello di parsing e i livelli di export
(CSV WooCommerce / REST API). Chi scrive un nuovo parser deve produrre
`Product`; chi scrive un nuovo exporter consuma `Product`.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any


def slugify(value: str, max_length: int = 60) -> str:
    """Slug ASCII, minuscolo, usato per SKU e nomi file."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()
    return slug[:max_length].strip("-")


@dataclass
class Variant:
    """Una singola combinazione acquistabile (es. Taglia = M)."""

    attribute: str
    value: str
    sku: str | None = None
    price: float | None = None
    in_stock: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "attribute": self.attribute,
            "value": self.value,
            "sku": self.sku,
            "price": self.price,
            "in_stock": self.in_stock,
        }


@dataclass
class Product:
    """Prodotto normalizzato, indipendente dalla sorgente."""

    title: str
    url: str = ""
    price: float | None = None
    sale_price: float | None = None
    currency: str = "EUR"
    categories: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    variants: list[Variant] = field(default_factory=list)
    sku: str | None = None
    description: str = ""
    short_description: str = ""
    in_stock: bool = True
    source: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Derivati
    # ------------------------------------------------------------------ #
    def ensure_sku(self, prefix: str = "SKU") -> str:
        """SKU deterministico: stessa pagina -> stesso SKU (import idempotente)."""
        if self.sku:
            return self.sku
        seed = self.url or self.title
        digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8].upper()
        self.sku = f"{prefix}-{slugify(self.title, 32).upper() or 'ITEM'}-{digest}"
        return self.sku

    @property
    def is_variable(self) -> bool:
        return len(self.variants) > 0

    @property
    def attributes(self) -> dict[str, list[str]]:
        """{'Taglia': ['S', 'M', 'L']} preservando l'ordine di comparsa."""
        grouped: dict[str, list[str]] = {}
        for variant in self.variants:
            values = grouped.setdefault(variant.attribute, [])
            if variant.value not in values:
                values.append(variant.value)
        return grouped

    @property
    def effective_price(self) -> float | None:
        return self.sale_price if self.sale_price is not None else self.price

    def is_valid(self) -> bool:
        """Scarta le card vuote/placeholder tipiche dei caroselli."""
        return bool(self.title.strip()) and (self.price is not None or self.is_variable)

    def as_dict(self) -> dict[str, Any]:
        return {
            "sku": self.sku,
            "title": self.title,
            "url": self.url,
            "price": self.price,
            "sale_price": self.sale_price,
            "currency": self.currency,
            "categories": self.categories,
            "images": self.images,
            "variants": [v.as_dict() for v in self.variants],
            "description": self.description,
            "short_description": self.short_description,
            "in_stock": self.in_stock,
            "source": self.source,
            "extra": self.extra,
        }
