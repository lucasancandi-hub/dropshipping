import Link from 'next/link';

import { business } from '@/lib/business';
import { shop } from '@/lib/config';

/**
 * Footer con i dati identificativi dell'attività.
 *
 * Per il commercio elettronico sono informazioni obbligatorie (art. 17
 * D.lgs. 70/2003): denominazione, sede, partita IVA e un recapito.
 */
export function Footer() {
  const anno = new Date().getFullYear();

  return (
    <footer className="mt-16 border-t border-neutral-200 dark:border-neutral-800">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 text-sm sm:grid-cols-2">
        <div>
          <p className="text-base font-semibold text-neutral-900 dark:text-neutral-100">
            {shop.name}
          </p>
          <p className="mt-2 max-w-sm text-neutral-500">
            Gli ordini si concludono in chat: nessun pagamento online, nessun account da creare.
          </p>

          <address className="mt-4 not-italic text-neutral-500">
            {business.legalName && <span className="block">{business.legalName}</span>}
            {business.address && <span className="block">{business.address}</span>}
            {business.vat && <span className="block">P. IVA {business.vat}</span>}
            {business.rea && <span className="block">REA {business.rea}</span>}
            {business.email && (
              <a href={`mailto:${business.email}`} className="block hover:underline">
                {business.email}
              </a>
            )}
          </address>
        </div>

        <nav className="sm:justify-self-end" aria-label="Informazioni">
          <ul className="space-y-2 text-neutral-500">
            <li>
              <Link href="/come-funziona" className="hover:text-neutral-900 dark:hover:text-white">
                Come funziona
              </Link>
            </li>
            <li>
              <Link href="/contatti" className="hover:text-neutral-900 dark:hover:text-white">
                Contatti
              </Link>
            </li>
            <li>
              <Link href="/termini" className="hover:text-neutral-900 dark:hover:text-white">
                Termini di vendita
              </Link>
            </li>
            <li>
              <Link href="/privacy" className="hover:text-neutral-900 dark:hover:text-white">
                Privacy
              </Link>
            </li>
          </ul>
        </nav>
      </div>

      <div className="mx-auto max-w-6xl px-4 pb-10 text-xs text-neutral-400">
        © {anno} {business.legalName || shop.name}
      </div>
    </footer>
  );
}
