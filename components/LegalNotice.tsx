import { missingBusinessFields } from '@/lib/business';

/**
 * Avviso mostrato quando i dati dell'attività non sono ancora configurati.
 *
 * Meglio dichiarare che il documento è incompleto che pubblicare una pagina
 * legale che sembra completa e non lo è.
 */
export function LegalNotice() {
  const mancanti = missingBusinessFields();
  if (mancanti.length === 0) return null;

  return (
    <div className="mb-8 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-700/60 dark:bg-amber-950/40 dark:text-amber-200">
      <p className="font-semibold">Documento incompleto</p>
      <p className="mt-1">
        Mancano: {mancanti.join(', ')}. Compila le variabili d’ambiente{' '}
        <code className="rounded bg-amber-100 px-1 dark:bg-amber-900/60">NEXT_PUBLIC_LEGAL_NAME</code>,{' '}
        <code className="rounded bg-amber-100 px-1 dark:bg-amber-900/60">NEXT_PUBLIC_VAT</code>,{' '}
        <code className="rounded bg-amber-100 px-1 dark:bg-amber-900/60">NEXT_PUBLIC_ADDRESS</code>,{' '}
        <code className="rounded bg-amber-100 px-1 dark:bg-amber-900/60">NEXT_PUBLIC_CONTACT_EMAIL</code>{' '}
        e fai rileggere il testo a un professionista prima di pubblicare.
      </p>
    </div>
  );
}

/** Impaginazione comune alle pagine di testo. */
export function Prose({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <article className="mx-auto max-w-2xl py-4">
      <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
      <div className="mt-6 space-y-5 text-[15px] leading-relaxed text-neutral-700 dark:text-neutral-300 [&_h2]:mt-8 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-neutral-900 dark:[&_h2]:text-neutral-100 [&_li]:ml-5 [&_li]:list-disc [&_strong]:text-neutral-900 dark:[&_strong]:text-neutral-100">
        {children}
      </div>
    </article>
  );
}
