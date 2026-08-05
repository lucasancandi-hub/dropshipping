import type { Metadata } from 'next';

import { Prose } from '@/components/LegalNotice';
import { business } from '@/lib/business';
import { shop } from '@/lib/config';
import { buildProductMessage, whatsappUrl } from '@/lib/order';

export const metadata: Metadata = {
  title: 'Contatti',
  description: 'Come raggiungerci: WhatsApp, email e dati dell’attività.',
  alternates: { canonical: '/contatti' },
};

export default function ContattiPage() {
  const chat = whatsappUrl('Ciao! 👋 Avrei una domanda:');

  return (
    <Prose title="Contatti">
      <p>
        Il canale più rapido è WhatsApp: rispondiamo in chat su disponibilità, taglie, spedizioni e
        stato degli ordini.
      </p>

      <p>
        <a href={chat} target="_blank" rel="noopener nofollow" className="btn-chat mt-2">
          Scrivici su WhatsApp
        </a>
      </p>

      <h2>Altri recapiti</h2>
      <ul>
        <li>WhatsApp: +{shop.whatsapp}</li>
        {business.email ? <li>Email: {business.email}</li> : <li>Email: da indicare</li>}
      </ul>

      <h2>Dati dell’attività</h2>
      <ul>
        <li>{business.legalName || 'Ragione sociale: da indicare'}</li>
        <li>{business.vat ? `P. IVA ${business.vat}` : 'Partita IVA: da indicare'}</li>
        <li>{business.address || 'Sede: da indicare'}</li>
        {business.rea && <li>REA {business.rea}</li>}
      </ul>
    </Prose>
  );
}
