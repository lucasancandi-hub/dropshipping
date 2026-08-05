"""Interfaccia a riga di comando.

    python -m catalog_scraper --config config.yaml
    python -m catalog_scraper --config config.yaml --html-file pagina.html -v
    python -m catalog_scraper --config config.yaml -o ../data/products.json

L'output alimenta direttamente il frontend: dopo un run basta un commit e
Vercel ricostruisce il sito con il catalogo aggiornato.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import ScraperConfig
from .exporters.json_exporter import export_json
from .importers.json_feed import import_feed
from .models import Product
from .pricing import apply_pricing
from .parser import CatalogParser
from .scraper import CatalogScraper

logger = logging.getLogger("catalog_scraper")

# Percorso di default: <repo>/data/products.json
DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "data" / "products.json"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="catalog_scraper",
        description="Estrae un catalogo prodotti e lo salva in JSON per il frontend.",
    )
    parser.add_argument("-c", "--config", required=True, help="File YAML di configurazione")
    parser.add_argument(
        "-o",
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"Percorso del JSON di output (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--html-file",
        default="",
        help="Analizza un HTML locale invece di scaricarlo (utile per tarare i selettori)",
    )
    parser.add_argument("--limit", type=int, default=0, help="Massimo prodotti da elaborare")
    parser.add_argument(
        "--markup",
        type=float,
        default=None,
        help="Ricarico percentuale sul prezzo fornitore (sovrascrive pricing.markup_percent)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra cosa verrebbe scritto senza toccare il file",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Log di debug")
    return parser


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _collect(args: argparse.Namespace, config: ScraperConfig) -> list[Product]:
    # Feed strutturato: nessun selettore CSS di mezzo.
    if config.feed.enabled:
        products = import_feed(config)
        logger.info("Importati %d prodotti dal feed.", len(products))
        return products

    if args.html_file:
        html = Path(args.html_file).read_text(encoding="utf-8")
        products = CatalogParser(config).parse_catalog(html, config.site.catalog_url)
        logger.info("Parsati %d prodotti da %s", len(products), args.html_file)
        return products

    with CatalogScraper(config) as scraper:
        return scraper.run()


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    _configure_logging(args.verbose)

    try:
        config = ScraperConfig.load(args.config)
        products = _collect(args, config)
    except (ValueError, OSError) as exc:
        logger.error("%s", exc)
        return 2

    # Il flag da riga di comando ha la precedenza sul file di configurazione.
    if args.markup is not None:
        if args.markup < 0:
            logger.error("Il ricarico non può essere negativo.")
            return 2
        config.pricing.markup_percent = args.markup

    if args.limit:
        products = products[: args.limit]
    if not products:
        logger.warning("Nessun prodotto estratto: verifica i selettori CSS.")
        return 1

    logger.info(
        "Estratti %d prodotti (%d con varianti, %d senza prezzo).",
        len(products),
        sum(1 for p in products if p.is_variable),
        sum(1 for p in products if p.effective_price is None),
    )

    apply_pricing(products, config.pricing)

    if args.dry_run:
        for product in products:
            cost = product.extra.get("cost_price")
            logger.info(
                "[dry-run] %-34s costo %-9s -> vendita %-9s | %d varianti | %d immagini",
                product.title[:34],
                f"{cost:.2f}" if cost is not None else "n/d",
                f"{product.effective_price:.2f}"
                if product.effective_price is not None
                else "da concordare",
                len(product.variants),
                len(product.images),
            )
        return 0

    export_json(products, args.output, config.pricing.include_cost_in_output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
