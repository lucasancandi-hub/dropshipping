"""Export del catalogo in JSON, formato letto dal frontend.

Questo file è il contratto fra scraper e applicazione: la stessa forma è
descritta in TypeScript in `lib/types.ts`. Cambiare una chiave qui significa
cambiarla anche lì.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..models import Product, slugify

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


def _unique_slug(product: Product, taken: set[str]) -> str:
    """Slug stabile e non ambiguo, usato come rotta /prodotto/<slug>."""
    base = slugify(product.title) or "prodotto"
    slug = base
    suffix = 2
    while slug in taken:
        slug = f"{base}-{suffix}"
        suffix += 1
    taken.add(slug)
    return slug


def product_to_dict(product: Product, slug: str) -> dict[str, Any]:
    """Un prodotto nella forma attesa dal frontend."""
    variants = [
        {
            "id": f"{product.sku}-{slugify(variant.value) or index}",
            "label": variant.value,
            "attribute": variant.attribute,
            "price": variant.price,
            "inStock": variant.in_stock,
            "sku": variant.sku,
        }
        for index, variant in enumerate(product.variants, start=1)
    ]

    price = product.effective_price
    # Senza prezzo il frontend mostra "Prezzo da concordare in chat".
    price_on_request = price is None

    return {
        "id": product.ensure_sku(),
        "slug": slug,
        "title": product.title,
        "category": product.categories[0] if product.categories else "",
        "price": price,
        "listPrice": product.price if product.sale_price is not None else None,
        "priceOnRequest": price_on_request,
        "currency": product.currency,
        "images": product.images,
        "variantLabel": variants[0]["attribute"] if variants else None,
        "variants": variants,
        "sku": product.sku,
        "description": product.description,
        "shortDescription": product.short_description,
        "inStock": product.in_stock,
        "sourceUrl": product.url,
    }


def build_catalog(products: Iterable[Product]) -> dict[str, Any]:
    """Documento completo: metadati, categorie e prodotti."""
    taken: set[str] = set()
    items = [product_to_dict(p, _unique_slug(p, taken)) for p in products]

    categories: list[str] = []
    for item in items:
        if item["category"] and item["category"] not in categories:
            categories.append(item["category"])

    currencies = {item["currency"] for item in items if item["currency"]}

    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "currency": currencies.pop() if len(currencies) == 1 else "EUR",
        "categories": categories,
        "products": items,
    }


def export_json(products: Iterable[Product], path: str | Path) -> Path:
    """Scrive il catalogo. UTF-8 senza escape: il JSON resta leggibile."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    catalog = build_catalog(products)
    destination.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    logger.info(
        "Catalogo scritto in %s (%d prodotti, %d categorie)",
        destination,
        len(catalog["products"]),
        len(catalog["categories"]),
    )
    return destination
