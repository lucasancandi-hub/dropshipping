/**
 * Configurazione del negozio.
 *
 * Tutto è sovrascrivibile da variabili d'ambiente (`.env.example`), ma i
 * default rendono il progetto deployabile su Vercel senza configurare nulla.
 */

const num = (value: string | undefined, fallback: number): number => {
  const parsed = Number.parseFloat(value ?? '');
  return Number.isFinite(parsed) ? parsed : fallback;
};

export type ShippingMode = 'flat' | 'quantity' | 'none';

const mode = process.env.NEXT_PUBLIC_SHIPPING_MODE;

export const shop = {
  name: process.env.NEXT_PUBLIC_SHOP_NAME || 'Atelier',
  /** Numero WhatsApp in formato internazionale, sole cifre. */
  whatsapp: (process.env.NEXT_PUBLIC_WHATSAPP_PHONE || '393408857026').replace(/\D/g, ''),
  locale: 'it-IT',
  currency: 'EUR',
} as const;

export const shipping = {
  mode: (mode === 'quantity' || mode === 'none' ? mode : 'flat') as ShippingMode,
  flat: num(process.env.NEXT_PUBLIC_SHIPPING_FLAT, 7.9),
  base: num(process.env.NEXT_PUBLIC_SHIPPING_BASE, 0),
  perItem: num(process.env.NEXT_PUBLIC_SHIPPING_PER_ITEM, 2),
  /** 0 disattiva la soglia di spedizione gratuita. */
  freeOver: num(process.env.NEXT_PUBLIC_SHIPPING_FREE_OVER, 99),
} as const;

export const order = {
  prefix: process.env.NEXT_PUBLIC_ORDER_PREFIX || 'ORD',
  digits: Math.min(8, Math.max(1, num(process.env.NEXT_PUBLIC_ORDER_DIGITS, 3))),
} as const;

export const labels = {
  priceOnRequest: 'Prezzo da concordare in chat',
  shippingOnRequest: 'Da concordare in chat',
  shippingFree: 'Gratuita',
  partialTotal: '(+ voci da concordare)',
} as const;
