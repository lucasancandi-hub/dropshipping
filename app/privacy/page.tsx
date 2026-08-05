import type { Metadata } from 'next';

import { LegalNotice, Prose } from '@/components/LegalNotice';
import { business } from '@/lib/business';
import { shop } from '@/lib/config';

export const metadata: Metadata = {
  title: 'Privacy policy',
  description: 'Come trattiamo i dati personali di chi ci contatta e ordina.',
  robots: { index: true, follow: false },
  alternates: { canonical: '/privacy' },
};

export default function PrivacyPage() {
  return (
    <Prose title="Privacy policy">
      <LegalNotice />

      <p>
        Informativa ai sensi degli articoli 13 e 14 del Regolamento UE 2016/679 (GDPR).
      </p>

      <h2>Titolare del trattamento</h2>
      <p>
        {business.legalName || '[ragione sociale]'}
        {business.vat && <>, P. IVA {business.vat}</>}
        {business.address && <>, {business.address}</>}. Per esercitare i tuoi diritti scrivi a{' '}
        {business.email || '[email di contatto]'}.
      </p>

      <h2>Quali dati raccogliamo</h2>
      <ul>
        <li>
          <strong>Dati che ci fornisci in chat</strong>: numero di telefono, nome, indirizzo di
          consegna e quanto altro comunichi per completare l’ordine.
        </li>
        <li>
          <strong>Dati tecnici del sito</strong>: il carrello è salvato nella memoria locale del
          tuo browser (localStorage) e non ci viene trasmesso. Non usiamo cookie di profilazione.
        </li>
      </ul>

      <h2>Perché li trattiamo</h2>
      <ul>
        <li>
          Rispondere alle richieste e gestire l’ordine: base giuridica è l’esecuzione di misure
          precontrattuali e del contratto (art. 6.1.b GDPR).
        </li>
        <li>
          Adempimenti fiscali e contabili: obbligo di legge (art. 6.1.c GDPR).
        </li>
      </ul>

      <h2>Con chi li condividiamo</h2>
      <p>
        La conversazione avviene su WhatsApp, servizio fornito da Meta Platforms Ireland Ltd., che
        tratta i dati secondo la propria informativa. Comunichiamo i dati necessari al corriere per
        la consegna e al professionista che cura la contabilità. Non vendiamo dati a terzi.
      </p>
      <p>
        Il sito è ospitato su Vercel Inc., che può trattare dati tecnici di connessione come
        responsabile del trattamento.
      </p>

      <h2>Per quanto tempo</h2>
      <p>
        I messaggi legati a una richiesta non andata a buon fine sono conservati per il tempo
        necessario a rispondere. I dati degli ordini conclusi sono conservati per dieci anni, come
        richiesto dalla normativa fiscale.
      </p>

      <h2>I tuoi diritti</h2>
      <p>
        Puoi chiedere accesso, rettifica, cancellazione, limitazione e portabilità dei dati, e
        opporti al trattamento (artt. 15-22 GDPR). Puoi inoltre proporre reclamo al Garante per la
        protezione dei dati personali.
      </p>

      <h2>Aggiornamenti</h2>
      <p>
        Questa informativa può essere aggiornata: la versione pubblicata su {shop.url}/privacy è
        sempre quella vigente.
      </p>
    </Prose>
  );
}
