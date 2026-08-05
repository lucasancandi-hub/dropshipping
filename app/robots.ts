import type { MetadataRoute } from 'next';

import { shop } from '@/lib/config';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: '*',
      allow: '/',
      // L'endpoint del contatore non ha nulla da indicizzare.
      disallow: '/api/',
    },
    sitemap: `${shop.url}/sitemap.xml`,
  };
}
