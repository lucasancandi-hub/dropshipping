"""Test del controllo su un catalogo generato da altri strumenti."""

from __future__ import annotations

import json

import pytest

from catalog_scraper.validate import Esito, main, normalizza_catalogo


def controlla(dati) -> tuple[dict, Esito]:
    esito = Esito()
    return normalizza_catalogo(dati, esito), esito


# --------------------------------------------------------------------------- #
# Il minimo indispensabile
# --------------------------------------------------------------------------- #
def test_bastano_titolo_e_prezzo():
    catalogo, esito = controlla([{"title": "Scarpa", "price": 19.9}])

    assert esito.valido
    prodotto = catalogo["products"][0]
    assert prodotto["slug"] == "scarpa"          # generato dal titolo
    assert prodotto["id"] == "scarpa"            # generato dallo slug
    assert prodotto["price"] == 19.9
    assert prodotto["priceOnRequest"] is False
    assert prodotto["variants"] == []
    assert prodotto["images"] == []


def test_accetta_sia_elenco_sia_oggetto():
    da_elenco, _ = controlla([{"title": "A", "price": 1}])
    da_oggetto, _ = controlla({"products": [{"title": "A", "price": 1}]})

    assert da_elenco["products"] == da_oggetto["products"]


# --------------------------------------------------------------------------- #
# Correzioni automatiche
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "prezzo,atteso,su_richiesta",
    [
        (19.9, 19.9, False),
        ("19.9", 19.9, False),
        ("19,90", 19.9, False),      # virgola decimale
        ("1.234,50", 1234.5, False), # separatore migliaia
        ("€ 19,90", 19.9, False),
        (0, None, True),             # zero = senza prezzo
        (None, None, True),
        ("da concordare", None, True),
    ],
)
def test_prezzi_in_ogni_formato(prezzo, atteso, su_richiesta):
    catalogo, _ = controlla([{"title": "X", "price": prezzo}])
    prodotto = catalogo["products"][0]

    assert prodotto["price"] == atteso
    assert prodotto["priceOnRequest"] is su_richiesta


def test_immagine_singola_diventa_elenco():
    catalogo, _ = controlla([{"title": "X", "price": 1, "images": "https://x.test/a.jpg"}])
    assert catalogo["products"][0]["images"] == ["https://x.test/a.jpg"]


def test_immagini_duplicate_rimosse():
    catalogo, _ = controlla(
        [{"title": "X", "price": 1, "images": ["https://x.test/a.jpg", "https://x.test/a.jpg"]}]
    )
    assert catalogo["products"][0]["images"] == ["https://x.test/a.jpg"]


def test_immagine_con_percorso_relativo_viene_ignorata():
    catalogo, esito = controlla(
        [{"title": "X", "price": 1, "images": ["foto.jpg", "/foto/ok.jpg"]}]
    )

    assert catalogo["products"][0]["images"] == ["/foto/ok.jpg"]
    assert any("immagine ignorata" in a for a in esito.avvisi)
    assert esito.valido   # non blocca


def test_taglie_come_stringhe_semplici():
    catalogo, _ = controlla([{"title": "X", "price": 1, "variants": ["S", "M", "L"]}])
    varianti = catalogo["products"][0]["variants"]

    assert [v["label"] for v in varianti] == ["S", "M", "L"]
    assert all(v["inStock"] for v in varianti)
    assert catalogo["products"][0]["variantLabel"] == "Taglia"


def test_taglie_come_oggetti_con_disponibilita():
    catalogo, _ = controlla(
        [{"title": "X", "price": 1, "variants": [{"label": "40", "inStock": False}]}]
    )
    assert catalogo["products"][0]["variants"][0]["inStock"] is False


def test_slug_duplicati_resi_unici():
    catalogo, esito = controlla([{"title": "Scarpa", "price": 1}, {"title": "Scarpa", "price": 2}])

    assert [p["slug"] for p in catalogo["products"]] == ["scarpa", "scarpa-2"]
    assert any("slug duplicato" in a for a in esito.avvisi)


def test_riga_senza_titolo_scartata_senza_bloccare():
    catalogo, esito = controlla([{"price": 5}, {"title": "Valida", "price": 10}])

    assert [p["title"] for p in catalogo["products"]] == ["Valida"]
    assert esito.valido
    assert any("riga scartata" in a for a in esito.avvisi)


def test_prezzo_barrato_incoerente_ignorato():
    catalogo, esito = controlla([{"title": "X", "price": 60, "listPrice": 50}])

    assert catalogo["products"][0]["listPrice"] is None
    assert any("listPrice" in a for a in esito.avvisi)


def test_categorie_raccolte_in_ordine():
    catalogo, _ = controlla(
        [
            {"title": "A", "price": 1, "category": "scarpe"},
            {"title": "B", "price": 1, "category": "magliette"},
            {"title": "C", "price": 1, "category": "scarpe"},
        ]
    )
    assert catalogo["categories"] == ["scarpe", "magliette"]


# --------------------------------------------------------------------------- #
# Casi bloccanti
# --------------------------------------------------------------------------- #
def test_catalogo_vuoto_e_bloccante():
    _, esito = controlla([])
    assert not esito.valido


def test_senza_chiave_products_e_bloccante():
    _, esito = controlla({"articoli": []})
    assert not esito.valido
    assert any("products" in e for e in esito.errori)


def test_solo_righe_senza_titolo_e_bloccante():
    _, esito = controlla([{"price": 5}, {"price": 8}])
    assert not esito.valido


# --------------------------------------------------------------------------- #
# Comando
# --------------------------------------------------------------------------- #
def test_fix_scrive_un_file_valido(tmp_path, capsys):
    sorgente = tmp_path / "mio.json"
    sorgente.write_text(
        json.dumps([{"title": "Scarpa", "price": "19,90", "variants": ["40", "41"]}]),
        encoding="utf-8",
    )
    destinazione = tmp_path / "products.json"

    assert main([str(sorgente), "--fix", "-o", str(destinazione)]) == 0

    catalogo = json.loads(destinazione.read_text(encoding="utf-8"))
    assert catalogo["schemaVersion"] == 1
    assert catalogo["products"][0]["price"] == 19.9
    assert "Catalogo valido" in capsys.readouterr().out


def test_json_malformato_spiega_dove(tmp_path, capsys):
    rotto = tmp_path / "rotto.json"
    rotto.write_text('[{"title": "X",}]', encoding="utf-8")

    assert main([str(rotto)]) == 2
    assert "non è JSON valido" in capsys.readouterr().out


def test_file_inesistente(tmp_path, capsys):
    assert main([str(tmp_path / "assente.json")]) == 2
    assert "non trovato" in capsys.readouterr().out
