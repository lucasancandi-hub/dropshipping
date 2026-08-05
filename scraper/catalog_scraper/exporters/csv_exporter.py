"""Export nel formato CSV nativo di WooCommerce (Prodotti > Importa).

I prodotti con varianti generano una riga `variable` (padre) seguita da una
riga `variation` per ogni taglia, collegata al padre tramite `Parent` = `id:SKU`.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Iterable, Sequence

from ..models import Product

logger = logging.getLogger(__name__)

# Intestazioni riconosciute nativamente dall'importatore WooCommerce
COLUMNS: Sequence[str] = (
    "ID",
    "Type",
    "SKU",
    "Name",
    "Published",
    "Visibility in catalog",
    "Short description",
    "Description",
    "In stock?",
    "Regular price",
    "Sale price",
    "Categories",
    "Images",
    "Parent",
    "Position",
    "Attribute 1 name",
    "Attribute 1 value(s)",
    "Attribute 1 visible",
    "Attribute 1 global",
    "External URL",
)


def _row(**overrides: object) -> dict[str, object]:
    row = {column: "" for column in COLUMNS}
    row.update(overrides)
    return row


def product_to_rows(product: Product) -> list[dict[str, object]]:
    """Una riga per prodotto semplice, 1+N righe per prodotto variabile."""
    sku = product.ensure_sku()
    attributes = product.attributes
    attribute_name = next(iter(attributes), "")
    attribute_values = attributes.get(attribute_name, [])

    parent = _row(
        Type="variable" if product.is_variable else "simple",
        SKU=sku,
        Name=product.title,
        Published=1,
        **{"Visibility in catalog": "visible"},
        **{"Short description": product.short_description},
        Description=product.description,
        **{"In stock?": 1 if product.in_stock else 0},
        **{"Regular price": product.price if product.price is not None else ""},
        **{"Sale price": product.sale_price if product.sale_price is not None else ""},
        Categories=", ".join(product.categories),
        Images=", ".join(product.images),
        Position=0,
        **{"Attribute 1 name": attribute_name},
        **{"Attribute 1 value(s)": " | ".join(attribute_values)},
        **{"Attribute 1 visible": 1 if attribute_name else ""},
        **{"Attribute 1 global": 1 if attribute_name else ""},
    )
    rows = [parent]

    for position, variant in enumerate(product.variants, start=1):
        rows.append(
            _row(
                Type="variation",
                SKU=variant.sku or f"{sku}-{variant.value.upper().replace(' ', '')}",
                Name=f"{product.title} - {variant.value}",
                Published=1,
                **{"In stock?": 1 if variant.in_stock else 0},
                **{
                    "Regular price": variant.price
                    if variant.price is not None
                    else (product.price if product.price is not None else "")
                },
                Parent=f"id:{sku}",
                Position=position,
                **{"Attribute 1 name": variant.attribute},
                **{"Attribute 1 value(s)": variant.value},
                **{"Attribute 1 visible": 1},
                **{"Attribute 1 global": 1},
            )
        )
    return rows


def export_csv(products: Iterable[Product], path: str | Path) -> Path:
    """Scrive il CSV (UTF-8 con BOM: Excel lo apre senza rompere gli accenti)."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with destination.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(COLUMNS))
        writer.writeheader()
        for product in products:
            for row in product_to_rows(product):
                writer.writerow(row)
                written += 1

    logger.info("CSV scritto in %s (%d righe)", destination, written)
    return destination
