"""Controllo (e riparazione) del catalogo letto dal sito.

Serve a chi genera `products.json` per conto proprio: qualunque cosa produca
il tuo script, questo comando dice se il sito lo accetta e, con `--fix`,
completa da solo i campi mancanti.

    python -m catalog_scraper.validate ../data/products.json
    python -m catalog_scraper.validate mio-catalogo.json --fix -o ../data/products.json

Campi obbligatori per prodotto: **title**. Tutto il resto ha un valore di
ripiego sensato.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .models import slugify

SCHEMA_VERSION = 1

# Campi attesi da lib/types.ts, con il valore usato quando mancano.
DEFAULTS: dict[str, Any] = {
    "category": "",
    "listPrice": None,
    "currency": "EUR",
    "images": [],
    "variantLabel": None,
    "variants": [],
    "sku": None,
    "description": "",
    "shortDescription": "",
    "inStock": True,
    "sourceUrl": "",
}


class Esito:
    """Raccoglie errori (bloccanti) e avvisi (il sito funziona comunque)."""

    def __init__(self) -> None:
        self.errori: list[str] = []
        self.avvisi: list[str] = []

    def errore(self, messaggio: str) -> None:
        self.errori.append(messaggio)

    def avviso(self, messaggio: str) -> None:
        self.avvisi.append(messaggio)

    @property
    def valido(self) -> bool:
        return not self.errori


def _as_number(value: Any) -> float | None:
    """Accetta 19.9, "19.9" e "19,90". Zero e negativi valgono "senza prezzo"."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numero = float(value)
    else:
        testo = str(value).strip().replace("€", "").replace(" ", "")
        if not testo:
            return None
        if "," in testo and "." in testo:
            testo = testo.replace(".", "") if testo.rfind(",") > testo.rfind(".") else testo.replace(",", "")
        testo = testo.replace(",", ".")
        try:
            numero = float(testo)
        except ValueError:
            return None
    return round(numero, 2) if numero > 0 else None


def normalizza_prodotto(grezzo: dict[str, Any], indice: int, slug_usati: set[str], esito: Esito) -> dict[str, Any] | None:
    """Completa un prodotto e segnala cosa non va. None se è irrecuperabile."""
    etichetta = f"prodotto #{indice + 1}"

    titolo = str(grezzo.get("title") or "").strip()
    if not titolo:
        esito.avviso(f"{etichetta}: manca il titolo, riga scartata")
        return None
    etichetta = f'"{titolo}"'

    prodotto = dict(grezzo)
    prodotto["title"] = titolo

    # Slug: chiave della pagina /prodotto/<slug>, deve essere unico.
    slug = str(prodotto.get("slug") or "").strip() or slugify(titolo)
    if not slug:
        slug = f"prodotto-{indice + 1}"
    base, contatore = slug, 2
    while slug in slug_usati:
        slug = f"{base}-{contatore}"
        contatore += 1
        esito.avviso(f"{etichetta}: slug duplicato, rinominato in '{slug}'")
    slug_usati.add(slug)
    prodotto["slug"] = slug

    prodotto["id"] = str(prodotto.get("id") or prodotto.get("sku") or slug)

    # Prezzo: numero o assente. Le stringhe vengono convertite.
    prezzo = _as_number(prodotto.get("price"))
    if prodotto.get("price") not in (None, "") and prezzo is None:
        esito.avviso(f"{etichetta}: prezzo non interpretabile ({prodotto.get('price')!r}), diventa «da concordare»")
    prodotto["price"] = prezzo
    prodotto["listPrice"] = _as_number(prodotto.get("listPrice"))
    prodotto["priceOnRequest"] = prezzo is None

    if prodotto["listPrice"] is not None and prezzo is not None and prodotto["listPrice"] <= prezzo:
        esito.avviso(f"{etichetta}: listPrice non è superiore al prezzo, il barrato viene ignorato")
        prodotto["listPrice"] = None

    # Immagini: lista di URL. Una stringa singola viene incapsulata.
    immagini = prodotto.get("images")
    if isinstance(immagini, str):
        immagini = [immagini]
    if not isinstance(immagini, list):
        immagini = []
    immagini = [str(u).strip() for u in immagini if str(u).strip()]
    prodotto["images"] = list(dict.fromkeys(immagini))
    if not prodotto["images"]:
        esito.avviso(f"{etichetta}: nessuna immagine, in griglia resta un riquadro vuoto")

    valide = [u for u in prodotto["images"] if u.startswith(("http://", "https://", "/"))]
    if len(valide) != len(prodotto["images"]):
        scartata = next(u for u in prodotto["images"] if u not in valide)
        esito.avviso(
            f"{etichetta}: immagine ignorata ({scartata}). Servono URL completi "
            "(https://...) o percorsi dalla cartella public (/foto/x.jpg)"
        )
    prodotto["images"] = valide

    # Varianti: lista di oggetti con almeno un'etichetta.
    varianti_grezze = prodotto.get("variants") or []
    if not isinstance(varianti_grezze, list):
        esito.avviso(f"{etichetta}: 'variants' non è un elenco, ignorato")
        varianti_grezze = []

    varianti: list[dict[str, Any]] = []
    for posizione, voce in enumerate(varianti_grezze):
        if isinstance(voce, str):
            voce = {"label": voce}
        if not isinstance(voce, dict):
            continue
        etichetta_variante = str(voce.get("label") or voce.get("value") or "").strip()
        if not etichetta_variante:
            continue
        varianti.append(
            {
                "id": str(voce.get("id") or f"{prodotto['id']}-{slugify(etichetta_variante) or posizione}"),
                "label": etichetta_variante,
                "attribute": str(voce.get("attribute") or prodotto.get("variantLabel") or "Taglia"),
                "price": _as_number(voce.get("price")),
                "inStock": bool(voce.get("inStock", True)),
                "sku": voce.get("sku") or None,
            }
        )
    prodotto["variants"] = varianti
    prodotto["variantLabel"] = varianti[0]["attribute"] if varianti else None

    if varianti and all(not v["inStock"] for v in varianti):
        esito.avviso(f"{etichetta}: tutte le taglie esaurite, il prodotto risulta non ordinabile")

    for chiave, ripiego in DEFAULTS.items():
        prodotto.setdefault(chiave, ripiego)

    prodotto["inStock"] = bool(prodotto["inStock"])
    prodotto["category"] = str(prodotto.get("category") or "").strip()
    for chiave in ("description", "shortDescription", "sourceUrl", "currency"):
        prodotto[chiave] = str(prodotto.get(chiave) or DEFAULTS.get(chiave) or "")

    return prodotto


