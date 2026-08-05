"""Ricarico sul prezzo del fornitore.

Il prezzo estratto dal sito sorgente è un **costo**: qui diventa prezzo di
vendita applicando una percentuale di ricarico, un eventuale override per
categoria e una regola di arrotondamento.

Il costo resta in `Product.extra['cost_price']` e per impostazione predefinita
**non finisce nel JSON esportato**: quel file viene incluso nel bundle del sito
e sarebbe leggibile da chiunque apra il browser.
"""

from __future__ import annotations

import logging
import math
from typing import Iterable

from .config import PricingConfig
from .models import Product

logger = logging.getLogger(__name__)


def markup_for(category: str, cost: float | None, pricing: PricingConfig) -> float:
    """Percentuale da applicare a questo prodotto.

    Ordine di precedenza, dal più specifico al più generico:

    1. override per categoria (`category_markup`),
    2. scaglione di costo (`price_tiers`): vince la soglia più alta raggiunta,
    3. `markup_percent`.

    Gli articoli costosi sopportano un ricarico percentuale minore a parità di
    margine assoluto, da cui gli scaglioni.
    """
    wanted = (category or "").strip().lower()
    for name, percent in pricing.category_markup.items():
        if str(name).strip().lower() == wanted and wanted:
            return float(percent)

    if cost is not None and pricing.price_tiers:
        applicabili = [
            tier
            for tier in pricing.price_tiers
            if cost >= float(tier.get("above", 0))
        ]
        if applicabili:
            migliore = max(applicabili, key=lambda t: float(t.get("above", 0)))
            return float(migliore["percent"])

    return pricing.markup_percent


def apply_rounding(value: float, pricing: PricingConfig) -> float:
    """Arrotonda il prezzo di vendita secondo la strategia configurata.

    * `none`    -> due decimali,
    * `integer` -> intero superiore (24,10 -> 25),
    * `charm`   -> prima cifra "psicologica" >= valore (24,10 -> 24,90).

    L'arrotondamento non scende mai sotto il prezzo calcolato: meglio un
    centesimo in più che un margine eroso.
    """
    if pricing.rounding == "integer":
        return float(math.ceil(value))

    if pricing.rounding == "charm":
        ending = pricing.charm_ending
        candidate = math.floor(value) + ending
        if candidate < value - 1e-9:
            candidate += 1
        return round(candidate, 2)

    return round(value, 2)


def sell_price(cost: float | None, percent: float, pricing: PricingConfig) -> float | None:
    """Costo fornitore -> prezzo di vendita. `None` resta `None`."""
    if cost is None:
        return None

    price = cost * (1 + percent / 100.0)
    price = apply_rounding(price, pricing)

    if pricing.min_price and price < pricing.min_price:
        price = round(pricing.min_price, 2)

    return price


def apply_pricing(products: Iterable[Product], pricing: PricingConfig) -> dict[str, float]:
    """Applica il ricarico in blocco. Ritorna qualche statistica per il log.

    Il ricarico tocca prezzo pieno, prezzo scontato e prezzi delle singole
    varianti con la stessa percentuale, così l'eventuale sconto mantiene la
    proporzione originale.
    """
    processed = 0
    skipped = 0
    total_cost = 0.0
    total_price = 0.0

    for product in products:
        cost = product.effective_price

        if cost is None or cost <= 0:
            # Prodotto senza prezzo: resta "da concordare in chat".
            # Ricaricare zero produrrebbe un prezzo di vendita inventato.
            skipped += 1
            continue

        percent = markup_for(
            product.categories[0] if product.categories else "", cost, pricing
        )

        product.extra["cost_price"] = cost
        product.extra["markup_percent"] = percent

        product.price = sell_price(product.price, percent, pricing)
        product.sale_price = sell_price(product.sale_price, percent, pricing)

        for variant in product.variants:
            variant.price = sell_price(variant.price, percent, pricing)

        processed += 1
        total_cost += cost
        total_price += product.effective_price or 0.0

    stats = {
        "processed": processed,
        "skipped": skipped,
        "avg_cost": round(total_cost / processed, 2) if processed else 0.0,
        "avg_price": round(total_price / processed, 2) if processed else 0.0,
        "effective_markup": round((total_price / total_cost - 1) * 100, 1)
        if total_cost
        else 0.0,
    }

    logger.info(
        "Ricarico applicato a %d prodotti (%d senza prezzo): media %.2f -> %.2f "
        "(+%.1f%% effettivo dopo arrotondamento)",
        stats["processed"],
        stats["skipped"],
        stats["avg_cost"],
        stats["avg_price"],
        stats["effective_markup"],
    )

    return stats
