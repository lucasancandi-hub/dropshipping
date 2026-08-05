import type { Metadata, Viewport } from 'next';

import { CartDrawer } from '@/components/CartDrawer';
import { Footer } from '@/components/Footer';
import { Header } from '@/components/Header';
import { JsonLd, organizationSchema } from '@/components/JsonLd';
import { CartProvider } from '@/lib/cart';
import { shop } from '@/lib/config';
import './globals.css';

const description =
  'Catalogo con ordine via WhatsApp: scegli gli articoli, controlla il riepilogo e concludi in chat.';

export const metadata: Metadata = {
  // Senza metadataBase le immagini di anteprima restano relative e i link
  // condivisi in chat arrivano senza foto: qui è il canale principale.
  metadataBase: new URL(shop.url),
  title: {
    default: `${shop.name} — Catalogo`,
    template: `%s — ${shop.name}`,
  },
  description,
  applicationName: shop.name,
  openGraph: {
    type: 'website',
    locale: 'it_IT',
    siteName: shop.name,
    title: `${shop.name} — Catalogo`,
    description,
    url: '/',
  },
  twitter: {
    card: 'summary_large_image',
    title: `${shop.name} — Catalogo`,
    description,
  },
  robots: { index: true, follow: true },
  alternates: { canonical: '/' },
};

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#ffffff' },
    { media: '(prefers-color-scheme: dark)', color: '#0a0a0a' },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="it">
      <body>
        <JsonLd data={organizationSchema()} />
        <CartProvider>
          <Header />
          <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
          <Footer />
          <CartDrawer />
        </CartProvider>
      </body>
    </html>
  );
}
