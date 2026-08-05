"""catalog_scraper - ingestion catalogo -> WooCommerce (CSV o REST API)."""

from .config import ScraperConfig
from .models import Product, Variant
from .parser import CatalogParser, parse_price
from .scraper import CatalogScraper

__version__ = "1.0.0"

__all__ = [
    "ScraperConfig",
    "Product",
    "Variant",
    "CatalogParser",
    "CatalogScraper",
    "parse_price",
    "__version__",
]
