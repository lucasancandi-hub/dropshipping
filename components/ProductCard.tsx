import Link from 'next/link';

import type { Product } from '@/lib/types';
import { Price } from './Price';

/**
 * Card della griglia catalogo.
 *
 * Porta sempre alla scheda prodotto: la taglia si sceglie lì, e un carrello
 * senza taglia sarebbe una richiesta incompleta da chiarire in chat.
 */
export function ProductCard({ product }: { product: Product }) {
  const cover = product.images[0];
  const soldOut = !product.inStock || product.variants.every((v) => !v.inStock);

  return (
    <li className="group">
      <Link href={`/prodotto/${product.slug}`} className="block">
        <div className="relative overflow-hidden rounded-card bg-neutral-100 dark:bg-neutral-900">
          {cover ? (
            <img
              src={cover}
              alt={product.title}
              loading="lazy"
              decoding="async"
              className="aspect-3/4 w-full object-cover transition duration-500 group-hover:scale-[1.03] motion-reduce:transition-none"
            />
          ) : (
            <div className="aspect-3/4 w-full" />
          )}

          {soldOut && (
            <span className="absolute left-3 top-3 rounded-full bg-white/95 px-2.5 py-1 text-xs font-medium text-neutral-900">
              Esaurito
            </span>
          )}
        </div>

        <div className="mt-2.5">
          {product.category && (
            <p className="text-xs uppercase tracking-[0.12em] text-neutral-500">
              {product.category}
            </p>
          )}
          <h3 className="mt-0.5 text-[15px] font-medium leading-snug group-hover:underline">
            {product.title}
          </h3>
          <div className="mt-1">
            <Price
              price={product.price}
              listPrice={product.listPrice}
              onRequest={product.priceOnRequest}
            />
          </div>
        </div>
      </Link>
    </li>
  );
}
