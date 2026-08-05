'use client';

/**
 * Stato del carrello: React context + localStorage.
 *
 * Nessun backend, nessuna sessione server. Il carrello vive nel browser e
 * sopravvive al reload; l'idratazione avviene in un effetto per non generare
 * mismatch fra HTML statico e primo render client.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { computeTotals } from './shipping';
import type { CartLine, CartTotals, Product, Variant } from './types';

const STORAGE_KEY = 'catalogo-chat.cart.v1';

type CartContextValue = {
  lines: CartLine[];
  totals: CartTotals;
  /** false finché non è stato letto localStorage: evita conteggi lampeggianti. */
  ready: boolean;
  isOpen: boolean;
  add: (product: Product, variant: Variant | null, qty?: number) => void;
  setQty: (key: string, qty: number) => void;
  remove: (key: string) => void;
  clear: () => void;
  openCart: () => void;
  closeCart: () => void;
};

const CartContext = createContext<CartContextValue | null>(null);

function lineKey(productId: string, variantId: string | null): string {
  return `${productId}::${variantId ?? ''}`;
}

/** Prezzo effettivo: quello della variante se presente, altrimenti del prodotto. */
function resolvePrice(product: Product, variant: Variant | null): number | null {
  if (product.priceOnRequest) return null;
  if (variant && variant.price !== null) return variant.price;
  return product.price;
}

function readStorage(): CartLine[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    // Filtro difensivo: uno schema vecchio in storage non deve rompere l'app.
    return parsed.filter(
      (line): line is CartLine =>
        typeof line === 'object' &&
        line !== null &&
        typeof (line as CartLine).key === 'string' &&
        typeof (line as CartLine).qty === 'number',
    );
  } catch {
    return [];
  }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>([]);
  const [ready, setReady] = useState(false);
  const [isOpen, setOpen] = useState(false);

  useEffect(() => {
    setLines(readStorage());
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(lines));
    } catch {
      // Storage pieno o negato: il carrello resta comunque in memoria.
    }
  }, [lines, ready]);

  // Il drawer aperto blocca lo scorrimento della pagina sotto.
  useEffect(() => {
    if (typeof document === 'undefined') return;
    document.body.style.overflow = isOpen ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  const add = useCallback((product: Product, variant: Variant | null, qty = 1) => {
    const key = lineKey(product.id, variant?.id ?? null);

    setLines((current) => {
      const existing = current.find((line) => line.key === key);
      if (existing) {
        return current.map((line) =>
          line.key === key ? { ...line, qty: Math.min(99, line.qty + qty) } : line,
        );
      }

      const line: CartLine = {
        key,
        productId: product.id,
        slug: product.slug,
        title: product.title,
        image: product.images[0] ?? null,
        variantId: variant?.id ?? null,
        variantLabel: variant?.label ?? null,
        unitPrice: resolvePrice(product, variant),
        priceOnRequest: product.priceOnRequest,
        qty,
      };
      return [...current, line];
    });

    setOpen(true);
  }, []);

  const setQty = useCallback((key: string, qty: number) => {
    setLines((current) =>
      qty <= 0
        ? current.filter((line) => line.key !== key)
        : current.map((line) => (line.key === key ? { ...line, qty: Math.min(99, qty) } : line)),
    );
  }, []);

  const remove = useCallback((key: string) => {
    setLines((current) => current.filter((line) => line.key !== key));
  }, []);

  const clear = useCallback(() => setLines([]), []);
  const openCart = useCallback(() => setOpen(true), []);
  const closeCart = useCallback(() => setOpen(false), []);

  const totals = useMemo(() => computeTotals(lines), [lines]);

  const value = useMemo<CartContextValue>(
    () => ({ lines, totals, ready, isOpen, add, setQty, remove, clear, openCart, closeCart }),
    [lines, totals, ready, isOpen, add, setQty, remove, clear, openCart, closeCart],
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartContextValue {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error('useCart va usato dentro <CartProvider>');
  }
  return context;
}
