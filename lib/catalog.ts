/**
 * Accesso al catalogo.
 *
 * Il JSON è importato staticamente: Next lo inlinea nel bundle a build time,
 * quindi le pagine sono generate staticamente e non c'è nessuna lettura da
 * filesystem né chiamata di rete a runtime.
 *
 * Per aggiornare il catalogo: rilanciare lo scraper, committare
 * `data/products.json`, e Vercel ricostruisce.
 */

import catalogData from '@/data/products.json';
import type { Catalog, Product } from './types';

export const catalog = catalogData as Catalog;

export function getProducts(): Product[] {
  return catalog.products;
}

export function getCategories(): string[] {
  return catalog.categories;
}

export function getProductBySlug(slug: string): Product | undefined {
  return catalog.products.find((product) => product.slug === slug);
}

/** Prodotti della stessa categoria, escluso quello corrente. */
export function getRelated(product: Product, limit = 4): Product[] {
  return catalog.products
    .filter((item) => item.slug !== product.slug && item.category === product.category)
    .slice(0, limit);
}
