import { business } from '@/lib/business';
import { shop } from '@/lib/config';
import type { Product } from '@/lib/types';

/**
 * Dati strutturati schema.org.
 *
 * È quello che fa comparire prezzo e disponibilità nei risultati di ricerca:
 * traffico organico che senza questo blocco non arriva.
 */
export function JsonLd({ data }: { data: object }) {
  return (
    <script
      type="application/ld+json"
      // I dati sono nostri e serializzati da JSON.stringify, non input utente.
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}

export function organizationSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: business.legalName || shop.name,
    url: shop.url,
    ...(business.email ? { email: business.email } : {}),
    ...(business.vat ? { vatID: business.vat } : {}),
    ...(business.address ? { address: { '@type': 'PostalAddress', streetAddress: business.address } } : {}),
    contactPoint: {
      '@type': 'ContactPoint',
      contactType: 'customer service',
      telephone: `+${shop.whatsapp}`,
      availableLanguage: ['it'],
    },
  };
}

export function productSchema(product: Product) {
  const url = `${shop.url}/prodotto/${product.slug}`;
  const disponibile =
    product.inStock && (product.variants.length === 0 || product.variants.some((v) => v.inStock));

  return {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: product.title,
    description: product.shortDescription || product.description || product.title,
    image: product.images,
    ...(product.sku ? { sku: product.sku } : {}),
    ...(product.category ? { category: product.category } : {}),
    url,
    offers: {
      '@type': 'Offer',
      url,
      priceCurrency: product.currency || shop.currency,
      // Senza prezzo il campo si omette: meglio nessun dato che una cifra inventata.
      ...(product.priceOnRequest || product.price === null ? {} : { price: product.price }),
      availability: disponibile
        ? 'https://schema.org/InStock'
        : 'https://schema.org/OutOfStock',
      seller: { '@type': 'Organization', name: business.legalName || shop.name },
    },
  };
}
