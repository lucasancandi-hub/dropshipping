'use client';

import Link from 'next/link';

import { useCart } from '@/lib/cart';
import { shop } from '@/lib/config';
import { CartIcon } from './icons';

/** Header sticky con contatore carrello. */
export function Header() {
  const { totals, ready, openCart } = useCart();

  return (
    <header className="sticky top-0 z-30 border-b border-neutral-200/70 bg-white/85 backdrop-blur-md dark:border-neutral-800/70 dark:bg-neutral-950/85">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3.5">
        <Link href="/" className="text-lg font-semibold tracking-tight">
          {shop.name}
        </Link>

        <button
          type="button"
          onClick={openCart}
          className="relative grid h-11 w-11 place-items-center rounded-full transition hover:bg-neutral-100 dark:hover:bg-neutral-900"
          aria-label={`Apri il carrello${ready && totals.count > 0 ? `, ${totals.count} articoli` : ''}`}
        >
          <CartIcon className="h-5.5 w-5.5" />

          {/* `ready` evita che il badge lampeggi prima di leggere localStorage. */}
          {ready && totals.count > 0 && (
            <span className="absolute -right-0.5 -top-0.5 grid h-5 min-w-5 place-items-center rounded-full bg-brand px-1 text-[11px] font-bold text-white">
              {totals.count}
            </span>
          )}
        </button>
      </div>
    </header>
  );
}
