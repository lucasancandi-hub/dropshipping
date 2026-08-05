/**
 * Dati dell'attività.
 *
 * Servono al footer e alle pagine legali. Sono obblighi informativi per il
 * commercio elettronico (art. 17 D.lgs. 70/2003), non decorazione: finché
 * mancano, le pagine legali lo dichiarano invece di fingersi complete.
 */

const env = (key: string): string => (process.env[key] || '').trim();

export const business = {
  /** Ragione sociale o nome e cognome del titolare. */
  legalName: env('NEXT_PUBLIC_LEGAL_NAME'),
  vat: env('NEXT_PUBLIC_VAT'),
  /** Sede: via, CAP, città, provincia. */
  address: env('NEXT_PUBLIC_ADDRESS'),
  email: env('NEXT_PUBLIC_CONTACT_EMAIL'),
  /** Iscrizione al registro imprese, se presente. */
  rea: env('NEXT_PUBLIC_REA'),
} as const;

/** Campi obbligatori mancanti: elenco vuoto = si può pubblicare. */
export function missingBusinessFields(): string[] {
  const required: Array<[keyof typeof business, string]> = [
    ['legalName', 'ragione sociale'],
    ['vat', 'partita IVA'],
    ['address', 'sede legale'],
    ['email', 'email di contatto'],
  ];

  return required.filter(([key]) => !business[key]).map(([, label]) => label);
}

export const businessIsComplete = (): boolean => missingBusinessFields().length === 0;
