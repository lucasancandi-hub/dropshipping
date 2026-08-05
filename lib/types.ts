/**
 * Contratto dati fra scraper e frontend.
 *
 * La forma è prodotta da `scraper/catalog_scraper/exporters/json_exporter.py`:
 * ogni modifica qui va replicata lì (e viceversa).
 */

export type Variant = {
  id: string;
  /** Valore mostrato all'utente: "M", "42", "Unica". */
  label: string;
  /** Nome dell'attributo: "Taglia", "Colore". */
  attribute: string;
  /** Prezzo specifico della variante; null = eredita quello del prodotto. */
  price: number | null;
  inStock: boolean;
  sku: string | null;
};

export type Product = {
  id: string;
  slug: string;
  title: string;
  category: string;
  /** null quando il prezzo va concordato in chat. */
  price: number | null;
  /** Prezzo pieno da barrare, presente solo se il prodotto è in saldo. */
  listPrice: number | null;
  priceOnRequest: boolean;
  currency: string;
  images: string[];
  variantLabel: string | null;
  variants: Variant[];
  sku: string | null;
  description: string;
  shortDescription: string;
  inStock: boolean;
  sourceUrl: string;
};

export type Catalog = {
  schemaVersion: number;
  generatedAt: string;
  currency: string;
  categories: string[];
  products: Product[];
};

/** Riga del carrello: prodotto + variante scelta. */
export type CartLine = {
  /** Chiave univoca della riga: `${productId}::${variantId ?? ''}`. */
  key: string;
  productId: string;
  slug: string;
  title: string;
  image: string | null;
  variantId: string | null;
  variantLabel: string | null;
  /** Prezzo unitario risolto; null = da concordare. */
  unitPrice: number | null;
  priceOnRequest: boolean;
  qty: number;
};

export type ShippingEstimate = {
  /** null quando la spedizione va concordata. */
  amount: number | null;
  label: string;
  onRequest: boolean;
  free: boolean;
};

export type CartTotals = {
  count: number;
  subtotal: number;
  shipping: ShippingEstimate;
  total: number;
  /** true se almeno una voce non ha prezzo: il totale è parziale. */
  hasOnRequest: boolean;
};
