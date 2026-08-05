"""Import da feed JSON.

È la strada da preferire quando il fornitore espone un'API o un file: i dati
arrivano già strutturati, non c'è nessun selettore CSS da indovinare e nulla si
rompe quando il fornitore ridisegna il sito.

Tutto è guidato dal blocco `feed:` del file di configurazione: `mapping`
associa i campi del fornitore a quelli del nostro modello, con percorsi puntati
(`price`, `meta.sku`, `images.0`).
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from ..config import FeedConfig, FeedMapping, ScraperConfig
from ..fetchers import BaseFetcher, FetchError, build_fetcher
from ..models import Product, Variant

logger = logging.getLogger(__name__)

# Testi che, in un campo di disponibilità, significano "non disponibile".
_OUT_OF_STOCK = {"out of stock", "outofstock", "esaurito", "non disponibile", "sold out", "0", "false", "no"}


def resolve(data: Any, path: str) -> Any:
    """Legge un valore seguendo un percorso puntato.

    Gli indici numerici entrano nelle liste: `images.0` prende la prima
    immagine. Un percorso che non esiste restituisce None invece di sollevare:
    un feed a cui manca un campo opzionale non deve fermare l'import.
    """
    if not path:
        return None

    current = data
    for chunk in path.split("."):
        if current is None:
            return None
        if isinstance(current, list):
            if not chunk.isdigit() or int(chunk) >= len(current):
                return None
            current = current[int(chunk)]
        elif isinstance(current, dict):
            current = current.get(chunk)
        else:
            return None
    return current


def _as_float(value: Any) -> float | None:
    """Numero da int/float/stringa ('19,90' e '19.90' vanno bene entrambi)."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    text = str(value).strip().replace("€", "").replace("$", "").strip()
    if not text:
        return None
    # Con entrambi i separatori l'ultimo è quello decimale.
    if "," in text and "." in text:
        text = text.replace(".", "") if text.rfind(",") > text.rfind(".") else text.replace(",", "")
    text = text.replace(",", ".")
    try:
        return round(float(text), 2)
    except ValueError:
        return None


def _as_price(value: Any) -> float | None:
    """Come `_as_float`, ma zero e negativi valgono "prezzo assente".

    Nei feed il campo prezzo a 0 significa quasi sempre "da definire": va
    trattato come mancante, non come merce regalata.
    """
    number = _as_float(value)
    return number if number is not None and number > 0 else None


def _as_stock(value: Any) -> bool:
    """Disponibilità da numero, booleano o testo. Assente = disponibile."""
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    return str(value).strip().lower() not in _OUT_OF_STOCK


def _as_images(item: dict[str, Any], mapping: FeedMapping) -> list[str]:
    """Lista di URL immagine, sia da un array sia da un campo singolo."""
    images: list[str] = []

    raw = resolve(item, mapping.images)
    if isinstance(raw, list):
        images.extend(str(url) for url in raw if url)
    elif isinstance(raw, str) and raw:
        images.append(raw)

    single = resolve(item, mapping.image)
    if isinstance(single, str) and single:
        images.append(single)

    # Ordine preservato, duplicati rimossi.
    return list(dict.fromkeys(images))


def _as_variants(item: dict[str, Any], feed: FeedConfig) -> list[Variant]:
    """Varianti/taglie, se il feed le espone come array."""
    mapping = feed.mapping
    raw = resolve(item, mapping.variants)
    if not isinstance(raw, list):
        return []

    variants: list[Variant] = []
    for entry in raw:
        # Un array di stringhe ("S", "M") è già la lista delle taglie.
        if isinstance(entry, str):
            label = entry.strip()
            if label:
                variants.append(Variant(attribute=feed.variant_attribute, value=label))
            continue

        if not isinstance(entry, dict):
            continue

        label = resolve(entry, mapping.variant_label)
        if not label:
            continue

        variants.append(
            Variant(
                attribute=feed.variant_attribute,
                value=str(label).strip(),
                price=_as_price(resolve(entry, mapping.variant_price)),
                in_stock=_as_stock(resolve(entry, mapping.variant_stock)),
                sku=(lambda s: str(s) if s else None)(resolve(entry, mapping.variant_sku)),
            )
        )

    return variants


