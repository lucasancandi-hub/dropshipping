import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="py-24 text-center">
      <p className="text-sm font-semibold uppercase tracking-[0.14em] text-neutral-500">404</p>
      <h1 className="mt-2 text-3xl font-bold tracking-tight">Pagina non trovata</h1>
      <p className="mx-auto mt-3 max-w-md text-neutral-600 dark:text-neutral-300">
        L’articolo che cercavi potrebbe essere esaurito o non essere più a catalogo.
      </p>
      <Link href="/" className="btn-solid mt-8">
        Torna al catalogo
      </Link>
    </div>
  );
}
