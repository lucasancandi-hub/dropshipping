"""Test del listino CSV compilato a mano."""

from __future__ import annotations

from pathlib import Path

import pytest

from catalog_scraper.config import ScraperConfig
from catalog_scraper.importers.csv_feed import detect_delimiter, load_rows, split_cell
from catalog_scraper.importers.json_feed import import_feed
from catalog_scraper.pricing import apply_pricing, landed_cost
from catalog_scraper.config import PricingConfig

CONFIG_FILE = Path(__file__).parents[1] / "config.listino.yaml"

INTESTAZIONE = "Titolo;Prezzo acquisto;Link prodotto;Categoria;Taglie;Taglie esaurite;Codice;Descrizione;Foto"


def scrivi_csv(tmp_path: Path, righe: list[str], nome: str = "listino.csv") -> Path:
    percorso = tmp_path / nome
    percorso.write_text("\n".join([INTESTAZIONE, *righe]) + "\n", encoding="utf-8")
    return percorso


def configura(file_csv: Path) -> ScraperConfig:
    config = ScraperConfig.load(CONFIG_FILE)
    config.feed.file = str(file_csv)
    config.detail.enabled = False
    return config


# --------------------------------------------------------------------------- #
# Lettura del file
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "sample,expected",
    [
        ("a;b;c\n1;2;3", ";"),      # Excel italiano
        ("a,b,c\n1,2,3", ","),
        ("a\tb\tc\n1\t2\t3", "\t"),
        ("solo-una-colonna\nvalore", ","),  # nessun delimitatore: ripiego
    ],
)
def test_rileva_delimitatore(sample, expected):
    assert detect_delimiter(sample) == expected


def test_delimitatore_dichiarato_vince():
    assert detect_delimiter("a,b\n1,2", configured=";") == ";"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("S|M|L", ["S", "M", "L"]),
        ("S, M, L", ["S", "M", "L"]),   # ripiego sulla virgola
        (" 40 | 41 ", ["40", "41"]),
        ("", []),
        (None, []),
    ],
)
def test_split_cella(value, expected):
    assert split_cell(value, "|") == expected


def test_bom_di_excel_non_sporca_la_prima_colonna(tmp_path):
    percorso = tmp_path / "con-bom.csv"
    percorso.write_text(
        "﻿" + INTESTAZIONE + "\nScarpa;10,00;;scarpe;40;;A1;desc;\n", encoding="utf-8"
    )
    config = configura(percorso)
    prodotti = import_feed(config)

    assert len(prodotti) == 1
    assert prodotti[0].title == "Scarpa"   # non "﻿Scarpa"


# --------------------------------------------------------------------------- #
# Taglie
# --------------------------------------------------------------------------- #
def test_taglia_in_entrambe_le_colonne_conta_una_volta_sola(tmp_path):
    """L'errore di compilazione più probabile: 41 elencata due volte."""
    percorso = scrivi_csv(tmp_path, ["Scarpa;20,00;;scarpe;40|41|42;41;A1;desc;"])
    prodotti = import_feed(configura(percorso))

    taglie = prodotti[0].variants
    assert [v.value for v in taglie] == ["40", "41", "42"]
    assert [v.in_stock for v in taglie] == [True, False, True]


def test_taglia_solo_fra_le_esaurite_viene_comunque_elencata(tmp_path):
    percorso = scrivi_csv(tmp_path, ["Scarpa;20,00;;scarpe;40|42;44;A1;desc;"])
    taglie = import_feed(configura(percorso))[0].variants

    assert [v.value for v in taglie] == ["40", "42", "44"]
    assert taglie[2].in_stock is False


def test_senza_taglie_il_prodotto_resta_semplice(tmp_path):
    percorso = scrivi_csv(tmp_path, ["Borsa;30,00;;accessori;;;A1;desc;"])
    prodotto = import_feed(configura(percorso))[0]

    assert prodotto.variants == []
    assert prodotto.is_variable is False


