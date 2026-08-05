"""Import da sorgenti strutturate (feed), alternativa al parsing HTML."""

from .json_feed import import_feed, item_to_product, resolve

__all__ = ["import_feed", "item_to_product", "resolve"]
