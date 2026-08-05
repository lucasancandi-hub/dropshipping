'use client';

import { useState } from 'react';

import { useCart } from '@/lib/cart';
import { buildProductMessage, whatsappUrl } from '@/lib/order';
import type { Product, Variant } from '@/lib/types';
import { Price } from './Price';
import { QuantityStepper } from './QuantityStepper';
import { WhatsAppIcon } from './icons';

/**
 * Blocco d'acquisto: taglia, quantità, aggiunta al carrello.
 *
 * Il prezzo mostrato segue la variante selezionata, che può avere un prezzo
 * proprio diverso da quello del prodotto.
 */
export function AddToCart({ product }: { product: Product }) {
  const { add } = useCart();
  const hasVariants = product.variants.length > 0;

  const [variant, setVariant] = useState<Variant | null>(
    hasVariants ? (product.variants.find((item) => item.inStock) ?? null) : null,
  );
  const [qty, setQty] = useState(1);

  const price = variant?.price ?? product.price;
  const soldOut = hasVariants ? product.variants.every((item) => !item.inStock) : !product.inStock;
  const missingVariant = hasVariants && !variant;

  const infoUrl = whatsappUrl(
    buildProductMessage(product.title, price, product.sourceUrl || undefined),
  );

  return (
    <div>
      <div className="mt-3">
        <Price
          price={price}
          listPrice={product.listPrice}
          onRequest={product.priceOnRequest}
          size="lg"
        />
      </div>

      {product.shortDescription && (
        <p className="mt-4 max-w-prose text-[15px] leading-relaxed text-neutral-600 dark:text-neutral-300">
          {product.shortDescription}
        </p>
      )}

      {hasVariants && (
        <fieldset className="mt-6">
          <legend className="text-xs font-semibold uppercase tracking-[0.14em] text-neutral-500">
            {product.variantLabel ?? 'Taglia'}
          </legend>

          <div className="mt-2 flex flex-wrap gap-2">
            {product.variants.map((item) => {
              const selected = variant?.id === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  disabled={!item.inStock}
                  aria-pressed={selected}
                  onClick={() => setVariant(item)}
                  className={`flex h-12 min-w-12 items-center justify-center rounded-xl border px-4 text-sm font-medium transition ${
                    !item.inStock
                      ? 'cursor-not-allowed border-dashed border-neutral-200 text-neutral-300 line-through dark:border-neutral-800 dark:text-neutral-600'
                      : selected
                        ? 'border-neutral-900 bg-neutral-900 text-white dark:border-white dark:bg-white dark:text-neutral-900'
                        : 'border-neutral-200 hover:border-neutral-900 dark:border-neutral-700 dark:hover:border-neutral-400'
                  }`}
                >
                  {item.label}
                </button>
              );
            })}
          </div>
        </fieldset>
      )}

      <div className="mt-7 flex flex-wrap items-center gap-3">
        <QuantityStepper value={qty} onChange={setQty} />

        <button
          type="button"
          disabled={soldOut || missingVariant}
          onClick={() => add(product, variant, qty)}
          className="btn-solid flex-1 basis-56"
        >
          {soldOut ? 'Esaurito' : 'Aggiungi al carrello'}
        </button>
      </div>

      <p className="mt-4 text-sm">
        <a
          href={infoUrl}
          target="_blank"
          rel="noopener nofollow"
          className="inline-flex items-center gap-1.5 text-brand-dark underline decoration-1 underline-offset-4 hover:opacity-80 dark:text-brand"
        >
          <WhatsAppIcon className="h-4 w-4" />
          Dubbi sulla taglia o sulla disponibilità? Scrivici
        </a>
      </p>
    </div>
  );
}
