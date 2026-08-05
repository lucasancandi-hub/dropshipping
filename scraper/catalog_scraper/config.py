"""Caricamento e validazione della configurazione YAML dello scraper.

Tutti i selettori CSS vivono nel file di config: cambiare sito significa
scrivere un nuovo YAML, mai toccare il codice.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


def _expand_env(value: Any) -> Any:
    """Espande ${VAR} e ${VAR:-default} ricorsivamente.

    Permette di tenere chiavi API fuori dal file di config versionato.
    """
    if isinstance(value, str):
        return _ENV_PATTERN.sub(
            lambda m: os.environ.get(m.group(1), m.group(2) or ""), value
        )
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


@dataclass
class PaginationConfig:
    mode: str = "none"  # none | query | link
    param: str = "page"
    start: int = 1
    step: int = 1
    max_pages: int = 1
    next_selector: str = ""


@dataclass
class SelectorConfig:
    """Selettori della pagina griglia (catalogo)."""

    product_card: str = ""
    title: str = ""
    url: str = ""
    price: str = ""
    sale_price: str = ""
    image: str = ""
    category: str = ""
    sku: str = ""
    out_of_stock_flag: str = ""


@dataclass
class DetailConfig:
    """Selettori della scheda prodotto (visitata solo se enabled)."""

    enabled: bool = False
    gallery: str = ""
    variants: str = ""
    variant_attribute: str = "Taglia"
    description: str = ""
    short_description: str = ""
    sku: str = ""
    category: str = ""
    price: str = ""
    max_products: int = 0  # 0 = nessun limite


@dataclass
class HttpConfig:
    engine: str = "requests"  # requests | selenium
    user_agent: str = (
        "Mozilla/5.0 (compatible; CatalogScraper/1.0; +https://example.com/bot)"
    )
    timeout: int = 20
    delay: float = 1.0  # secondi fra due richieste (rate limiting)
    retries: int = 3
    respect_robots: bool = True
    headers: dict[str, str] = field(default_factory=dict)
    # Solo engine=selenium
    headless: bool = True
    wait_selector: str = ""
    wait_timeout: int = 15
    scroll: bool = False
    scroll_pause: float = 1.0
    scroll_max: int = 10


@dataclass
class ParsingConfig:
    decimal_separator: str = ""  # "" = autodetect
    thousands_separator: str = ""
    currency: str = "EUR"
    default_category: str = "Non categorizzato"
    sku_prefix: str = "DS"
    image_attributes: list[str] = field(
        default_factory=lambda: ["data-srcset", "srcset", "data-src", "src"]
    )


@dataclass
class FeedMapping:
    """Da dove leggere ogni campo dentro un elemento del feed.

    I valori sono percorsi puntati: `price`, `meta.sku`, `images.0`.
    Lasciare vuoto un campo significa "questo feed non ce l'ha".
    """

    title: str = "title"
    price: str = "price"
    sale_price: str = ""
    # Percentuale di sconto già applicata dal fornitore (es. dummyjson):
    # se valorizzata, `price` è il prezzo pieno e il netto viene calcolato.
    discount_percent: str = ""
    category: str = "category"
    sku: str = "sku"
    description: str = "description"
    short_description: str = ""
    images: str = "images"      # array di URL
    image: str = ""             # oppure un singolo URL
    url: str = ""
    stock: str = "stock"        # numero, booleano o testo
    # Varianti: percorso all'array + campi al suo interno
    variants: str = ""
    variant_label: str = "size"
    variant_price: str = ""
    variant_stock: str = ""
    variant_sku: str = ""
    # Solo CSV: colonna con le taglie esaurite, se tenute separate.
    variants_out: str = ""


@dataclass
class FeedConfig:
    """Import da feed strutturato (JSON), alternativa al parsing HTML."""

    enabled: bool = False
    # json = API o file JSON, csv = foglio di calcolo esportato in CSV
    format: str = "json"
    url: str = ""
    file: str = ""
    # Solo CSV: "" = rileva da solo virgola o punto e virgola (Excel italiano)
    delimiter: str = ""
    # Solo CSV: separatore dentro una cella che contiene più valori
    list_separator: str = "|"
    # Percorso puntato all'array di prodotti: "" se la radice è già un array.
    root: str = "products"
    variant_attribute: str = "Taglia"
    # none | offset (aggiunge limit/skip come parametri di query)
    pagination_mode: str = "none"
    limit_param: str = "limit"
    offset_param: str = "skip"
    page_size: int = 30
    max_items: int = 0
    total_key: str = "total"
    mapping: "FeedMapping" = field(default_factory=lambda: FeedMapping())


@dataclass
class PricingConfig:
    """Ricarico applicato al prezzo del fornitore."""

    # Percentuale sul costo: 100 = raddoppia, 60 = +60%.
    markup_percent: float = 0.0
    # Override per categoria: {"Giacche": 80}
    category_markup: dict[str, float] = field(default_factory=dict)
    # Scaglioni sul costo: [{"above": 100, "percent": 50}]
    # Si applica lo scaglione con la soglia più alta raggiunta dal costo.
    price_tiers: list[dict[str, float]] = field(default_factory=list)
    # Costi che il prezzo del fornitore non comprende (spedizione in acquisto,
    # dogana, imballo): si sommano al costo PRIMA di applicare il ricarico,
    # altrimenti il margine reale è più basso di quello impostato.
    cost_surcharge_fixed: float = 0.0
    cost_surcharge_percent: float = 0.0
    rounding: str = "none"  # none | integer | charm
    charm_ending: float = 0.90
    min_price: float = 0.0
    # Il JSON finisce nel bundle pubblico: tenere il costo fuori è il default.
    include_cost_in_output: bool = False


@dataclass
class SiteConfig:
    name: str = "catalogo"
    base_url: str = ""
    catalog_url: str = ""
    pagination: PaginationConfig = field(default_factory=PaginationConfig)


def _build_feed(raw: dict[str, Any]) -> FeedConfig:
    """FeedConfig con il mapping annidato."""
    raw = dict(raw)
    mapping = FeedMapping(**(raw.pop("mapping", None) or {}))
    return FeedConfig(**raw, mapping=mapping)


@dataclass
class ScraperConfig:
    site: SiteConfig = field(default_factory=SiteConfig)
    selectors: SelectorConfig = field(default_factory=SelectorConfig)
    detail: DetailConfig = field(default_factory=DetailConfig)
    http: HttpConfig = field(default_factory=HttpConfig)
    parsing: ParsingConfig = field(default_factory=ParsingConfig)
    pricing: PricingConfig = field(default_factory=PricingConfig)
    feed: FeedConfig = field(default_factory=FeedConfig)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ScraperConfig":
        raw = _expand_env(raw or {})
        site_raw = dict(raw.get("site") or {})
        pagination = PaginationConfig(**(site_raw.pop("pagination", None) or {}))
        return cls(
            site=SiteConfig(**site_raw, pagination=pagination),
            selectors=SelectorConfig(**(raw.get("selectors") or {})),
            detail=DetailConfig(**(raw.get("detail") or {})),
            http=HttpConfig(**(raw.get("http") or {})),
            parsing=ParsingConfig(**(raw.get("parsing") or {})),
            pricing=PricingConfig(**(raw.get("pricing") or {})),
            feed=_build_feed(raw.get("feed") or {}),
        )

    @classmethod
    def load(cls, path: str | Path) -> "ScraperConfig":
        with open(path, "r", encoding="utf-8") as handle:
            return cls.from_dict(yaml.safe_load(handle) or {})

    def validate(self) -> None:
        errors: list[str] = []

        # In modalità feed i selettori CSS non hanno senso: si valida altro.
        if self.feed.enabled:
            if not (self.feed.url or self.feed.file):
                errors.append("feed.url oppure feed.file è obbligatorio")
            if self.feed.format not in {"json", "csv"}:
                errors.append("feed.format deve essere 'json' o 'csv'")
            if self.feed.format == "csv" and not self.feed.file:
                errors.append("feed.file è obbligatorio con format: csv")
            if self.feed.pagination_mode not in {"none", "offset"}:
                errors.append("feed.pagination_mode deve essere 'none' o 'offset'")
            if not self.feed.mapping.title:
                errors.append("feed.mapping.title è obbligatorio")
            if self.pricing.rounding not in {"none", "integer", "charm"}:
                errors.append("pricing.rounding deve essere 'none', 'integer' o 'charm'")
            if errors:
                raise ValueError("Configurazione non valida:\n- " + "\n- ".join(errors))
            return

        if not self.site.catalog_url:
            errors.append("site.catalog_url è obbligatorio")
        if not self.selectors.product_card:
            errors.append("selectors.product_card è obbligatorio")
        if not self.selectors.title:
            errors.append("selectors.title è obbligatorio")
        if self.http.engine not in {"requests", "selenium"}:
            errors.append("http.engine deve essere 'requests' o 'selenium'")
        if self.site.pagination.mode not in {"none", "query", "link"}:
            errors.append("site.pagination.mode deve essere 'none', 'query' o 'link'")
        if self.pricing.rounding not in {"none", "integer", "charm"}:
            errors.append("pricing.rounding deve essere 'none', 'integer' o 'charm'")
        if self.pricing.markup_percent < 0:
            errors.append("pricing.markup_percent non può essere negativo")
        if errors:
            raise ValueError("Configurazione non valida:\n- " + "\n- ".join(errors))
