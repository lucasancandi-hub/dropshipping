"""Parsing HTML -> `Product`, guidato dai selettori CSS di configurazione.

Nessun selettore è hard-coded: `CatalogParser` legge tutto da `ScraperConfig`,
così lo stesso codice serve una griglia Shopify, WooCommerce o custom.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from .config import DetailConfig, ParsingConfig, ScraperConfig, SelectorConfig
from .models import Product, Variant

logger = logging.getLogger(__name__)

_PRICE_PATTERN = re.compile(r"[-+]?\d[\d.,\s ']*\d|\d")
_CURRENCY_SYMBOLS = {"€": "EUR", "$": "USD", "£": "GBP", "¥": "JPY", "CHF": "CHF"}
# Voci che i menu a tendina usano come placeholder, non come variante reale
_PLACEHOLDER_VALUES = {"", "-", "--", "taglia", "size", "opzione", "option"}
_PLACEHOLDER_PATTERN = re.compile(
    r"^(seleziona|scegli|scegliere|select|choose|pick)\b", re.IGNORECASE
)


def _is_placeholder(node: Tag, value: str) -> bool:
    """Un `<option value="">` o un testo tipo "Seleziona una taglia"."""
    if node.name == "option" and node.has_attr("value") and not node["value"].strip():
        return True
    return (
        value.strip().lower() in _PLACEHOLDER_VALUES
        or bool(_PLACEHOLDER_PATTERN.match(value.strip()))
    )


def parse_price(text: str | None, parsing: ParsingConfig | None = None) -> float | None:
    """Estrae un float da '€ 1.234,56', '$1,234.56', 'da 19,90 EUR'.

    Se i separatori non sono configurati, li deduce dalla posizione:
    l'ultimo separatore seguito da 1-2 cifre è il decimale.
    """
    if not text:
        return None
    cleaned = text.replace(" ", " ").strip()
    match = _PRICE_PATTERN.search(cleaned)
    if not match:
        return None

    raw = re.sub(r"[\s ']", "", match.group(0))
    decimal_sep = parsing.decimal_separator if parsing else ""
    thousands_sep = parsing.thousands_separator if parsing else ""

    if decimal_sep:
        raw = raw.replace(thousands_sep, "") if thousands_sep else raw
        raw = raw.replace(decimal_sep, ".")
    else:
        # Autodetect: l'ultimo fra . e , con <= 2 decimali è il separatore decimale
        last_dot, last_comma = raw.rfind("."), raw.rfind(",")
        sep_index = max(last_dot, last_comma)
        if sep_index == -1:
            pass  # solo cifre
        elif len(raw) - sep_index - 1 in (1, 2):
            integer = re.sub(r"[.,]", "", raw[:sep_index])
            raw = f"{integer}.{raw[sep_index + 1:]}"
        else:
            raw = re.sub(r"[.,]", "", raw)  # separatore di migliaia

    try:
        return round(float(raw), 2)
    except ValueError:
        logger.debug("Prezzo non interpretabile: %r", text)
        return None


def detect_currency(text: str | None, fallback: str = "EUR") -> str:
    if not text:
        return fallback
    upper = text.upper()
    for symbol, code in _CURRENCY_SYMBOLS.items():
        if symbol in text or symbol in upper:
            return code
    for code in ("EUR", "USD", "GBP"):
        if code in upper:
            return code
    return fallback


def _text_of(node: Tag | None) -> str:
    return node.get_text(" ", strip=True) if node else ""


def _select_one(scope: Tag, selector: str) -> Tag | None:
    return scope.select_one(selector) if selector else None


def _select(scope: Tag, selector: str) -> list[Tag]:
    return scope.select(selector) if selector else []


def _best_from_srcset(value: str) -> str:
    """Da un srcset restituisce l'URL con la larghezza dichiarata più alta."""
    best_url, best_width = "", -1
    for candidate in value.split(","):
        parts = candidate.strip().split()
        if not parts:
            continue
        url = parts[0]
        width = -1
        if len(parts) > 1 and parts[1].endswith("w"):
            try:
                width = int(parts[1][:-1])
            except ValueError:
                width = -1
        if width > best_width:
            best_url, best_width = url, width
    return best_url


def extract_image_url(node: Tag, parsing: ParsingConfig, base_url: str) -> str:
    """Gestisce lazy-loading (`data-src`), `srcset` e `<source>` dentro `<picture>`."""
    if node.name == "picture":
        source = node.find("source")
        if isinstance(source, Tag):
            node = source
    for attribute in parsing.image_attributes:
        value = node.get(attribute)
        if not value:
            continue
        if isinstance(value, list):
            value = value[0]
        url = _best_from_srcset(value) if "srcset" in attribute else value.strip()
        if url and not url.startswith("data:"):
            return urljoin(base_url, url)
    style = node.get("style", "")
    background = re.search(r"url\(['\"]?(?P<url>[^'\")]+)", style or "")
    if background:
        return urljoin(base_url, background.group("url"))
    return ""


