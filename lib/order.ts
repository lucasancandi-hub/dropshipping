/**
 * Numero d'ordine progressivo, messaggio precompilato e link WhatsApp.
 *
 * Il numero viene dal contatore condiviso (`/api/order-number`) quando il
 * progetto ha uno store KV collegato; altrimenti si ripiega su un contatore
 * per browser in localStorage. In entrambi i casi il formato è lo stesso:
 * ORD-2026-001.
 */

import { labels, order, shop } from './config';
import { formatPrice } from './format';
import { totalLabel } from './shipping';
import type { CartLine, CartTotals } from './types';

const COUNTER_KEY = 'catalogo-chat.order-counter';

function pad(value: number): string {
  return String(value).padStart(order.digits, '0');
}

export function formatOrderCode(year: number, number: number): string {
  return `${order.prefix}-${year}-${pad(number)}`;
}

/**
 * Contatore locale: progressivo per browser.
 *
 * È il ripiego quando non c'è uno store condiviso. Due visitatori diversi
 * possono ottenere lo stesso numero: per una numerazione globale serve
 * configurare KV_REST_API_URL e KV_REST_API_TOKEN.
 */
function nextLocalNumber(year: number): number {
  if (typeof window === 'undefined') return 1;

  try {
    const raw = window.localStorage.getItem(COUNTER_KEY);
    const stored = raw ? (JSON.parse(raw) as { year: number; value: number }) : null;
    const next = stored && stored.year === year ? stored.value + 1 : 1;
    window.localStorage.setItem(COUNTER_KEY, JSON.stringify({ year, value: next }));
    return next;
  } catch {
    // Storage negato (modalità privata, cookie bloccati): meglio un numero
    // basato sull'orario che nessun ordine.
    return Number(String(Date.now()).slice(-5));
  }
}

/** Codice ordine per la richiesta corrente. Non lancia mai: l'invio è prioritario. */
export async function nextOrderCode(): Promise<string> {
  const year = new Date().getFullYear();

  try {
    const response = await fetch('/api/order-number', { method: 'POST' });
    if (response.ok) {
      const data = (await response.json()) as { mode: string; year: number; number?: number };
      if (data.mode === 'shared' && typeof data.number === 'number') {
        return formatOrderCode(data.year, data.number);
      }
    }
  } catch {
    // Offline o funzione non disponibile: si continua in locale.
  }

  return formatOrderCode(year, nextLocalNumber(year));
}

/* -------------------------------------------------------------------------- */
/* Messaggio                                                                   */
/* -------------------------------------------------------------------------- */

/**
 * Riga articolo. I segmenti con valori vuoti spariscono: su un prodotto senza
 * taglia non resta un "Taglia:" orfano.
 */
function itemLine(line: CartLine): string {
  const segments = [
    line.title,
    line.variantLabel ? `Taglia: ${line.variantLabel}` : '',
    `Q.tà: ${line.qty}`,
    `Prezzo: ${
      line.priceOnRequest || line.unitPrice === null
        ? labels.priceOnRequest
        : formatPrice(line.unitPrice * line.qty)
    }`,
  ].filter(Boolean);

  return `• ${segments.join(' - ')}`;
}

/** Messaggio completo dell'ordine, pronto per essere codificato in URL. */
export function buildOrderMessage(code: string, lines: CartLine[], totals: CartTotals): string {
  const divider = '----------------------------------';

  return [
    `🛒 *Nuovo Ordine #${code}*`,
    divider,
    lines.map(itemLine).join('\n'),
    divider,
    `📦 Spedizione: ${totals.shipping.label}`,
    `💰 *Totale Stimato: ${totalLabel(totals)}*`,
    '',
    'Ciao! Vorrei confermare questo ordine.',
  ].join('\n');
}

/**
 * Link alla chat con il testo già scritto.
 *
 * `encodeURIComponent` codifica gli a capo come %0A e gli spazi come %20;
 * usare una querystring costruita a mano con "+" al posto degli spazi
 * farebbe comparire i "+" nel messaggio.
 */
export function whatsappUrl(message: string, phone: string = shop.whatsapp): string {
  return `https://api.whatsapp.com/send?phone=${encodeURIComponent(phone)}&text=${encodeURIComponent(message)}`;
}

/** Messaggio per una singola scheda prodotto (domanda pre-acquisto). */
export function buildProductMessage(title: string, price: number | null, url?: string): string {
  return [
    'Ciao! 👋 Vorrei informazioni su questo articolo:',
    '',
    `*${title}*`,
    price === null ? '' : `Prezzo: ${formatPrice(price)}`,
    url ?? '',
  ]
    .filter((row, index, all) => row !== '' || all[index - 1] !== '')
    .join('\n')
    .trim();
}
