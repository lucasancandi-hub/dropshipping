"""Client REST API WooCommerce v3: upsert idempotente dei prodotti.

Autenticazione Basic con consumer key/secret (richiede HTTPS).
Genera: WooCommerce > Impostazioni > Avanzate > REST API > Aggiungi chiave
(permessi: Lettura/Scrittura).

L'upsert usa lo SKU come chiave naturale: rilanciare lo script aggiorna i
prodotti esistenti invece di duplicarli.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

import requests
from requests.auth import HTTPBasicAuth

from ..config import WooConfig
from ..models import Product

logger = logging.getLogger(__name__)


class WooCommerceError(RuntimeError):
    """Errore restituito dall'API WooCommerce."""


class WooCommerceClient:
    def __init__(self, config: WooConfig) -> None:
        if not config.url:
            raise WooCommerceError("woocommerce.url mancante in configurazione")
        if not (config.consumer_key and config.consumer_secret):
            raise WooCommerceError(
                "Credenziali mancanti: imposta WOO_CONSUMER_KEY / WOO_CONSUMER_SECRET"
            )
        if not config.url.startswith("https://"):
            # Su HTTP la Basic Auth di WooCommerce viaggia in chiaro
            raise WooCommerceError("woocommerce.url deve usare HTTPS")

        self.config = config
        self.base = config.url.rstrip("/") + "/wp-json/wc/v3"
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(config.consumer_key, config.consumer_secret)
        self.session.headers.update({"Accept": "application/json"})
        self._category_cache: dict[str, int] = {}

    # ------------------------------------------------------------------ #
    # HTTP
    # ------------------------------------------------------------------ #
    def _request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        url = f"{self.base}/{endpoint.lstrip('/')}"
        response = self.session.request(
            method,
            url,
            timeout=self.config.timeout,
            verify=self.config.verify_ssl,
            **kwargs,
        )
        if response.status_code >= 400:
            raise WooCommerceError(
                f"{method} {endpoint} -> {response.status_code}: {response.text[:500]}"
            )
        return response.json() if response.content else None

    # ------------------------------------------------------------------ #
    # Categorie
    # ------------------------------------------------------------------ #
    def resolve_category(self, name: str) -> int | None:
        """Restituisce l'ID categoria, creandola se non esiste (con cache)."""
        key = name.strip().lower()
        if not key:
            return None
        if key in self._category_cache:
            return self._category_cache[key]

        existing = self._request(
            "GET", "products/categories", params={"search": name, "per_page": 100}
        )
        for category in existing or []:
            if category.get("name", "").strip().lower() == key:
                self._category_cache[key] = category["id"]
                return category["id"]

        created = self._request("POST", "products/categories", json={"name": name})
        self._category_cache[key] = created["id"]
        logger.info("Categoria creata: %s (id=%s)", name, created["id"])
        return created["id"]

    # ------------------------------------------------------------------ #
    # Prodotti
    # ------------------------------------------------------------------ #
    def find_by_sku(self, sku: str) -> dict[str, Any] | None:
        results = self._request("GET", "products", params={"sku": sku})
        return results[0] if results else None

    def build_payload(self, product: Product) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": product.title,
            "sku": product.ensure_sku(),
            "type": "variable" if product.is_variable else "simple",
            "status": self.config.status,
            "catalog_visibility": "visible",
            "description": product.description,
            "short_description": product.short_description,
            "images": [{"src": url} for url in product.images[:10]],
            "categories": [
                {"id": category_id}
                for name in product.categories
                if (category_id := self.resolve_category(name))
            ],
            "meta_data": [{"key": "_source_url", "value": product.url}],
        }

        if not product.is_variable:
            payload["regular_price"] = (
                f"{product.price:.2f}" if product.price is not None else ""
            )
            if product.sale_price is not None:
                payload["sale_price"] = f"{product.sale_price:.2f}"
            payload["manage_stock"] = self.config.manage_stock
            payload["stock_status"] = "instock" if product.in_stock else "outofstock"
        else:
            payload["attributes"] = [
                {
                    "name": name,
                    "position": index,
                    "visible": True,
                    "variation": True,
                    "options": values,
                }
                for index, (name, values) in enumerate(product.attributes.items())
            ]
        return payload

    def upsert_product(self, product: Product) -> dict[str, Any]:
        """Crea o aggiorna il prodotto (chiave: SKU) e sincronizza le varianti."""
        sku = product.ensure_sku()
        existing = self.find_by_sku(sku)
        payload = self.build_payload(product)

        if existing:
            # Le immagini già caricate non vanno ri-sideloaded a ogni run
            payload.pop("images", None)
            remote = self._request("PUT", f"products/{existing['id']}", json=payload)
            logger.info("Aggiornato #%s %s", remote["id"], product.title)
        else:
            remote = self._request("POST", "products", json=payload)
            logger.info("Creato #%s %s", remote["id"], product.title)

        if product.is_variable:
            self.sync_variations(remote["id"], product)
        return remote

    def sync_variations(self, product_id: int, product: Product) -> None:
        """Batch create/update delle varianti; elimina quelle non più a catalogo."""
        current = self._request(
            "GET", f"products/{product_id}/variations", params={"per_page": 100}
        ) or []
        by_sku = {item.get("sku"): item for item in current}

        create: list[dict[str, Any]] = []
        update: list[dict[str, Any]] = []
        keep_ids: set[int] = set()

        base_price = product.effective_price
        for variant in product.variants:
            variation_sku = variant.sku or f"{product.sku}-{variant.value.upper().replace(' ', '')}"
            price = variant.price if variant.price is not None else base_price
            body: dict[str, Any] = {
                "sku": variation_sku,
                "regular_price": f"{price:.2f}" if price is not None else "",
                "stock_status": "instock" if variant.in_stock else "outofstock",
                "attributes": [{"name": variant.attribute, "option": variant.value}],
            }
            match = by_sku.get(variation_sku)
            if match:
                body["id"] = match["id"]
                keep_ids.add(match["id"])
                update.append(body)
            else:
                create.append(body)

        # Varianti non più presenti a catalogo: rimosse per non lasciare orfani
        delete = [item["id"] for item in current if item["id"] not in keep_ids]

        batch = {"create": create, "update": update, "delete": delete}
        if any(batch.values()):
            self._request("POST", f"products/{product_id}/variations/batch", json=batch)
            logger.info(
                "Varianti #%s: +%d ~%d -%d",
                product_id,
                len(create),
                len(update),
                len(batch["delete"]),
            )


def push_to_woocommerce(
    products: Iterable[Product], config: WooConfig, dry_run: bool = False
) -> dict[str, int]:
    """Invia i prodotti a WooCommerce. Ritorna il conteggio esiti."""
    stats = {"ok": 0, "failed": 0, "skipped": 0}
    if dry_run:
        for product in products:
            logger.info(
                "[dry-run] %s (%s) - %s varianti",
                product.title,
                product.ensure_sku(),
                len(product.variants),
            )
            stats["skipped"] += 1
        return stats

    client = WooCommerceClient(config)
    for product in products:
        try:
            client.upsert_product(product)
            stats["ok"] += 1
        except WooCommerceError as exc:
            logger.error("Import fallito per %s: %s", product.title, exc)
            stats["failed"] += 1
    return stats