def normalizza_catalogo(dati: Any, esito: Esito) -> dict[str, Any]:
    """Accetta sia {"products": [...]} sia un elenco nudo di prodotti."""
    if isinstance(dati, list):
        esito.avviso("Il file è un elenco: viene incapsulato in {\"products\": [...]}")
        grezzi = dati
        radice: dict[str, Any] = {}
    elif isinstance(dati, dict):
        radice = dati
        grezzi = dati.get("products")
        if not isinstance(grezzi, list):
            esito.errore("Manca la chiave 'products' con l'elenco dei prodotti")
            return {}
    else:
        esito.errore("Il file non contiene né un oggetto né un elenco")
        return {}

    if not grezzi:
        esito.errore("Il catalogo è vuoto: il sito non mostrerebbe nessun prodotto")
        return {}

    slug_usati: set[str] = set()
    prodotti = [
        p
        for indice, grezzo in enumerate(grezzi)
        if isinstance(grezzo, dict) and (p := normalizza_prodotto(grezzo, indice, slug_usati, esito))
    ]

    if not prodotti:
        esito.errore("Nessun prodotto utilizzabile: serve almeno il titolo su ogni riga")

    categorie: list[str] = []
    for prodotto in prodotti:
        if prodotto["category"] and prodotto["category"] not in categorie:
            categorie.append(prodotto["category"])

    from datetime import datetime, timezone

    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": radice.get("generatedAt") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "currency": radice.get("currency") or (prodotti[0]["currency"] if prodotti else "EUR"),
        "categories": categorie,
        "products": prodotti,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="catalog_scraper.validate",
        description="Controlla che un products.json sia utilizzabile dal sito.",
    )
    parser.add_argument("file", help="File JSON da controllare")
    parser.add_argument("--fix", action="store_true", help="Completa i campi mancanti e riscrive il file")
    parser.add_argument("-o", "--output", default="", help="Dove scrivere il file corretto (default: sovrascrive)")
    args = parser.parse_args(argv)

    percorso = Path(args.file)
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        print(f"File non trovato: {percorso}")
        return 2
    except json.JSONDecodeError as exc:
        print(f"Il file non è JSON valido: riga {exc.lineno}, colonna {exc.colno} — {exc.msg}")
        return 2

    esito = Esito()
    catalogo = normalizza_catalogo(dati, esito)

    for messaggio in esito.errori:
        print(f"  ERRORE   {messaggio}")
    for messaggio in esito.avvisi:
        print(f"  avviso   {messaggio}")

    if not esito.valido:
        print(f"\n{len(esito.errori)} errori bloccanti.")
        return 1

    prodotti = catalogo.get("products", [])
    senza_prezzo = sum(1 for p in prodotti if p["priceOnRequest"])
    con_taglie = sum(1 for p in prodotti if p["variants"])
    immagini = sum(len(p["images"]) for p in prodotti)

    print(
        f"\nCatalogo valido: {len(prodotti)} prodotti, {len(catalogo['categories'])} categorie, "
        f"{immagini} immagini, {con_taglie} con taglie, {senza_prezzo} da concordare."
    )
    if esito.avvisi:
        print(f"{len(esito.avvisi)} avvisi: il sito funziona comunque.")

    if args.fix:
        destinazione = Path(args.output or percorso)
        destinazione.parent.mkdir(parents=True, exist_ok=True)
        destinazione.write_text(
            json.dumps(catalogo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Scritto: {destinazione}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
