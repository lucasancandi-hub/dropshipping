import { labels, shipping } from './config';
import { formatPrice } from './format';
import type { CartLine, CartTotals, ShippingEstimate } from './types';

/**
 * Stima della spedizione sul contenuto del carrello.
 *
 * Non è un calcolo definitivo: è la cifra mostrata a schermo e scritta nel
 * messaggio, che viene confermata in conversazione.
 */
export function estimateShipping(lines: CartLine[], subtotal: number): ShippingEstimate {
  if (lines.length === 0 || shipping.mode === 'none') {
    return { amount: null, label: labels.shippingOnRequest, onRequest: true, free: false };
  }

  if (shipping.freeOver > 0 && subtotal >= shipping.freeOver) {
    return { amount: 0, label: labels.shippingFree, onRequest: false, free: true };
  }

  const pieces = lines.reduce((total, line) => total + line.qty, 0);
  const amount =
    shipping.mode === 'quantity'
      ? shipping.base + shipping.perItem * pieces
      : shipping.flat;

  const rounded = Math.max(0, Math.round(amount * 100) / 100);

  return {
    amount: rounded,
    label: rounded === 0 ? labels.shippingFree : formatPrice(rounded),
    onRequest: false,
    free: rounded === 0,
  };
}

/** Totali completi del carrello, spedizione inclusa. */
export function computeTotals(lines: CartLine[]): CartTotals {
  let subtotal = 0;
  let count = 0;
  let hasOnRequest = false;

  for (const line of lines) {
    count += line.qty;
    if (line.priceOnRequest || line.unitPrice === null) {
      hasOnRequest = true;
    } else {
      subtotal += line.unitPrice * line.qty;
    }
  }

  subtotal = Math.round(subtotal * 100) / 100;
  const estimate = estimateShipping(lines, subtotal);
  const total = Math.round((subtotal + (estimate.amount ?? 0)) * 100) / 100;

  return { count, subtotal, shipping: estimate, total, hasOnRequest };
}

/** Etichetta del totale: segnala se restano voci senza prezzo. */
export function totalLabel(totals: CartTotals): string {
  const base = formatPrice(totals.total);
  return totals.hasOnRequest || totals.shipping.onRequest
    ? `${base} ${labels.partialTotal}`
    : base;
}

/** Descrizione della regola attiva, mostrata sotto la stima. */
export function shippingRuleLabel(): string {
  switch (shipping.mode) {
    case 'quantity':
      return `Stima: ${formatPrice(shipping.perItem)} per articolo`;
    case 'none':
      return 'Definita in chat';
    default:
      return shipping.freeOver > 0
        ? `Gratuita oltre ${formatPrice(shipping.freeOver)}`
        : 'Tariffa fissa';
  }
}
