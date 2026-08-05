/**
 * Contatore ordini condiviso fra tutti i visitatori.
 *
 * Funziona se il progetto ha uno store Redis/KV collegato (variabili
 * KV_REST_API_URL e KV_REST_API_TOKEN, che Vercel inietta automaticamente
 * quando colleghi uno store dalla dashboard). L'incremento usa il comando
 * INCR di Redis, che è atomico: due ordini simultanei non possono ricevere lo
 * stesso numero.
 *
 * Senza store la funzione risponde `mode: "local"` e il client usa il proprio
 * contatore in localStorage — il sito resta interamente statico e gratuito.
 *
 * Nessuna dipendenza npm: si parla con lo store via REST.
 */

export const dynamic = 'force-dynamic';

export async function POST(): Promise<Response> {
  const year = new Date().getFullYear();
  const url = process.env.KV_REST_API_URL;
  const token = process.env.KV_REST_API_TOKEN;

  if (!url || !token) {
    return Response.json({ mode: 'local', year });
  }

  try {
    const response = await fetch(`${url}/incr/orders:${year}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    });

    if (!response.ok) {
      throw new Error(`store ha risposto ${response.status}`);
    }

    const data = (await response.json()) as { result?: number };
    if (typeof data.result !== 'number') {
      throw new Error('risposta senza contatore');
    }

    return Response.json({ mode: 'shared', year, number: data.result });
  } catch (error) {
    // Lo store non deve mai bloccare un ordine: si degrada al contatore locale.
    console.error('[order-number] fallback locale:', error);
    return Response.json({ mode: 'local', year });
  }
}
