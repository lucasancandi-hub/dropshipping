"""Rilevamento automatico dei selettori CSS di una pagina catalogo.

    python -m catalog_scraper.inspect --html-file pagina.html
    python -m catalog_scraper.inspect --url https://fornitore.it/collezione

Come funziona: trova i nodi che contengono un prezzo, risale i loro antenati e
cerca la struttura che si **ripete** con la stessa firma di classi. Quella è la
card prodotto. Da lì deduce titolo, link, immagine e categoria.

L'output è un blocco YAML da incollare nel file di configurazione. Va sempre
riletto: è un punto di partenza, non un oracolo.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from .config import HttpConfig
from .parser import parse_price

logger = logging.getLogger("catalog_scraper.inspect")

# Un prezzo: simbolo di valuta accanto a un numero con decimali.
PRICE_TEXT = re.compile(
    r"(?:[€$£]\s?\d[\d.,\s]*|\d[\d.,\s]*\s?(?:€|\$|£|EUR|USD|GBP))", re.IGNORECASE
)

TITLE_HINTS = ("title", "name", "heading", "titolo", "nome", "prodotto", "product")
CATEGORY_HINTS = ("vendor", "brand", "categor", "marca", "collection")
SOLDOUT_HINTS = ("sold", "esaur", "out-of-stock", "unavailable", "nondisponibile")
NOISE_HINTS = ("cart", "carrello", "wishlist", "compare", "quick", "badge-new")


def signature(node: Tag, max_classes: int = 3) -> str:
    """Firma CSS di un elemento: `li.card.product`. Senza classi, solo il tag."""
    classes = [c for c in (node.get("class") or []) if not c.startswith("js-")]
    if not classes:
        return node.name
    return node.name + "".join(f".{c}" for c in classes[:max_classes])


def _own_text(node: Tag) -> str:
    """Testo dei soli figli diretti: evita di attribuire il prezzo ai contenitori."""
    return " ".join(t.strip() for t in node.find_all(string=True, recursive=False)).strip()


def find_price_nodes(soup: BeautifulSoup) -> list[Tag]:
    """Elementi foglia il cui testo proprio è un prezzo."""
    found: list[Tag] = []
    for node in soup.find_all(True):
        text = _own_text(node)
        if not text or len(text) > 40:
            continue
        if PRICE_TEXT.search(text) and parse_price(text) is not None:
            found.append(node)
    return found


def richness(node: Tag) -> int:
    """Quanto un elemento "sembra" una card prodotto completa.

    Il contenitore del solo prezzo si ripete quanto la card, quindi la
    ripetizione da sola non basta a distinguerli: serve verificare che dentro
    ci siano anche link, immagine e titolo.
    """
    score = 0
    if node.find("a", href=True):
        score += 1
    if node.find("img") or node.find("picture"):
        score += 1
    if node.find(["h1", "h2", "h3", "h4", "h5"]):
        score += 2
    elif _hinted(node, TITLE_HINTS) is not None:
        score += 1
    return score


def detect_card(soup: BeautifulSoup, min_occurrences: int = 3) -> tuple[str, list[Tag]]:
    """Individua il selettore della card prodotto e le card trovate.

    Si risale dagli elementi-prezzo raccogliendo i candidati che si ripetono
    almeno `min_occurrences` volte con un solo prezzo ciascuno, e si sceglie
    il più "ricco"; a parità di ricchezza vince il più interno, cioè la card
    più stretta che contiene comunque tutti i dati.
    """
    price_nodes = find_price_nodes(soup)
    if not price_nodes:
        return "", []

    # Per ogni livello di risalita, conta quante volte ricorre ciascuna firma.
    per_level: list[Counter[str]] = [Counter() for _ in range(7)]
    for price in price_nodes:
        ancestor: Tag | None = price
        for level in range(7):
            ancestor = ancestor.parent if ancestor else None
            if not isinstance(ancestor, Tag) or ancestor.name in ("body", "html", "[document]"):
                break
            per_level[level][signature(ancestor)] += 1

    best: tuple[int, int, str, list[Tag]] | None = None  # (score, -level, sig, cards)

    for level, counter in enumerate(per_level):
        for sig, count in counter.most_common():
            if count < min_occurrences:
                continue
            usable = [c for c in soup.select(sig) if len(find_price_nodes(c)) == 1]
            if len(usable) < min_occurrences:
                continue

            score = richness(usable[0])
            candidate = (score, -level, sig, usable)
            if best is None or candidate[:2] > best[:2]:
                best = candidate

            # Punteggio pieno: card con link, immagine e intestazione.
            if score == 4:
                return sig, usable

    if best is not None:
        return best[2], best[3]

    # Ripiego: il contenitore diretto del prezzo.
    parents = Counter(signature(p.parent) for p in price_nodes if isinstance(p.parent, Tag))
    if parents:
        sig = parents.most_common(1)[0][0]
        return sig, soup.select(sig)

    return "", []


def _relative_selector(card: Tag, node: Tag) -> str:
    """Selettore del nodo relativo alla card: preferisce le classi, poi il tag."""
    classes = [c for c in (node.get("class") or []) if not c.startswith("js-")]
    if classes:
        candidate = "." + classes[0]
        if len(card.select(candidate)) == 1:
            return candidate
        return "".join(f".{c}" for c in classes[:2])
    if len(card.select(node.name)) == 1:
        return node.name
    return f"{node.parent.name} {node.name}" if isinstance(node.parent, Tag) else node.name


def _hinted(card: Tag, hints: tuple[str, ...]) -> Tag | None:
    """Primo elemento le cui classi contengono uno degli indizi."""
    for node in card.find_all(True):
        blob = " ".join(node.get("class") or []).lower()
        if not blob or any(noise in blob for noise in NOISE_HINTS):
            continue
        if any(hint in blob for hint in hints):
            return node
    return None


def guess_selectors(cards: list[Tag]) -> dict[str, str]:
    """Deduce i selettori dei campi dentro le card.

    I campi obbligatori si leggono dalla prima card; quelli opzionali
    (categoria, badge esaurito) vengono cercati in tutte, perché compaiono solo
    su alcuni prodotti.
    """
    card = cards[0]
    guesses: dict[str, str] = {}

    # Titolo: intestazione, altrimenti classe con un indizio, altrimenti il link più lungo.
    heading = card.find(["h1", "h2", "h3", "h4", "h5"])
    title = heading or _hinted(card, TITLE_HINTS)
    if not title:
        links = [a for a in card.find_all("a") if a.get_text(strip=True)]
        title = max(links, key=lambda a: len(a.get_text(strip=True)), default=None)
    if title:
        guesses["title"] = _relative_selector(card, title)

    prices = find_price_nodes(card)
    if prices:
        guesses["price"] = _relative_selector(card, prices[0])

    link = card if card.name == "a" else card.find("a", href=True)
    if isinstance(link, Tag) and link is not card:
        guesses["url"] = _relative_selector(card, link)

    image = card.find("img") or card.find("picture")
    if isinstance(image, Tag):
        guesses["image"] = _relative_selector(card, image)

    for key, hints in (("category", CATEGORY_HINTS), ("out_of_stock_flag", SOLDOUT_HINTS)):
        for candidate in cards:
            node = _hinted(candidate, hints)
            if node is not None:
                guesses[key] = _relative_selector(candidate, node)
                break

    return guesses


def detect_pagination(soup: BeautifulSoup) -> str:
    """Selettore del link "pagina successiva", se riconoscibile."""
    for link in soup.find_all("a", href=True):
        blob = (
            " ".join(link.get("class") or [])
            + " "
            + (link.get("rel") and " ".join(link.get("rel")) or "")
            + " "
            + link.get_text(" ", strip=True)
        ).lower()
        if any(word in blob for word in ("next", "success", "avanti", "→", "»")):
            return _relative_selector(soup, link) if link.get("class") else "a[rel='next']"
    return ""


def report(html: str, source: str, limit: int = 3) -> str:
    """Analizza la pagina e produce il blocco YAML con l'anteprima dei dati."""
    soup = BeautifulSoup(html, "lxml")
    card_selector, cards = detect_card(soup)

    if not card_selector or not cards:
        return (
            "Nessuna griglia riconosciuta.\n"
            "Possibili cause: la pagina è renderizzata in JavaScript (usa\n"
            "http.engine: selenium), oppure i prezzi non sono nel formato atteso.\n"
            "Salva la pagina dal browser con 'Salva come > pagina completa' e riprova."
        )

    guesses = guess_selectors(cards)

    lines = [
        f"Pagina analizzata: {source}",
        f"Card trovate: {len(cards)}",
        "",
        "# ---- Blocco da incollare nel file di configurazione ----",
        "selectors:",
        f'  product_card: "{card_selector}"',
    ]
    for key in ("title", "url", "price", "image", "category", "out_of_stock_flag"):
        if key in guesses:
            lines.append(f'  {key}: "{guesses[key]}"')

    next_selector = detect_pagination(soup)
    if next_selector:
        lines += [
            "",
            "site:",
            "  pagination:",
            "    mode: link",
            f'    next_selector: "{next_selector}"',
        ]

    # Anteprima: mostra cosa estrarrebbero davvero questi selettori.
    lines += ["", "# ---- Anteprima dei primi prodotti ----"]
    for card in cards[:limit]:
        title_node = card.select_one(guesses["title"]) if "title" in guesses else None
        price_node = card.select_one(guesses["price"]) if "price" in guesses else None
        image_node = card.select_one(guesses["image"]) if "image" in guesses else None
        link_node = card.select_one(guesses["url"]) if "url" in guesses else None

        raw_price = price_node.get_text(" ", strip=True) if price_node else ""
        image_url = ""
        if isinstance(image_node, Tag):
            for attribute in ("data-srcset", "srcset", "data-src", "src"):
                value = image_node.get(attribute)
                if value:
                    image_url = str(value).split(",")[0].split()[0]
                    break

        lines += [
            f"  titolo:   {title_node.get_text(' ', strip=True) if title_node else '(non trovato)'}",
            f"  prezzo:   {raw_price or '(non trovato)'} -> {parse_price(raw_price)}",
            f"  link:     {link_node.get('href') if isinstance(link_node, Tag) else '(non trovato)'}",
            f"  immagine: {image_url or '(non trovata)'}",
            "",
        ]

    lines += [
        "# Le taglie stanno quasi sempre nella scheda prodotto, non nella griglia:",
        "# apri un prodotto, salva l'HTML e cerca il <select> o i bottoni taglia,",
        "# poi compila il blocco detail: (vedi config.example.yaml).",
    ]

    return "\n".join(lines)


