import { CatalogView } from '@/components/CatalogView';
import { getCategories, getProducts } from '@/lib/catalog';

/**
 * Home: griglia catalogo.
 *
 * Server component: il JSON è già nel bundle, la pagina è generata a build
 * time e servita statica.
 */
export default function HomePage() {
  const products = getProducts();

  return (
    <>
      <section className="mb-9 max-w-2xl">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Nuovi arrivi</h1>
        <p className="mt-2.5 text-neutral-600 dark:text-neutral-300">
          Scegli i capi, aggiungili al carrello e invia l’ordine su WhatsApp: confermiamo
          disponibilità, spedizione e totale in chat.
        </p>
      </section>

      <CatalogView products={products} categories={getCategories()} />
    </>
  );
}