# --------------------------------------------------------------------------- #
# Prezzi e campi
# --------------------------------------------------------------------------- #
def test_prezzo_con_virgola_decimale(tmp_path):
    percorso = scrivi_csv(tmp_path, ["Scarpa;24,50;;scarpe;40;;A1;desc;"])
    assert import_feed(configura(percorso))[0].price == 24.50


def test_riga_senza_prezzo_diventa_da_concordare(tmp_path):
    percorso = scrivi_csv(tmp_path, ["Borsa;;;accessori;Unica;;A1;desc;"])
    prodotto = import_feed(configura(percorso))[0]

    assert prodotto.price is None
    assert prodotto.effective_price is None


def test_riga_senza_titolo_viene_scartata(tmp_path):
    percorso = scrivi_csv(
        tmp_path, [";10,00;;scarpe;40;;A1;desc;", "Valida;12,00;;scarpe;41;;A2;desc;"]
    )
    prodotti = import_feed(configura(percorso))

    assert [p.title for p in prodotti] == ["Valida"]


def test_codice_duplicato_non_crea_due_prodotti(tmp_path):
    percorso = scrivi_csv(
        tmp_path,
        ["Scarpa;20,00;;scarpe;40;;DUP;desc;", "Scarpa bis;22,00;;scarpe;41;;DUP;desc;"],
    )
    assert len(import_feed(configura(percorso))) == 1


def test_foto_multiple_nella_stessa_cella(tmp_path):
    percorso = scrivi_csv(
        tmp_path, ["Giacca;38,00;;giacche;M;;A1;desc;https://x.test/1.jpg|https://x.test/2.jpg"]
    )
    assert import_feed(configura(percorso))[0].images == [
        "https://x.test/1.jpg",
        "https://x.test/2.jpg",
    ]


def test_link_scheda_conservato_per_l_arricchimento(tmp_path):
    """Serve a visitare la pagina del fornitore e prenderne le foto."""
    percorso = scrivi_csv(
        tmp_path, ["Scarpa;20,00;https://fornitore.test/p/scarpa;scarpe;40;;A1;desc;"]
    )
    assert import_feed(configura(percorso))[0].url == "https://fornitore.test/p/scarpa"


# --------------------------------------------------------------------------- #
# Costo reale: il listino non comprende la spedizione in acquisto
# --------------------------------------------------------------------------- #
def test_maggiorazione_fissa_sul_costo():
    config = PricingConfig(markup_percent=60, cost_surcharge_fixed=3.50)
    assert landed_cost(20.00, config) == 23.50


def test_maggiorazione_percentuale_sul_costo():
    config = PricingConfig(markup_percent=60, cost_surcharge_percent=10)
    assert landed_cost(20.00, config) == 22.00


def test_il_ricarico_parte_dal_costo_reale():
    from catalog_scraper.models import Product

    prodotto = Product(title="Scarpa", price=20.00, categories=["scarpe"])
    prodotto.ensure_sku()

    apply_pricing(
        [prodotto],
        PricingConfig(markup_percent=60, rounding="charm", cost_surcharge_fixed=3.50),
    )

    # 20,00 + 3,50 = 23,50 -> +60% = 37,60 -> arrotondato 37,90
    assert prodotto.extra["cost_price"] == 20.00
    assert prodotto.extra["landed_cost"] == 23.50
    assert prodotto.price == 37.90
    # Il margine resta sopra il costo reale, non sopra il prezzo nudo
    assert prodotto.price - prodotto.extra["landed_cost"] > 14


def test_lo_scaglione_si_calcola_sul_costo_reale():
    from catalog_scraper.models import Product

    # 95 + 10 di spedizione supera la soglia dei 100: scatta il 50%
    prodotto = Product(title="Giacca", price=95.00, categories=["giacche"])
    prodotto.ensure_sku()

    apply_pricing(
        [prodotto],
        PricingConfig(
            markup_percent=60,
            price_tiers=[{"above": 100, "percent": 50}],
            cost_surcharge_fixed=10.00,
        ),
    )

    assert prodotto.extra["markup_percent"] == 50
