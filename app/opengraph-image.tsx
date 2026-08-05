import { ImageResponse } from 'next/og';

import { shop } from '@/lib/config';

/**
 * Anteprima mostrata quando il link del sito viene incollato in chat.
 * Le schede prodotto usano invece la foto del prodotto (vedi generateMetadata).
 */
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';
export const alt = `${shop.name} — catalogo`;

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          padding: '80px',
          background: '#0f1115',
          color: '#ffffff',
        }}
      >
        <div style={{ fontSize: 76, fontWeight: 700, letterSpacing: '-0.02em' }}>{shop.name}</div>
        <div style={{ marginTop: 18, fontSize: 34, color: '#9ca3af' }}>
          Scegli, aggiungi al carrello, ordina in chat
        </div>
        <div
          style={{
            marginTop: 48,
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            fontSize: 28,
            color: '#25d366',
          }}
        >
          <div style={{ width: 16, height: 16, borderRadius: 8, background: '#25d366' }} />
          Ordini via WhatsApp · nessun pagamento online
        </div>
      </div>
    ),
    size,
  );
}
