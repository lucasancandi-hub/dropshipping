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
class SiteConfig:
    name: str = "catalogo"
    base_url: str = ""
    catalog_url: str = ""
    pagination: PaginationConfig = field(default_factory=PaginationConfig)


@dataclass
class WooConfig:
    """Credenziali REST API WooCommerce (chiavi generate da WooCommerce > Impostazioni > Avanzate)."""

    url: str = ""
    consumer_key: str = ""
    consumer_secret: str = ""
    timeout: int = 30
    status: str = "publish"
    manage_stock: bool = False
    verify_ssl: bool = True


@dataclass
class ScraperConfig:
    site: SiteConfig = field(default_factory=SiteConfig)
    selectors: SelectorConfig = field(default_factory=SelectorConfig)
    detail: DetailConfig = field(default_factory=DetailConfig)
    http: HttpConfig = field(default_factory=HttpConfig)
    parsing: ParsingConfig = field(default_factory=ParsingConfig)
    woocommerce: WooConfig = field(default_factory=WooConfig)

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
            woocommerce=WooConfig(**(raw.get("woocommerce") or {})),
        )

    @classmethod
    def load(cls, path: str | Path) -> "ScraperConfig":
        with open(path, "r", encoding="utf-8") as handle:
            return cls.from_dict(yaml.safe_load(handle) or {})

    def validate(self) -> None:
        errors: list[str] = []
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
        if errors:
            raise ValueError("Configurazione non valida:\n- " + "\n- ".join(errors))
