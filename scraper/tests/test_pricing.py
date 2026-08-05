"""Test del ricarico sul prezzo fornitore.

    cd scraper && python -m pytest -q
"""

from __future__ import annotations

import pytest

from catalog_scraper.config import PricingConfig
from catalog_scraper.exporters.json_exporter import build_catalog
from catalog_scraper.models import Product, Variant
from catalog_scraper.pricing import apply_pricing, apply_rounding, markup_for, sell_price


def prodotto(title="Felpa", price=24.50, category="Felpe", **kwargs) -> Product:
    product = Product(title=title, price=price, categories=[category], **kwargs)
    product.ensure_sku()
    return product


# --------------------------------------------------------------------------- #
# Calcolo base
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "cost,percent,expected",
    [
        (24.50, 100, 49.00),   # raddoppio
        (24.50, 60, 39.20),    # +60%
        (10.00, 0, 10.00),     # nessun ricarico
        (31.00, 150, 77.50),
    ],
)
def test_ricarico_senza_arrotondamento(cost, percent, expected):
    assert sell_price(cost, percent, PricingConfig()) == expected


def test_prezzo_assente_resta_assente():
    assert sell_price(None, 100, PricingConfig()) is None


# --------------------------------------------------------------------------- #
# Arrotondamenti
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "value,expected",
    [
        (49.00, 49.90),
        (24.10, 24.90),
        (25.90, 25.90),   # già in forma psicologica: resta com'è
        (26.00, 26.90),
        (104.40, 104.90),
    ],
)
def test_arrotondamento_charm(value, expected):
    config = PricingConfig(rounding="charm", charm_ending=0.90)
    assert apply_rounding(value, config) == expected


def test_charm_non_scende_mai_sotto_il_prezzo_calcolato():
    """L'arrotondamento non deve erodere il margine."""
    config = PricingConfig(rounding="charm", charm_ending=0.50)
    for cents in range(0, 100):
        value = 20 + cents / 100
        assert apply_rounding(value, config) >= value - 1e-9


def test_arrotondamento_intero_per_eccesso():
    config = PricingConfig(rounding="integer")
    assert apply_rounding(24.10, config) == 25.0
    assert apply_rounding(25.00, config) == 25.0


def test_prezzo_minimo():
    config = PricingConfig(markup_percent=100, min_price=15)
    assert sell_price(2.00, 100, config) == 15.0   # 4,00 -> alzato a 15
    assert sell_price(20.00, 100, config) == 40.0  # sopra la soglia: invariato


# --------------------------------------------------------------------------- #
# Override per categoria
# --------------------------------------------------------------------------- #
def test_override_categoria_case_insensitive():
    config = PricingConfig(markup_percent=100, category_markup={"Giacche": 80})
    assert markup_for("Giacche", config) == 80
    assert markup_for("giacche", config) == 80
    assert markup_for("Felpe", config) == 100
    assert markup_for("", config) == 100


# --------------------------------------------------------------------------- #
# Applicazione al catalogo
# --------------------------------------------------------------------------- #
def test_ricarico_su_prodotto_varianti_e_saldo():
    product = prodotto(price=50.0, sale_price=40.0)
    product.variants = [
        Variant(attribute="Taglia", value="M"),            # eredita dal prodotto
        Variant(attribute="Taglia", value="L", price=55.0),
    ]

    apply_pricing([product], PricingConfig(markup_percent=100))

    assert product.price == 100.0
    assert product.sale_price == 80.0          # lo sconto mantiene la proporzione
    assert product.variants[0].price is None   # continua a ereditare
    assert product.variants[1].price == 110.0
    assert product.extra["cost_price"] == 40.0  # il costo effettivo era il saldo
    assert product.extra["markup_percent"] == 100


def test_prodotto_senza_prezzo_viene_saltato():
    muto = prodotto(price=None)
    stats = apply_pricing([muto], PricingConfig(markup_percent=100))

    assert muto.price is None
    assert stats["skipped"] == 1
    assert stats["processed"] == 0
    assert "cost_price" not in muto.extra


def test_statistiche():
    prodotti = [prodotto(price=10.0), prodotto(title="Altro", price=30.0)]
    stats = apply_pricing(prodotti, PricingConfig(markup_percent=100))

    assert stats["processed"] == 2
    assert stats["avg_cost"] == 20.0
    assert stats["avg_price"] == 40.0
    assert stats["effective_markup"] == 100.0


# --------------------------------------------------------------------------- #
# Il costo non deve finire nel catalogo pubblico
# --------------------------------------------------------------------------- #
def test_costo_escluso_dal_json_pubblico():
    product = prodotto(price=24.50)
    apply_pricing([product], PricingConfig(markup_percent=100))

    esportato = build_catalog([product])["products"][0]

    assert esportato["price"] == 49.0
    assert "costPrice" not in esportato
    assert "markupPercent" not in esportato


def test_costo_incluso_solo_su_richiesta_esplicita():
    product = prodotto(price=24.50)
    apply_pricing([product], PricingConfig(markup_percent=100))

    esportato = build_catalog([product], include_cost=True)["products"][0]

    assert esportato["costPrice"] == 24.50
    assert esportato["markupPercent"] == 100
