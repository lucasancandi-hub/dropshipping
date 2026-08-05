"""Orchestratore: paginazione, deduplica e arricchimento dalle schede prodotto."""

from __future__ import annotations

import logging
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .config import ScraperConfig
from .fetchers import BaseFetcher, FetchError, build_fetcher
from .models import Product
from .parser import CatalogParser

logger = logging.getLogger(__name__)


def _with_query_param(url: str, param: str, value: int | str) -> str:
    parts = urlparse(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query[param] = str(value)
    return urlunparse(parts._replace(query=urlencode(query)))


class CatalogScraper:
    """Punto d'ingresso unico: `CatalogScraper(config).run()` -> list[Product]."""

    def __init__(
        self, config: ScraperConfig, fetcher: BaseFetcher | None = None
    ) -> None:
        config.validate()
        self.config = config
        self.parser = CatalogParser(config)
        self._fetcher = fetcher
        self._owns_fetcher = fetcher is None

    @property
    def fetcher(self) -> BaseFetcher:
        if self._fetcher is None:
            self._fetcher = build_fetcher(self.config.http)
        return self._fetcher

    def close(self) -> None:
        if self._fetcher is not None and self._owns_fetcher:
            self._fetcher.close()
            self._fetcher = None

    def __enter__(self) -> "CatalogScraper":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    def run(self) -> list[Product]:
        products = self.scrape_catalog()
        if self.config.detail.enabled:
            products = self.enrich(products)
        return products

    def scrape_catalog(self) -> list[Product]:
        """Scorre le pagine griglia e deduplica per URL (o titolo se manca l'URL)."""
        pagination = self.config.site.pagination
        collected: dict[str, Product] = {}

        url: str | None = self.config.site.catalog_url
        for page_index in range(pagination.max_pages or 1):
            if not url:
                break
            page_url = url
            if pagination.mode == "query":
                page_url = _with_query_param(
                    self.config.site.catalog_url,
                    pagination.param,
                    pagination.start + page_index * pagination.step,
                )

            try:
                html = self.fetcher.get(page_url)
            except FetchError as exc:
                logger.error("Pagina %s saltata: %s", page_url, exc)
                break

            page_products = self.parser.parse_catalog(html, page_url)
            if not page_products:
                logger.info("Nessun prodotto in %s: fine paginazione.", page_url)
                break

            new_items = 0
            for product in page_products:
                key = product.url or product.title
                if key not in collected:
                    collected[key] = product
                    new_items += 1
            logger.info(
                "Pagina %d: %d prodotti (%d nuovi, %d totali)",
                page_index + 1,
                len(page_products),
                new_items,
                len(collected),
            )
            if new_items == 0:
                logger.info("Solo duplicati: interrompo la paginazione.")
                break

            if pagination.mode == "link":
                url = self.parser.find_next_page(html, page_url)
            elif pagination.mode == "none":
                url = None

        return list(collected.values())

    def enrich(self, products: list[Product]) -> list[Product]:
        """Visita ogni scheda prodotto per galleria completa e varianti."""
        limit = self.config.detail.max_products or len(products)
        for index, product in enumerate(products[:limit], start=1):
            if not product.url:
                continue
            try:
                html = self.fetcher.get(product.url)
            except FetchError as exc:
                logger.warning("Dettaglio non recuperato per %s: %s", product.url, exc)
                continue
            self.parser.enrich_from_detail(product, html)
            logger.info(
                "[%d/%d] %s -> %d immagini, %d varianti",
                index,
                limit,
                product.title,
                len(product.images),
                len(product.variants),
            )
        return products
