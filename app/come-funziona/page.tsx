import type { Metadata } from 'next';

import { Prose } from '@/components/LegalNotice';
import { labels, shipping, shop } from '@/lib/config';
import { formatPrice } from '@/lib/format';

export const metadata: Metadata = {
  title: 'Come funziona',
  description: 'Come si ordina, spedizioni, tempi di consegna e pagamento.',
  alternates: { canonical: '/come-funziona' },
};

export default function ComeFunzionaPage() {
  const sogliaAttiva = shipping.freeOver > 0;

  return (
    <Prose title="Come funziona">
      <p>
        Su {shop.name} non si paga online. Scegli gli articoli, li aggiungi al carrello e invii
        l’ordine su WhatsApp con un messaggio già compilato: da lì confermiamo insieme
        disponibilità, spedizione e totale.
      </p>

      <h2>1. Scegli e aggiungi al carrello</h2>
      <p>
        Su ogni scheda prodotto selezioni la taglia e la quantità. Le taglie esaurite sono
        barrate e non selezionabili. Alcuni articoli riportano
        «{labels.priceOnRequest}»: sono pezzi il cui prezzo dipende dalla
        disponibilità del momento e lo definiamo in conversazione.
      </p>

      <h2>2. Invii l’ordine</h2>
      <p>
        Dal carrello, il pulsante <strong>Invia ordine su WhatsApp</strong> apre la chat con il
        riepilogo già scritto: articoli, taglie, quantità, spedizione stimata, totale e un numero
        d’ordine per ritrovare la conversazione.
      </p>

      <h2>3. Confermiamo insieme</h2>
      <p>
        Ti rispondiamo confermando la disponibilità effettiva e il totale definitivo, e ci
        accordiamo sul pagamento e sull’indirizzo di consegna. L’ordine è impegnativo solo dopo
        questa conferma.
      </p>

      <h2>Spedizione</h2>
      <p>
        Il totale che vedi nel carrello include una <strong>stima</strong> di spedizione
        {shipping.mode === 'flat' && <> pari a {formatPrice(shipping.flat)}</>}
        {shipping.mode === 'quantity' && <> calcolata in base al numero di articoli</>}
        {shipping.mode === 'none' && <> da definire in chat</>}. Il costo esatto dipende da
        destinazione, peso e volume del pacco, e te lo confermiamo prima di procedere.
        {sogliaAttiva && (
          <> La spedizione è gratuita per ordini a partire da {formatPrice(shipping.freeOver)}.</>
        )}
      </p>
      <p>
        {/* DA COMPLETARE: corriere, tempi reali, aree servite */}
        <strong>Tempi di consegna e corriere:</strong> da indicare.
      </p>

      <h2>Pagamento</h2>
      <p>
        {/* DA COMPLETARE: bonifico, PayPal, contrassegno... */}
        <strong>Metodi accettati:</strong> da indicare. Nessun pagamento avviene sul sito: non
        raccogliamo né conserviamo dati di carte di credito.
      </p>

      <h2>Resi e recesso</h2>
      <p>
        Se acquisti come consumatore hai diritto di recedere entro 14 giorni dal ricevimento della
        merce, senza doverne indicare il motivo. Trovi le condizioni complete nei{' '}
        <a href="/termini" className="underline underline-offset-4">
          termini di vendita
        </a>
        .
      </p>
    </Prose>
  );
}
