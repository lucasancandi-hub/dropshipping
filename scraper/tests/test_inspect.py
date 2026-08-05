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
