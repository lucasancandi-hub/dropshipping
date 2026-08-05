import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';

import { AddToCart } from '@/components/AddToCart';
import { Gallery } from '@/components/Gallery';
import { ProductCard } from '@/components/ProductCard';
import { getProductBySlug, getProducts, getRelated } from '@/lib/catalog';

type Props = { params: Promise<{ slug: string }> };

/** Tutte le schede prodotto sono pre-generate: nessun rendering a runtime. */
export function generateStaticParams() {
  return getProducts().map((product) => ({ slug: product.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const product = getProductBySlug(slug);

  if (!product) return { title: 'Prodotto non trovato' };

  return {
    title: product.title,
    description: product.shortDescription || product.description || product.title,
    openGraph: {
      title: product.title,
      description: product.shortDescription || product.title,
      images: product.images.slice(0, 1),
      type: 'website',
    },
  };
}

export default async function ProductPage({ params }: Props) {
  const { slug } = await params;
  const product = getProductBySlug(slug);

  if (!product) notFound();

  const related = getRelated(product);

  return (
    <>
      <nav className="mb-6 text-sm text-neutral-500">
        <Link href="/" className="hover:underline">
          Catalogo
        </Link>
        {product.category && <span> / {product.category}</span>}
      </nav>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1.15fr_1fr] lg:gap-14">
        <Gallery images={product.images} title={product.title} />

        {/* La colonna dati resta visibile mentre si scorrono le immagini. */}
        <section className="lg:sticky lg:top-24 lg:self-start">
          {product.category && (
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-neutral-500">
              {product.category}
            </p>
          )}

          <h1 className="mt-1 text-3xl font-bold leading-tight tracking-tight sm:text-4xl">
            {product.title}
          </h1>

          <AddToCart product={product} />

          {product.description && (
            <div className="mt-8 border-t border-neutral-200 pt-6 dark:border-neutral-800">
              <h2 className="text-sm font-semibold uppercase tracking-[0.12em] text-neutral-500">
                Dettagli
              </h2>
              <p className="mt-2.5 max-w-prose text-[15px] leading-relaxed text-neutral-600 dark:text-neutral-300">
                {product.description}
              </p>
              {product.sku && <p className="mt-3 text-sm text-neutral-400">Codice: {product.sku}</p>}
            </div>
          )}
        </section>
      </div>

      {related.length > 0 && (
        <section className="mt-16">
          <h2 className="mb-5 text-xl font-semibold tracking-tight">Ti potrebbe piacere</h2>
          <ul className="grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-3 lg:grid-cols-4">
            {related.map((item) => (
              <ProductCard key={item.id} product={item} />
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
