"""Test del parser e degli exporter su fixture HTML statiche.

    cd scraper && python -m pytest -q
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from catalog_scraper.config import ScraperConfig
from catalog_scraper.exporters.json_exporter import build_catalog, export_json
from catalog_scraper.models import Product, Variant
from catalog_scraper.parser import CatalogParser, detect_currency, parse_price

FIXTURES = Path(__file__).parent / "fixtures"

CONFIG = ScraperConfig.from_dict(
    {
        "site": {
            "name": "demo",
            "base_url": "https://esempio-store.com",
            "catalog_url": "https://esempio-store.com/collezioni/tutti",
            "pagination": {"mode": "link", "next_selector": "a.pagination__next"},
        },
        "selectors": {
            "product_card": "ul.product-grid li.card",
            "title": ".card__heading",
            "url": "a.card__link",
            "price": ".price__regular .money",
            "sale_price": ".price__sale .money",
            "image": ".card__media img, .card__media picture",
            "category": ".card__vendor",
            "out_of_stock_flag": ".badge--sold-out",
        },
        "detail": {
            "enabled": True,
            "gallery": ".product__media-list img",
            "variants": "select[name='Taglia'] option",
            "variant_attribute": "Taglia",
            "description": ".product__description",
            "short_description": ".product__subtitle",
            "sku": ".product__sku",
            "price": ".product__price .money",
        },
        "parsing": {"sku_prefix": "DS", "default_category": "Novità"},
    }
)


@pytest.fixture(scope="module")
def products() -> list[Product]:
    html = (FIXTURES / "catalog.html").read_text(encoding="utf-8")
    return CatalogParser(CONFIG).parse_catalog(html, CONFIG.site.catalog_url)


# --------------------------------------------------------------------------- #
# Prezzi
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("€ 79,90", 79.90),
        ("€ 1.249,00", 1249.00),
        ("$1,234.56", 1234.56),
        ("da 19,90 EUR", 19.90),
        ("1 299", 1299.0),
        ("Prezzo su richiesta", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_price(raw, expected):
    assert parse_price(raw) == expected


def test_detect_currency():
    assert detect_currency("€ 79,90") == "EUR"
    assert detect_currency("$29.99") == "USD"
    assert detect_currency("29.99") == "EUR"  # fallback


# --------------------------------------------------------------------------- #
# Griglia
# --------------------------------------------------------------------------- #
def test_le_card_placeholder_sono_scartate(products):
    assert len(products) == 3
    assert all(p.title for p in products)


def test_dati_card(products):
    felpa = products[0]
    assert felpa.title == "Felpa Oversize Nera"
    assert felpa.url == "https://esempio-store.com/prodotti/felpa-oversize-nera"
    assert felpa.price == 79.90
    assert felpa.sale_price == 59.90
    assert felpa.categories == ["Felpe"]
    assert felpa.currency == "EUR"


def test_immagini_srcset_e_lazyload(products):
    felpa, jeans, tee = products
    # <picture><source srcset> -> vince la larghezza maggiore
    assert "https://esempio-store.com/img/felpa-1200.jpg" in felpa.images
    # data-src ha priorità sul placeholder base64 in src
    assert "https://esempio-store.com/img/felpa-800.jpg" in felpa.images
    assert not any(url.startswith("data:") for url in felpa.images)
    assert jeans.images == ["https://esempio-store.com/img/jeans-1000.jpg"]
    assert tee.images == ["https://esempio-store.com/img/tee.jpg"]


def test_separatore_migliaia(products):
    assert products[1].price == 1249.00


def test_flag_esaurito(products):
    assert products[2].in_stock is False
    assert products[0].in_stock is True


def test_sku_generato_deterministico(products):
    first = products[0].sku
    assert first.startswith("DS-FELPA-OVERSIZE-NERA-")
    riparsato = CatalogParser(CONFIG).parse_catalog(
        (FIXTURES / "catalog.html").read_text(encoding="utf-8"), CONFIG.site.catalog_url
    )
    assert riparsato[0].sku == first  # import idempotente


def test_next_page():
    html = (FIXTURES / "catalog.html").read_text(encoding="utf-8")
    next_url = CatalogParser(CONFIG).find_next_page(html, CONFIG.site.catalog_url)
    assert next_url == "https://esempio-store.com/collezioni/tutti?page=2"


# --------------------------------------------------------------------------- #
# Scheda prodotto
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def felpa_arricchita(products) -> Product:
    product = Product(**{**products[0].as_dict(), "variants": []})
    product.url = products[0].url
    html = (FIXTURES / "product.html").read_text(encoding="utf-8")
    return CatalogParser(CONFIG).enrich_from_detail(product, html)


def test_enrich_varianti(felpa_arricchita):
    valori = [v.value for v in felpa_arricchita.variants]
    assert valori == ["S", "M", "L", "XL"]  # placeholder escluso
    assert felpa_arricchita.attributes == {"Taglia": ["S", "M", "L", "XL"]}
    assert felpa_arricchita.variants[2].price == 64.90
    assert felpa_arricchita.variants[3].in_stock is False
    assert felpa_arricchita.is_variable


def test_enrich_galleria_e_testi(felpa_arricchita):
    assert "https://esempio-store.com/img/felpa-retro.jpg" in felpa_arricchita.images
    assert (
        "https://esempio-store.com/img/felpa-dettaglio-1400.jpg"
        in felpa_arricchita.images
    )
    assert len(felpa_arricchita.images) == len(set(felpa_arricchita.images))
    assert felpa_arricchita.sku == "FLP-OVR-NER"
    assert "cotone organico" in felpa_arricchita.description
    assert felpa_arricchita.short_description.startswith("Cotone pesante")


# --------------------------------------------------------------------------- #
# Export JSON (contratto con il frontend)
# --------------------------------------------------------------------------- #
def test_catalogo_json_prodotto_variabile(felpa_arricchita, tmp_path):
    destination = export_json([felpa_arricchita], tmp_path / "products.json")
    catalog = json.loads(destination.read_text(encoding="utf-8"))

    assert catalog["schemaVersion"] == 1
    assert catalog["categories"] == ["Felpe"]
    assert catalog["generatedAt"].endswith("+00:00")

    product = catalog["products"][0]
    assert product["slug"] == "felpa-oversize-nera"
    assert product["title"] == "Felpa Oversize Nera"
    assert product["price"] == 59.90          # prezzo scontato
    assert product["listPrice"] == 79.90      # prezzo pieno barrato
    assert product["priceOnRequest"] is False
    assert product["variantLabel"] == "Taglia"
    assert [v["label"] for v in product["variants"]] == ["S", "M", "L", "XL"]
    assert product["variants"][2]["price"] == 64.90
    assert product["variants"][3]["inStock"] is False
    assert len(product["images"]) == len(set(product["images"]))


def test_prodotto_senza_prezzo_e_da_concordare():
    muto = Product(title="Borsa su misura", categories=["Accessori"])
    muto.ensure_sku()
    catalog = build_catalog([muto])

    assert catalog["products"][0]["priceOnRequest"] is True
    assert catalog["products"][0]["price"] is None


def test_slug_duplicati_restano_unici():
    primo = Product(title="Cappello", price=19.9, url="https://a.test/1")
    secondo = Product(title="Cappello", price=24.9, url="https://a.test/2")
    primo.ensure_sku()
    secondo.ensure_sku()

    slugs = [p["slug"] for p in build_catalog([primo, secondo])["products"]]
    assert slugs == ["cappello", "cappello-2"]


def test_variante_senza_prezzo_resta_nulla():
    product = Product(title="Cinta", price=25.0)
    product.ensure_sku()
    product.variants = [Variant(attribute="Taglia", value="Unica")]

    variant = build_catalog([product])["products"][0]["variants"][0]
    assert variant["price"] is None   # il frontend eredita il prezzo del prodotto
    assert variant["label"] == "Unica"
    assert variant["inStock"] is True
