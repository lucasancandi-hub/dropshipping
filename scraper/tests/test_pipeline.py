"""Prova end-to-end della catena completa, senza rete.

Esegue davvero il comando con `config.fornitore.yaml`: selettori -> schede
prodotto -> taglie -> ricarico -> products.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from catalog_scraper.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
CONFIG = Path(__file__).parents[1] / "config.fornitore.yaml"


def esegui(tmp_path, *extra: str) -> dict:
    destination = tmp_path / "products.json"
    codice = main(["-c", str(CONFIG), "-o", str(destination), *extra])
    assert codice == 0, "il comando è uscito con errore"
    return json.loads(destination.read_text(encoding="utf-8"))


def test_catena_completa(tmp_path, monkeypatch):
    monkeypatch.setenv("FIXTURES_DIR", str(FIXTURES))
    catalogo = esegui(tmp_path)

    assert len(catalogo["products"]) == 5
    assert catalogo["categories"] == [
        "Felpe",
        "Pantaloni",
        "T-Shirt",
        "Giacche",
        "Maglieria",
    ]

    felpa = catalogo["products"][0]
    assert felpa["title"] == "Felpa Heavy Cotton"
    assert felpa["sku"] == "FLP-HVY-001"          # letto dalla scheda prodotto
    assert felpa["price"] == 49.90                # 24,50 +100% -> 49,00 -> 49,90
    assert felpa["priceOnRequest"] is False
    assert "cotone garzato" in felpa["description"].lower()

    # Taglie dalla scheda prodotto, placeholder escluso, XL esaurita
    assert [v["label"] for v in felpa["variants"]] == ["S", "M", "L", "XL", "XXL"]
    assert felpa["variants"][3]["inStock"] is False
    assert felpa["variants"][2]["price"] == 53.90  # 26,50 +100% -> 53,00 -> 53,90

    # Galleria: immagine di griglia + tre della scheda, senza duplicati
    assert len(felpa["images"]) == 4
    assert len(set(felpa["images"])) == 4


def test_override_categoria_nel_file_finale(tmp_path, monkeypatch):
    monkeypatch.setenv("FIXTURES_DIR", str(FIXTURES))
    prodotti = {p["title"]: p for p in esegui(tmp_path)["products"]}

    # Giacche: 58,00 +80% -> 104,40 -> 104,90
    assert prodotti["Giacca Bomber Nylon"]["price"] == 104.90
    # Maglieria: 1.240,00 +70% -> 2.108,00 -> 2.108,90 (separatore migliaia ok)
    assert prodotti["Maglione Merino Fine"]["price"] == 2108.90


def test_il_flag_markup_sovrascrive_la_configurazione(tmp_path, monkeypatch):
    monkeypatch.setenv("FIXTURES_DIR", str(FIXTURES))
    catalogo = esegui(tmp_path, "--markup", "60")

    # 24,50 +60% -> 39,20 -> 39,90; l'override di categoria resta attivo
    assert catalogo["products"][0]["price"] == 39.90


def test_nessun_costo_fornitore_nel_file_pubblicato(tmp_path, monkeypatch):
    monkeypatch.setenv("FIXTURES_DIR", str(FIXTURES))
    catalogo = esegui(tmp_path)

    grezzo = json.dumps(catalogo)
    assert "costPrice" not in grezzo
    assert "markupPercent" not in grezzo
    # 24.5 è il prezzo di acquisto: non deve comparire da nessuna parte
    assert '"price": 24.5' not in grezzo
