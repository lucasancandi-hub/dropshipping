import type { Metadata, Viewport } from 'next';

import { CartDrawer } from '@/components/CartDrawer';
import { Header } from '@/components/Header';
import { CartProvider } from '@/lib/cart';
import { shop } from '@/lib/config';
import './globals.css';

export const metadata: Metadata = {
  title: {
    default: `${shop.name} — Catalogo`,
    template: `%s — ${shop.name}`,
  },
  description:
    'Catalogo con ordine via WhatsApp: scegli gli articoli, controlla il riepilogo e concludi in chat.',
  robots: { index: true, follow: true },
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
        <CartProvider>
          <Header />
          <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>

          <footer className="mx-auto max-w-6xl px-4 py-12 text-sm text-neutral-500">
            <p>
              {shop.name} — gli ordini si concludono in chat. Nessun pagamento online, nessun
              account da creare.
            </p>
          </footer>

          <CartDrawer />
        </CartProvider>
      </body>
    </html>
  );
}