def merge_into_config(path: Path, selectors: dict[str, str], next_selector: str = "") -> str:
    """Sostituisce il blocco `selectors:` nel file di configurazione.

    Lavora sul testo e non sull'albero YAML apposta: ricaricare e riscrivere
    con PyYAML cancellerebbe tutti i commenti del file, che qui servono.
    """
    testo = path.read_text(encoding="utf-8")
    righe = testo.splitlines()

    blocco = ["selectors:"]
    for chiave in ("product_card", "title", "url", "price", "sale_price", "image", "category", "sku", "out_of_stock_flag"):
        if chiave in selectors:
            blocco.append(f'  {chiave}: "{selectors[chiave]}"')

    inizio = next((i for i, r in enumerate(righe) if re.match(r"^selectors:\s*$", r)), None)

    if inizio is None:
        righe += ["", *blocco]
    else:
        fine = inizio + 1
        while fine < len(righe) and (righe[fine].startswith((" ", "\t")) or not righe[fine].strip()):
            fine += 1
        # Non inghiottire i commenti che introducono la sezione successiva.
        while fine > inizio + 1 and not righe[fine - 1].strip():
            fine -= 1
        righe[inizio:fine] = blocco

    # Il selettore di paginazione, se trovato, va aggiornato dov'è.
    if next_selector:
        for i, riga in enumerate(righe):
            if "next_selector:" in riga:
                indent = riga[: len(riga) - len(riga.lstrip())]
                righe[i] = f'{indent}next_selector: "{next_selector}"'
                break

    nuovo = "\n".join(righe) + "\n"
    path.write_text(nuovo, encoding="utf-8")
    return "\n".join(blocco)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="catalog_scraper.inspect",
        description="Suggerisce i selettori CSS di una pagina catalogo.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--html-file", help="Pagina salvata in locale")
    source.add_argument("--url", help="Scarica la pagina (rispetta robots.txt)")
    parser.add_argument("--limit", type=int, default=3, help="Prodotti in anteprima")
    parser.add_argument(
        "--write-config",
        metavar="FILE",
        help="Scrive i selettori trovati dentro questo file di configurazione",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.html_file:
        html = Path(args.html_file).read_text(encoding="utf-8", errors="replace")
        origin = args.html_file
    else:
        from .fetchers import FetchError, build_fetcher

        try:
            with build_fetcher(HttpConfig()) as fetcher:
                html = fetcher.get(args.url)
        except FetchError as exc:
            logger.error("%s", exc)
            return 2
        origin = args.url

    print(report(html, origin, args.limit))

    if args.write_config:
        destinazione = Path(args.write_config)
        if not destinazione.exists():
            logger.error("File di configurazione inesistente: %s", destinazione)
            return 2

        soup = BeautifulSoup(html, "lxml")
        selettore, cards = detect_card(soup)
        if not selettore or not cards:
            logger.error("Nessun selettore da scrivere: la griglia non è stata riconosciuta.")
            return 1

        trovati = {"product_card": selettore, **guess_selectors(cards)}
        merge_into_config(destinazione, trovati, detect_pagination(soup))
        print(f"\nSelettori scritti in {destinazione}. Rileggili prima di lanciare lo scraper.")

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
