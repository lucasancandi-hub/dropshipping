"""Interfaccia a riga di comando.

    python -m catalog_scraper --config config.yaml --output out/catalogo.csv
    python -m catalog_scraper --config config.yaml --push --dry-run
    python -m catalog_scraper --config config.yaml --html-file pagina.html
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import ScraperConfig
from .exporters.csv_exporter import export_csv
from .exporters.woo_api import WooCommerceError, push_to_woocommerce
from .models import Product
from .parser import CatalogParser
from .scraper import CatalogScraper

logger = logging.getLogger("catalog_scraper")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="catalog_scraper",
        description="Estrae un catalogo prodotti e lo importa in WooCommerce.",
    )
    parser.add_argument("-c", "--config", required=True, help="File YAML di configurazione")
    parser.add_argument(
        "-o", "--output", default="", help="Percorso CSV di output (default: da config)"
    )
    parser.add_argument("--json", default="", help="Salva anche un dump JSON grezzo")
    parser.add_argument(
        "--push", action="store_true", help="Invia i prodotti alla REST API WooCommerce"
    )
    parser.add_argument(
        "--no-csv", action="store_true", help="Salta la scrittura del CSV"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Con --push: mostra cosa verrebbe inviato senza scrivere su WooCommerce",
    )
    parser.add_argument(
        "--html-file",
        default="",
        help="Analizza un HTML locale invece di scaricarlo (utile per testare i selettori)",
    )
    parser.add_argument("--limit", type=int, default=0, help="Massimo prodotti da elaborare")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Log di debug"
    )
    return parser


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _collect(args: argparse.Namespace, config: ScraperConfig) -> list[Product]:
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

    if args.limit:
        products = products[: args.limit]
    if not products:
        logger.warning("Nessun prodotto estratto: verifica i selettori CSS.")
        return 1

    logger.info(
        "Estratti %d prodotti (%d con varianti).",
        len(products),
        sum(1 for p in products if p.is_variable),
    )

    if not args.no_csv:
        output = Path(args.output or f"output/{config.site.name}.csv")
        export_csv(products, output)

    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps([p.as_dict() for p in products], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("JSON scritto in %s", destination)

    if args.push:
        try:
            stats = push_to_woocommerce(products, config.woocommerce, args.dry_run)
        except WooCommerceError as exc:
            logger.error("%s", exc)
            return 3
        logger.info(
            "Import WooCommerce: %d ok, %d falliti, %d saltati",
            stats["ok"],
            stats["failed"],
            stats["skipped"],
        )
        if stats["failed"]:
            return 4

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
