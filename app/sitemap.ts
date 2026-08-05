import type { MetadataRoute } from 'next';

import { catalog, getProducts } from '@/lib/catalog';
import { shop } from '@/lib/config';

export default function sitemap(): MetadataRoute.Sitemap {
  const aggiornato = new Date(catalog.generatedAt);

  const statiche: MetadataRoute.Sitemap = [
    { url: shop.url, lastModified: aggiornato, changeFrequency: 'daily', priority: 1 },
    { url: `${shop.url}/come-funziona`, changeFrequency: 'yearly', priority: 0.5 },
    { url: `${shop.url}/contatti`, changeFrequency: 'yearly', priority: 0.5 },
    { url: `${shop.url}/privacy`, changeFrequency: 'yearly', priority: 0.2 },
    { url: `${shop.url}/termini`, changeFrequency: 'yearly', priority: 0.2 },
  ];

  const prodotti: MetadataRoute.Sitemap = getProducts().map((product) => ({
    url: `${shop.url}/prodotto/${product.slug}`,
    lastModified: aggiornato,
    changeFrequency: 'weekly',
    priority: 0.8,
  }));

  return [...statiche, ...prodotti];
}
