"""Test del rilevamento automatico dei selettori."""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from catalog_scraper.inspect import (
    detect_card,
    detect_pagination,
    find_price_nodes,
    guess_selectors,
    report,
)

FIXTURES = Path(__file__).parent / "fixtures"
CATALOGO = (FIXTURES / "fornitore-catalogo.html").read_text(encoding="utf-8")


def soup_catalogo() -> BeautifulSoup:
    return BeautifulSoup(CATALOGO, "lxml")


def test_trova_i_prezzi():
    prezzi = find_price_nodes(soup_catalogo())
    assert len(prezzi) == 5
    assert "24,50" in prezzi[0].get_text()


def test_individua_la_card_e_non_il_contenitore_del_prezzo():
    """Il wrapper del prezzo si ripete quanto la card: va scartato."""
    selettore, cards = detect_card(soup_catalogo())

    assert selettore == "article.product-item"
    assert len(cards) == 5


def test_selettori_dedotti():
    _, cards = detect_card(soup_catalogo())
    guesses = guess_selectors(cards)

    assert guesses["title"] == ".product-item__title"
    assert guesses["url"] == ".product-item__link"
    assert guesses["price"] == ".amount"
    assert guesses["image"] == ".product-item__img"
    assert guesses["category"] == ".product-item__brand"
    # Il badge "esaurito" esiste solo sulla quarta card: va cercato in tutte.
    assert "out_of_stock_flag" in guesses


def test_link_pagina_successiva():
    assert detect_pagination(soup_catalogo()) == ".pager__next"


def test_report_contiene_yaml_e_anteprima():
    testo = report(CATALOGO, "fixture", limit=2)

    assert 'product_card: "article.product-item"' in testo
    assert "Felpa Heavy Cotton" in testo
    assert "24,50" in testo
    assert "-> 24.5" in testo          # il prezzo viene anche interpretato
    assert "(non trovato)" not in testo


def test_pagina_senza_griglia_spiega_il_problema():
    testo = report("<html><body><p>Nessun prodotto</p></body></html>", "vuota")

    assert "Nessuna griglia riconosciuta" in testo
    assert "selenium" in testo         # suggerisce la causa più comune


# --------------------------------------------------------------------------- #
# Scrittura dei selettori nel file di configurazione
# --------------------------------------------------------------------------- #
def test_write_config_sostituisce_solo_i_selettori(tmp_path):
    """I commenti del file di configurazione devono sopravvivere."""
    from catalog_scraper.inspect import merge_into_config

    config = tmp_path / "config.yaml"
    config.write_text(
        "\n".join(
            [
                "# commento iniziale",
                "site:",
                '  name: prova',
                "  pagination:",
                '    next_selector: "VECCHIO"',
                "",
                "# commento sopra i selettori",
                "selectors:",
                '  product_card: "DA_RILEVARE"',
                '  title: "DA_RILEVARE"',
                "",
                "# commento finale",
                "pricing:",
                "  markup_percent: 60",
                "",
            ]
        ),
        encoding="utf-8",
    )

    _, cards = detect_card(soup_catalogo())
    merge_into_config(
        config,
        {"product_card": "article.product-item", **guess_selectors(cards)},
        ".pager__next",
    )

    testo = config.read_text(encoding="utf-8")

    assert 'product_card: "article.product-item"' in testo
    assert 'title: ".product-item__title"' in testo
    assert "DA_RILEVARE" not in testo
    # Tutto il resto resta dov'era
    assert "# commento iniziale" in testo
    assert "# commento sopra i selettori" in testo
    assert "# commento finale" in testo
    assert "markup_percent: 60" in testo
    assert 'next_selector: ".pager__next"' in testo
    assert "VECCHIO" not in testo


def test_write_config_su_file_senza_blocco_selettori(tmp_path):
    from catalog_scraper.inspect import merge_into_config

    config = tmp_path / "config.yaml"
    config.write_text("site:\n  name: prova\n", encoding="utf-8")

    _, cards = detect_card(soup_catalogo())
    merge_into_config(config, {"product_card": "article.product-item", **guess_selectors(cards)})

    testo = config.read_text(encoding="utf-8")
    assert "name: prova" in testo
    assert "selectors:" in testo


def test_classi_tailwind_arbitrarie_non_rompono_i_selettori():
    """`mt-[12px]` o `w-1/2` non sono identificatori CSS validi.

    Finivano dentro i selettori generati e facevano esplodere il parser di
    soupsieve: vanno scartate, sono comunque classi di impaginazione.
    """
    from catalog_scraper.inspect import signature, usable_classes

    html = """
    <div class="grid">
      <div class="card mt-[12px] w-1/2"><a href="/a"><img src="/1.jpg"></a>
        <h3 class="font-bold">Uno</h3><div class="price"><span>10,00 €</span></div></div>
      <div class="card mt-[12px] w-1/2"><a href="/b"><img src="/2.jpg"></a>
        <h3 class="font-bold">Due</h3><div class="price"><span>20,00 €</span></div></div>
      <div class="card mt-[12px] w-1/2"><a href="/c"><img src="/3.jpg"></a>
        <h3 class="font-bold">Tre</h3><div class="price"><span>30,00 €</span></div></div>
    </div>"""

    documento = BeautifulSoup(html, "lxml")
    carta = documento.select_one(".card")

    assert usable_classes(carta) == ["card"]
    assert signature(carta) == "div.card"

    # Non deve sollevare SelectorSyntaxError
    selettore, cards = detect_card(documento)
    assert selettore == "div.card"
    assert len(cards) == 3