def item_to_product(item: dict[str, Any], feed: FeedConfig, currency: str, sku_prefix: str) -> Product | None:
    """Un elemento del feed -> Product. None se manca il titolo."""
    mapping = feed.mapping

    title = resolve(item, mapping.title)
    if not title:
        return None

    price = _as_price(resolve(item, mapping.price))
    sale_price = _as_price(resolve(item, mapping.sale_price))

    # Sconto già applicato dal fornitore: `price` è il pieno, il netto si ricava.
    if sale_price is None and mapping.discount_percent:
        discount = _as_float(resolve(item, mapping.discount_percent))
        if discount and price is not None and 0 < discount < 100:
            sale_price = round(price * (1 - discount / 100), 2)

    category = resolve(item, mapping.category)
    sku = resolve(item, mapping.sku)

    product = Product(
        title=str(title).strip(),
        url=str(resolve(item, mapping.url) or ""),
        price=price,
        sale_price=sale_price,
        currency=currency,
        categories=[str(category).strip()] if category else [],
        images=_as_images(item, mapping),
        variants=_as_variants(item, feed),
        sku=str(sku).strip() if sku else None,
        description=str(resolve(item, mapping.description) or ""),
        short_description=str(resolve(item, mapping.short_description) or ""),
        in_stock=_as_stock(resolve(item, mapping.stock)),
        source=feed.url or feed.file,
    )
    product.ensure_sku(sku_prefix)
    return product


def _with_paging(url: str, feed: FeedConfig, offset: int) -> str:
    """Aggiunge limit/skip all'URL senza toccare gli altri parametri."""
    parts = urlparse(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query[feed.limit_param] = str(feed.page_size)
    query[feed.offset_param] = str(offset)
    return urlunparse(parts._replace(query=urlencode(query)))


def _load_page(fetcher: BaseFetcher, feed: FeedConfig, offset: int) -> Any:
    """Scarica (o legge) una pagina del feed e ne restituisce il JSON."""
    if feed.file:
        with open(feed.file, "r", encoding="utf-8") as handle:
            return json.load(handle)

    url = _with_paging(feed.url, feed, offset) if feed.pagination_mode == "offset" else feed.url
    raw = fetcher.get(url)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FetchError(f"Risposta non JSON da {url}: {exc}") from exc


def import_feed(config: ScraperConfig, fetcher: BaseFetcher | None = None) -> list[Product]:
    """Scarica il feed e restituisce i prodotti normalizzati."""
    feed = config.feed
    owns_fetcher = fetcher is None
    fetcher = fetcher or build_fetcher(config.http)

    products: list[Product] = []
    seen: set[str] = set()
    offset = 0

    try:
        while True:
            payload = _load_page(fetcher, feed, offset)

            items = resolve(payload, feed.root) if feed.root else payload
            if not isinstance(items, list):
                raise FetchError(
                    f"In '{feed.root or 'radice'}' non c'è un array di prodotti. "
                    "Controlla feed.root nella configurazione."
                )

            for item in items:
                if not isinstance(item, dict):
                    continue
                product = item_to_product(item, feed, config.parsing.currency, config.parsing.sku_prefix)
                if product is None or not product.is_valid():
                    continue
                if product.sku in seen:
                    continue
                seen.add(product.sku or "")
                products.append(product)

            logger.info("Feed: %d prodotti raccolti (offset %d)", len(products), offset)

            if feed.file or feed.pagination_mode != "offset":
                break
            if len(items) < feed.page_size:
                break
            if feed.max_items and len(products) >= feed.max_items:
                break

            total = resolve(payload, feed.total_key) if feed.total_key else None
            offset += feed.page_size
            if isinstance(total, int) and offset >= total:
                break
    finally:
        if owns_fetcher:
            fetcher.close()

    if feed.max_items:
        products = products[: feed.max_items]

    return products