class CatalogParser:
    """Traduce l'HTML in `Product` usando i selettori del file di config."""

    def __init__(self, config: ScraperConfig) -> None:
        self.config = config
        self.selectors: SelectorConfig = config.selectors
        self.detail: DetailConfig = config.detail
        self.parsing: ParsingConfig = config.parsing
        self.base_url = config.site.base_url or config.site.catalog_url

    # ------------------------------------------------------------------ #
    # Pagina griglia
    # ------------------------------------------------------------------ #
    def parse_catalog(self, html: str, page_url: str = "") -> list[Product]:
        soup = BeautifulSoup(html, "lxml")
        base = page_url or self.base_url
        cards = soup.select(self.selectors.product_card)
        logger.info("Trovate %d card in %s", len(cards), base or "documento")

        products: list[Product] = []
        for card in cards:
            product = self.parse_card(card, base)
            if product and product.is_valid():
                products.append(product)
            elif product:
                logger.debug("Card scartata (dati insufficienti): %r", product.title)
        return products

    def parse_card(self, card: Tag, base_url: str) -> Product | None:
        title = _text_of(_select_one(card, self.selectors.title))
        if not title:
            return None

        price_text = _text_of(_select_one(card, self.selectors.price))
        sale_text = _text_of(_select_one(card, self.selectors.sale_price))
        price = parse_price(price_text, self.parsing)
        sale_price = parse_price(sale_text, self.parsing)
        # Se il tema espone prezzo pieno e scontato invertiti, normalizziamo
        if sale_price is not None and price is not None and sale_price > price:
            price, sale_price = sale_price, price

        link = _select_one(card, self.selectors.url) or (
            card if card.name == "a" else card.find("a")
        )
        href = link.get("href") if isinstance(link, Tag) else None
        url = urljoin(base_url, href) if href else ""

        category = _text_of(_select_one(card, self.selectors.category))
        images = [
            image_url
            for node in _select(card, self.selectors.image)
            if (image_url := extract_image_url(node, self.parsing, base_url))
        ]

        product = Product(
            title=title,
            url=url,
            price=price,
            sale_price=sale_price,
            currency=detect_currency(price_text or sale_text, self.parsing.currency),
            categories=[category] if category else [self.parsing.default_category],
            images=list(dict.fromkeys(images)),  # dedup mantenendo l'ordine
            sku=_text_of(_select_one(card, self.selectors.sku)) or None,
            in_stock=not bool(_select_one(card, self.selectors.out_of_stock_flag)),
            source=base_url,
        )
        product.ensure_sku(self.parsing.sku_prefix)
        return product

    # ------------------------------------------------------------------ #
    # Scheda prodotto (arricchimento)
    # ------------------------------------------------------------------ #
    def enrich_from_detail(self, product: Product, html: str) -> Product:
        """Aggiunge galleria completa, varianti, descrizione e SKU reale."""
        soup = BeautifulSoup(html, "lxml")
        base = product.url or self.base_url

        gallery = [
            image_url
            for node in _select(soup, self.detail.gallery)
            if (image_url := extract_image_url(node, self.parsing, base))
        ]
        if gallery:
            product.images = list(dict.fromkeys(product.images + gallery))

        if self.detail.price and product.price is None:
            product.price = parse_price(
                _text_of(_select_one(soup, self.detail.price)), self.parsing
            )

        if self.detail.description:
            product.description = _text_of(_select_one(soup, self.detail.description))
        if self.detail.short_description:
            product.short_description = _text_of(
                _select_one(soup, self.detail.short_description)
            )
        if self.detail.sku:
            product.sku = (
                _text_of(_select_one(soup, self.detail.sku)) or product.sku
            )
        if self.detail.category:
            category = _text_of(_select_one(soup, self.detail.category))
            if category and category not in product.categories:
                product.categories = [category]

        product.variants = self.parse_variants(soup)
        return product

    def parse_variants(self, soup: BeautifulSoup) -> list[Variant]:
        """Legge `<option>`, swatch o bottoni taglia dichiarati in `detail.variants`."""
        variants: list[Variant] = []
        seen: set[str] = set()

        for node in _select(soup, self.detail.variants):
            value = (
                node.get("data-value")
                or node.get("value")
                or node.get("title")
                or _text_of(node)
            )
            value = (value or "").strip()
            if not value or value in seen or _is_placeholder(node, value):
                continue
            seen.add(value)

            disabled = (
                node.has_attr("disabled")
                or "disabled" in " ".join(node.get("class") or [])
                or node.get("aria-disabled") == "true"
                or str(node.get("data-available", "")).lower() == "false"
            )
            variants.append(
                Variant(
                    attribute=self.detail.variant_attribute,
                    value=value,
                    sku=node.get("data-sku"),
                    price=parse_price(node.get("data-price"), self.parsing),
                    in_stock=not disabled,
                )
            )
        return variants

    # ------------------------------------------------------------------ #
    # Paginazione
    # ------------------------------------------------------------------ #
    def find_next_page(self, html: str, current_url: str) -> str | None:
        selector = self.config.site.pagination.next_selector
        if not selector:
            return None
        node = BeautifulSoup(html, "lxml").select_one(selector)
        href = node.get("href") if isinstance(node, Tag) else None
        return urljoin(current_url, href) if href else None
