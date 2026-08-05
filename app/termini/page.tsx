import type { Metadata } from 'next';

import { LegalNotice, Prose } from '@/components/LegalNotice';
import { business } from '@/lib/business';
import { shipping, shop } from '@/lib/config';
import { formatPrice } from '@/lib/format';

export const metadata: Metadata = {
  title: 'Termini di vendita',
  description: 'Condizioni di vendita, spedizioni, diritto di recesso e garanzia.',
  robots: { index: true, follow: false },
  alternates: { canonical: '/termini' },
};

export default function TerminiPage() {
  return (
    <Prose title="Termini di vendita">
      <LegalNotice />

      <h2>Venditore</h2>
      <p>
        {business.legalName || '[ragione sociale]'}
        {business.vat && <>, P. IVA {business.vat}</>}
        {business.address && <>, {business.address}</>}
        {business.email && <>, {business.email}</>}.
      </p>

      <h2>Come si conclude il contratto</h2>
      <p>
        Il catalogo pubblicato su {shop.name} è un invito a trattare, non un’offerta al pubblico.
        L’invio del riepilogo via WhatsApp è una <strong>richiesta d’ordine</strong>: il contratto
        si perfeziona quando confermiamo per iscritto in chat disponibilità, prezzo definitivo e
        costo di spedizione. Fino a quel momento nulla è dovuto.
      </p>

      <h2>Prezzi</h2>
      <p>
        I prezzi sono espressi in euro e comprensivi di IVA quando dovuta. Il totale mostrato nel
        carrello include una stima della spedizione
        {shipping.freeOver > 0 && (
          <>, gratuita per ordini pari o superiori a {formatPrice(shipping.freeOver)}</>
        )}
        : l’importo definitivo è quello confermato in chat. Gli articoli indicati come «prezzo da
        concordare» non hanno un prezzo prefissato.
      </p>

      <h2>Pagamento</h2>
      <p>
        {/* DA COMPLETARE: metodi effettivamente accettati */}
        I metodi accettati sono concordati in chat. Il sito non elabora pagamenti e non raccoglie
        dati di strumenti di pagamento.
      </p>

      <h2>Consegna</h2>
      <p>
        {/* DA COMPLETARE: corriere, tempi, aree servite */}
        Tempi e vettore vengono comunicati in fase di conferma. Il rischio di perdita o
        danneggiamento passa al consumatore alla consegna materiale del bene.
      </p>

      <h2>Diritto di recesso</h2>
      <p>
        Se acquisti come consumatore hai diritto di recedere entro <strong>14 giorni</strong> dal
        ricevimento della merce, senza obbligo di motivazione (artt. 52 e seguenti del Codice del
        Consumo). È sufficiente comunicarlo ai recapiti indicati sopra. Il bene va restituito
        integro entro 14 giorni dalla comunicazione; le spese di restituzione sono a carico
        dell’acquirente salvo diverso accordo. Il rimborso avviene entro 14 giorni dal rientro
        della merce.
      </p>

      <h2>Garanzia legale di conformità</h2>
      <p>
        Sui beni venduti a consumatori si applica la garanzia legale di conformità di 24 mesi
        (artt. 128 e seguenti del Codice del Consumo).
      </p>

      <h2>Legge applicabile e controversie</h2>
      <p>
        Al contratto si applica la legge italiana. Per il consumatore è competente il foro del
        luogo di residenza o domicilio. È disponibile la piattaforma europea di risoluzione delle
        controversie online (ODR) della Commissione europea.
      </p>
    </Prose>
  );
}
