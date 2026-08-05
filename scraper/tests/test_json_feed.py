"""Test dell'import da feed JSON.

La fixture `feed-demo.json` ha la stessa forma della risposta di
dummyjson.com, così quello che passa qui passa anche contro l'API vera.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from catalog_scraper.config import FeedConfig, FeedMapping, ScraperConfig
from catalog_scraper.importers.json_feed import (
    import_feed,
    item_to_product,
    resolve,
)

FIXTURES = Path(__file__).parent / "fixtures"
FEED = FIXTURES / "feed-demo.json"
CONFIG_FILE = Path(__file__).parents[1] / "config.feed-demo.yaml"


@pytest.fixture(scope="module")
def config() -> ScraperConfig:
    scraper_config = ScraperConfig.load(CONFIG_FILE)
    scraper_config.feed.file = str(FEED)  # il path nel YAML è relativo a scraper/
    return scraper_config


@pytest.fixture(scope="module")
def prodotti(config) -> list:
    return import_feed(config)


# --------------------------------------------------------------------------- #
# Percorsi puntati
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "path,expected",
    [
        ("title", "Scarpa"),
        ("meta.sku", "ABC"),
        ("images.0", "uno.jpg"),
        ("images.5", None),          # indice fuori range
        ("manca", None),
        ("meta.manca.ancora", None),  # discesa in un ramo inesistente
        ("", None),
    ],
)
def test_resolve(path, expected):
    dato = {"title": "Scarpa", "meta": {"sku": "ABC"}, "images": ["uno.jpg", "due.jpg"]}
    assert resolve(dato, path) == expected


# --------------------------------------------------------------------------- #
# Import completo
# --------------------------------------------------------------------------- #
def test_scarta_gli_elementi_senza_titolo(prodotti):
    """La fixture contiene un elemento con titolo vuoto."""
    assert len(prodotti) == 5
    assert all(p.title for p in prodotti)


def test_campi_di_base(prodotti):
    scarpa = prodotti[0]
    assert scarpa.title == "Sneaker Runner Grigia"
    assert scarpa.sku == "SNK-RUN-GRI"
    assert scarpa.categories == ["scarpe"]
    assert scarpa.price == 42.00
    assert "mesh traspirante" in scarpa.description


def test_sconto_percentuale_diventa_prezzo_scontato(prodotti):
    """discountPercentage: 10.5 su 42,00 -> 37,59 effettivi."""
    scarpa = prodotti[0]
    assert scarpa.sale_price == 37.59
    assert scarpa.effective_price == 37.59

    # Sconto 0: nessun prezzo scontato inventato
    maglietta = prodotti[1]
    assert maglietta.sale_price is None
    assert maglietta.effective_price == 12.50


def test_immagini_array_piu_singola_senza_duplicati(prodotti):
    scarpa = prodotti[0]
    assert scarpa.images == [
        "https://esempio.test/img/sneaker-1.jpg",
        "https://esempio.test/img/sneaker-2.jpg",
        "https://esempio.test/img/sneaker-thumb.jpg",   # da `thumbnail`
    ]


def test_varianti_da_oggetti(prodotti):
    taglie = prodotti[0].variants
    assert [v.value for v in taglie] == ["40", "41", "42", "43"]
    assert taglie[1].in_stock is False        # stock 0
    assert taglie[2].price == 44.00           # prezzo proprio della taglia
    assert taglie[0].price is None            # eredita dal prodotto
    assert taglie[0].attribute == "Taglia"


def test_varianti_da_lista_di_stringhe(prodotti):
    """Un feed può dare le taglie come semplici stringhe."""
    oversize = next(p for p in prodotti if p.title == "T-Shirt Oversize Nera")
    assert [v.value for v in oversize.variants] == ["S", "M", "L", "XL"]
    assert all(v.in_stock for v in oversize.variants)


def test_disponibilita_dal_campo_stock(prodotti):
    oversize = next(p for p in prodotti if p.title == "T-Shirt Oversize Nera")
    assert oversize.in_stock is False        # stock: 0
    assert prodotti[0].in_stock is True      # stock: 24


def test_prezzo_zero_vale_come_assente(prodotti):
    """Un prezzo a 0 nel feed significa "da definire", non merce gratis."""
    trail = next(p for p in prodotti if p.title == "Sneaker Trail Verde")
    assert trail.price is None
    assert trail.effective_price is None


# --------------------------------------------------------------------------- #
# Paginazione a offset
# --------------------------------------------------------------------------- #
class FakeFetcher:
    """Simula un'API paginata senza toccare la rete."""

    def __init__(self, pagine: list[dict]) -> None:
        self.pagine = pagine
        self.urls: list[str] = []

    def get(self, url: str) -> str:
        self.urls.append(url)
        indice = len(self.urls) - 1
        return json.dumps(self.pagine[min(indice, len(self.pagine) - 1)])

    def close(self) -> None:
        pass


