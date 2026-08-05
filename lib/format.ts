import { shop } from './config';

const formatter = new Intl.NumberFormat(shop.locale, {
  style: 'currency',
  currency: shop.currency,
});

/** "€ 59,90". Lo spazio unificatore diventa normale: in chat si legge meglio. */
export function formatPrice(value: number): string {
  return formatter.format(value).replace(/ /g, ' ');
}

/** Percentuale di sconto arrotondata, o null se non c'è sconto. */
export function discountPercent(price: number | null, listPrice: number | null): number | null {
  if (price === null || listPrice === null || listPrice <= price) return null;
  return Math.round(((listPrice - price) / listPrice) * 100);
}
