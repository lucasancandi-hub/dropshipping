'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';

import { useCart } from '@/lib/cart';
import { labels } from '@/lib/config';
import { formatPrice } from '@/lib/format';
import { buildOrderMessage, nextOrderCode, whatsappUrl } from '@/lib/order';
import { shippingRuleLabel, totalLabel } from '@/lib/shipping';
import { QuantityStepper } from './QuantityStepper';
import { CartIcon, CloseIcon, WhatsAppIcon } from './icons';

/**
 * Drawer laterale: riepilogo, stima spedizione e invio ordine.
 *
 * L'invio genera il codice progressivo, compone il messaggio e apre WhatsApp.
 * La finestra viene aperta **prima** dell'await sul codice: aprirla dopo una
 * promise la farebbe bloccare dal browser come popup.
 */
export function CartDrawer() {
  const { lines, totals, isOpen, closeCart, setQty, remove, clear } = useCart();
  const [sending, setSending] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  // Chiusura con ESC e focus dentro il pannello finché è aperto.
  useEffect(() => {
    if (!isOpen) return;

    closeRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        closeCart();
        return;
      }
      if (event.key !== 'Tab' || !panelRef.current) return;

      const focusables = panelRef.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (focusables.length === 0) return;

      const first = focusables[0];
      const last = focusables[focusables.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [isOpen, closeCart]);

  async function sendOrder() {
    if (lines.length === 0 || sending) return;
    setSending(true);

    // Apertura sincrona: il browser la collega al click, non alla promise.
    const target = window.open('', '_blank');

    try {
      const code = await nextOrderCode();
      const url = whatsappUrl(buildOrderMessage(code, lines, totals));

      // La scheda può essere stata bloccata, o restituita in uno stato su cui
      // non si può scrivere: in ogni caso l'ordine deve partire.
      let opened = false;
      try {
        if (target) {
          target.location.href = url;
          opened = true;
        }
      } catch {
        opened = false;
      }

      if (!opened) {
        window.location.href = url;
      }
    } finally {
      setSending(false);
    }
  }

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="Il tuo ordine">
      <button
        type="button"
        aria-label="Chiudi il carrello"
        onClick={closeCart}
        className="absolute inset-0 h-full w-full cursor-default bg-neutral-900/45 backdrop-blur-[2px]"
      />

      <div
        ref={panelRef}
        className="absolute right-0 top-0 flex h-full w-full max-w-[420px] flex-col bg-white shadow-2xl dark:bg-neutral-950"
      >
        <header className="flex items-center justify-between border-b border-neutral-200 px-5 py-4 dark:border-neutral-800">
          <h2 className="text-base font-semibold">Il tuo ordine</h2>
          <button
            ref={closeRef}
            type="button"
            onClick={closeCart}
            aria-label="Chiudi"
            className="grid h-10 w-10 place-items-center rounded-full transition hover:bg-neutral-100 dark:hover:bg-neutral-800"
          >
            <CloseIcon />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5">
          {lines.length === 0 ? (
            <div className="grid h-full place-items-center py-16 text-center">
              <div>
                <CartIcon className="mx-auto h-8 w-8 text-neutral-300" />
                <p className="mt-3 text-neutral-500">Il carrello è vuoto.</p>
                <button type="button" onClick={closeCart} className="btn-ghost mt-5">
                  Continua a sfogliare
                </button>
              </div>
            </div>
          ) : (
            <ul className="divide-y divide-neutral-200 dark:divide-neutral-800">
              {lines.map((line) => (
                <li key={line.key} className="grid grid-cols-[64px_1fr] gap-3.5 py-4">
                  <Link href={`/prodotto/${line.slug}`} onClick={closeCart}>
                    {line.image ? (
                      <img
                        src={line.image}
                        alt=""
                        loading="lazy"
                        className="aspect-3/4 w-16 rounded-lg bg-neutral-100 object-cover dark:bg-neutral-900"
                      />
                    ) : (
                      <div className="aspect-3/4 w-16 rounded-lg bg-neutral-100 dark:bg-neutral-900" />
                    )}
                  </Link>

                  <div className="min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <Link
                        href={`/prodotto/${line.slug}`}
                        onClick={closeCart}
                        className="text-sm font-medium leading-snug hover:underline"
                      >
                        {line.title}
                      </Link>
                      <button
                        type="button"
                        onClick={() => remove(line.key)}
                        aria-label={`Rimuovi ${line.title}`}
                        className="shrink-0 text-neutral-400 transition hover:text-neutral-900 dark:hover:text-white"
                      >
                        <CloseIcon className="h-4 w-4" />
                      </button>
                    </div>

                    {line.variantLabel && (
                      <p className="mt-0.5 text-sm text-neutral-500">Taglia: {line.variantLabel}</p>
                    )}

                    <div className="mt-2 flex items-center justify-between gap-3">
                      <QuantityStepper
                        compact
                        value={line.qty}
                        onChange={(qty) => setQty(line.key, qty)}
                      />
                      <span className="text-sm font-semibold">
                        {line.priceOnRequest || line.unitPrice === null ? (
                          <span className="tag-request">{labels.priceOnRequest}</span>
                        ) : (
                          formatPrice(line.unitPrice * line.qty)
                        )}
                      </span>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {lines.length > 0 && (
          <footer className="border-t border-neutral-200 px-5 pb-[calc(1rem+env(safe-area-inset-bottom))] pt-4 dark:border-neutral-800">
            <dl className="space-y-1.5 text-sm">
              <div className="flex justify-between text-neutral-500">
                <dt>Subtotale</dt>
                <dd>{formatPrice(totals.subtotal)}</dd>
              </div>
              <div className="flex justify-between text-neutral-500">
                <dt>
                  Spedizione stimata
                  <span className="block text-xs text-neutral-400">{shippingRuleLabel()}</span>
                </dt>
                <dd>{totals.shipping.label}</dd>
              </div>
              <div className="flex justify-between border-t border-neutral-200 pt-2 text-base font-semibold dark:border-neutral-800">
                <dt>Totale stimato</dt>
                <dd className="text-right">{totalLabel(totals)}</dd>
              </div>
            </dl>

            <button
              type="button"
              onClick={sendOrder}
              disabled={sending}
              className="btn-chat mt-4 w-full"
            >
              <WhatsAppIcon />
              {sending ? 'Preparo l’ordine…' : 'Invia ordine su WhatsApp'}
            </button>

            <div className="mt-2 flex items-center justify-between text-xs text-neutral-500">
              <span>Nessun pagamento online · confermi tutto in chat</span>
              <button type="button" onClick={clear} className="underline hover:text-neutral-900 dark:hover:text-white">
                Svuota
              </button>
            </div>
          </footer>
        )}
      </div>
    </div>
  );
}