def test_paginazione_offset_si_ferma_al_totale():
    def pagina(inizio: int, quanti: int) -> dict:
        return {
            "products": [
                {"title": f"Prodotto {i}", "price": 10 + i, "sku": f"S{i}"}
                for i in range(inizio, inizio + quanti)
            ],
            "total": 5,
        }

    config = ScraperConfig.from_dict(
        {
            "feed": {
                "enabled": True,
                "url": "https://api.esempio.test/products",
                "root": "products",
                "pagination_mode": "offset",
                "page_size": 2,
                "total_key": "total",
            }
        }
    )

    fetcher = FakeFetcher([pagina(0, 2), pagina(2, 2), pagina(4, 1)])
    prodotti = import_feed(config, fetcher)

    assert len(prodotti) == 5
    assert len(fetcher.urls) == 3
    # I parametri di paginazione avanzano come previsto
    assert "limit=2&skip=0" in fetcher.urls[0].replace("%3D", "=")
    assert "skip=2" in fetcher.urls[1]
    assert "skip=4" in fetcher.urls[2]


def test_max_items_tronca_il_risultato():
    config = ScraperConfig.from_dict(
        {
            "feed": {
                "enabled": True,
                "url": "https://api.esempio.test/products",
                "pagination_mode": "none",
                "max_items": 2,
            }
        }
    )
    pagina = {
        "products": [
            {"title": f"P{i}", "price": 10 + i, "sku": f"S{i}"} for i in range(6)
        ]
    }
    assert len(import_feed(config, FakeFetcher([pagina]))) == 2


# --------------------------------------------------------------------------- #
# Configurazione
# --------------------------------------------------------------------------- #
def test_in_modalita_feed_i_selettori_non_servono():
    config = ScraperConfig.from_dict(
        {"feed": {"enabled": True, "url": "https://api.esempio.test/products"}}
    )
    config.validate()   # non deve lamentare catalog_url o product_card


def test_feed_senza_sorgente_e_invalido():
    config = ScraperConfig.from_dict({"feed": {"enabled": True}})
    with pytest.raises(ValueError, match="feed.url"):
        config.validate()


def test_mappatura_personalizzata():
    """Un feed con nomi di campo diversi si adatta senza toccare il codice."""
    feed = FeedConfig(
        enabled=True,
        variant_attribute="Misura",
        mapping=FeedMapping(
            title="nome",
            price="listino.netto",
            category="reparto",
            images="foto",
            sku="codice",
            stock="giacenza",
            variants="misure",
            variant_label="etichetta",
        ),
    )

    item = {
        "nome": "Maglietta Basic",
        "listino": {"netto": "14,90"},
        "reparto": "magliette",
        "foto": ["a.jpg"],
        "codice": "MB-01",
        "giacenza": 3,
        "misure": [{"etichetta": "M"}, {"etichetta": "L"}],
    }

    prodotto = item_to_product(item, feed, "EUR", "DEMO")

    assert prodotto is not None
    assert prodotto.title == "Maglietta Basic"
    assert prodotto.price == 14.90          # virgola decimale interpretata
    assert prodotto.categories == ["magliette"]
    assert prodotto.sku == "MB-01"
    assert [v.value for v in prodotto.variants] == ["M", "L"]
    assert prodotto.variants[0].attribute == "Misura"
