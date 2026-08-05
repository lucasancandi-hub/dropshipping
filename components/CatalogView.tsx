'use client';

import { useMemo, useState } from 'react';

import type { Product } from '@/lib/types';
import { ProductCard } from './ProductCard';

/**
 * Griglia catalogo con filtro per categoria.
 *
 * Il filtro è client-side su un array già presente nel bundle: nessuna
 * richiesta di rete, nessun ricaricamento di pagina.
 */
export function CatalogView({
  products,
  categories,
}: {
  products: Product[];
  categories: string[];
}) {
  const [active, setActive] = useState<string | null>(null);

  const visible = useMemo(
    () => (active ? products.filter((product) => product.category === active) : products),
    [products, active],
  );

  return (
    <>
      {categories.length > 1 && (
        <div
          className="-mx-4 mb-7 flex snap-x gap-2 overflow-x-auto px-4 pb-1"
          role="group"
          aria-label="Filtra per categoria"
        >
          <FilterChip label="Tutti" active={active === null} onClick={() => setActive(null)} />
          {categories.map((category) => (
            <FilterChip
              key={category}
              label={category}
              active={active === category}
              onClick={() => setActive(category)}
            />
          ))}
        </div>
      )}

      <ul className="grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-3 lg:grid-cols-4">
        {visible.map((product) => (
          <ProductCard key={product.id} product={product} />
        ))}
      </ul>

      {visible.length === 0 && (
        <p className="py-16 text-center text-neutral-500">Nessun prodotto in questa categoria.</p>
      )}
    </>
  );
}

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`snap-start whitespace-nowrap rounded-full border px-4 py-2 text-sm font-medium transition ${
        active
          ? 'border-neutral-900 bg-neutral-900 text-white dark:border-white dark:bg-white dark:text-neutral-900'
          : 'border-neutral-200 hover:border-neutral-900 dark:border-neutral-700 dark:hover:border-neutral-400'
      }`}
    >
      {label}
    </button>
  );
}
