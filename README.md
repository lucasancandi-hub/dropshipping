# Catalogo chat-first — Next.js + scraper Python

Catalogo e-commerce senza checkout: l'utente sfoglia i prodotti, sceglie taglie
e quantità, e chiude l'ordine su WhatsApp con un messaggio già scritto che
contiene articoli, spedizione stimata, totale e un numero d'ordine progressivo.

Nessun database, nessun CMS, nessun backend da mantenere: il catalogo è un file
JSON generato dallo scraper, il carrello vive nel browser, il sito è statico.

| Componente | Percorso | Cosa fa |
|---|---|---|
| **Ingestion** | `scraper/` | Estrae il catalogo del fornitore e scrive `data/products.json` |
| **Catalogo** | `data/products.json` | Contratto dati fra scraper e frontend |
| **Frontend** | `app/`, `components/`, `lib/` | Next.js App Router, griglia, carrello e checkout WhatsApp |

```
pagina catalogo fornitore
        │  scraper Python (BeautifulSoup / Selenium)
        ▼
  data/products.json  ──►  build Next.js (pagine statiche)
                                    │
                    carrello nel browser (localStorage)
                                    │
                        ORD-2026-001 + messaggio precompilato
                                    ▼
                             chat WhatsApp = ordine
```

---

## Avvio rapido

```bash
npm install
npm run dev            # http://localhost:3000
```

Il catalogo demo (8 prodotti) è già in `data/products.json`, quindi l'app parte
senza configurare nulla.

## Deploy su Vercel

1. Push del repository su GitHub.
2. Su Vercel: **Add New → Project**, seleziona il repo, **Deploy**.

Vercel riconosce Next.js da solo: nessun `vercel.json`, nessun build command da
scrivere. Il piano gratuito basta — le pagine sono statiche e l'unica funzione
serverless (`/api/order-number`) è opzionale.

Variabili d'ambiente (tutte facoltative, vedi `.env.example`):

| Variabile | Default | A cosa serve |
|---|---|---|
| `NEXT_PUBLIC_WHATSAPP_PHONE` | `393408857026` | Numero destinatario degli ordini |
| `NEXT_PUBLIC_SHOP_NAME` | `Atelier` | Nome in header e metadati |
| `NEXT_PUBLIC_SHIPPING_MODE` | `flat` | `flat`, `quantity` o `none` |
| `NEXT_PUBLIC_SHIPPING_FLAT` | `7.90` | Tariffa fissa |
| `NEXT_PUBLIC_SHIPPING_BASE` / `_PER_ITEM` | `0` / `2.00` | Base + tariffa per articolo |
| `NEXT_PUBLIC_SHIPPING_FREE_OVER` | `99` | Soglia spedizione gratuita (0 = disattiva) |
| `NEXT_PUBLIC_ORDER_PREFIX` / `_DIGITS` | `ORD` / `3` | Formato del codice ordine |

---

## 1. Scraper (Python)

```
scraper/catalog_scraper/
├── config.py      # schema YAML tipizzato (selettori CSS, HTTP)
├── fetchers.py    # requests | selenium, rate limiting, robots.txt
├── parser.py      # HTML -> Product (BeautifulSoup)
├── scraper.py     # paginazione, dedup, arricchimento da scheda prodotto
├── models.py      # Product / Variant
└── exporters/json_exporter.py   # catalogo JSON per il frontend
```

**Nessun selettore è hard-coded**: cambiare fornitore significa scrivere un
nuovo YAML, mai toccare il codice.

```bash
cd scraper
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml     # adatta i selettori CSS

# Tara i selettori su una pagina salvata, senza toccare la rete
python -m catalog_scraper -c config.yaml --html-file pagina.html --dry-run -v

# Genera il catalogo che il frontend legge
python -m catalog_scraper -c config.yaml
```

Estrae titolo, categoria, prezzo pieno e scontato, **immagini multiple**
(`srcset`, `<picture>`, lazy-load `data-src`) e **varianti/taglie** con
disponibilità e prezzo per taglia. Un prodotto senza prezzo diventa
automaticamente "da concordare in chat".

**Aggiornare il catalogo**: rilancia lo scraper, committa `data/products.json`,
Vercel ricostruisce da solo. Il deploy è il momento in cui il catalogo cambia —
niente cache da invalidare.

```bash
cd scraper && python -m pytest -q     # 22 test su fixture HTML statiche
```

### Uso responsabile

Lo scraper rispetta `robots.txt` (attivo di default) e applica un ritardo fra le
richieste. Prima di puntarlo su un sito di terzi verifica di averne diritto:
termini di servizio, copyright su foto e testi, accordo con il fornitore. Per i
cataloghi dropshipping il canale corretto è quasi sempre il feed/API del
fornitore, non l'HTML.

---

## 2. Frontend (Next.js)

```
app/
├── layout.tsx                 # header, provider carrello, drawer
├── page.tsx                   # griglia catalogo (statica)
├── prodotto/[slug]/page.tsx   # scheda prodotto (pre-generata)
└── api/order-number/route.ts  # contatore ordini condiviso (opzionale)
lib/
├── types.ts     # contratto dati, gemello di json_exporter.py
├── catalog.ts   # accesso al JSON, inlinato nel bundle a build time
├── cart.tsx     # stato carrello + localStorage
├── shipping.ts  # stima spedizione e totali
├── order.ts     # codice progressivo, messaggio, link WhatsApp
└── config.ts    # configurazione da env con default funzionanti
```

Tutte le schede prodotto sono **pre-generate** (`generateStaticParams`): a
runtime non c'è rendering, solo HTML servito da CDN.

### Immagini

Le foto restano `<img>` normali invece di `next/image`. Ragione: le URL arrivano
dal CDN del fornitore e cambiano con lui, quindi servirebbe mantenere una
allowlist di host in `next.config.mjs` — e ogni immagine consumerebbe quota di
ottimizzazione su Vercel. Così il sito resta portabile su qualunque host statico
e a costo zero.

### Carrello

React context + `localStorage`, idratato in un effetto per non generare mismatch
fra HTML statico e primo render. Ogni riga tiene prodotto, taglia, quantità e
prezzo unitario risolto (la variante può avere un prezzo suo diverso da quello
del prodotto).

### Prezzo e spedizione

Un prodotto senza prezzo mostra "Prezzo da concordare in chat", resta
aggiungibile al carrello ed è escluso dal subtotale; il totale viene marcato
`(+ voci da concordare)` per non spacciare una cifra parziale per definitiva.

La spedizione è una stima: tariffa fissa, base + tariffa per articolo, oppure
sempre da concordare. La soglia di gratuità vale per entrambe le modalità
numeriche.

### Numero d'ordine progressivo

Formato `ORD-2026-001`, azzerato ogni anno.

Di default il contatore è in `localStorage`, quindi **progressivo per browser**:
due visitatori diversi possono ricevere lo stesso numero. Per un sito che
raccoglie ordini in chat è in genere sufficiente — il numero serve a te e al
cliente per ritrovare la conversazione, e la chat resta la fonte di verità.

Per una numerazione **realmente globale** basta collegare uno store Redis/KV dal
pannello Vercel: la route `/api/order-number` usa il comando `INCR`, atomico, e
il client la preferisce automaticamente. Senza store risponde `mode: "local"` e
si torna al contatore del browser. Nessuna dipendenza npm: si parla con lo store
via REST.

### Apertura di WhatsApp

Il codice ordine può arrivare da una chiamata di rete, quindi la scheda va
aperta **prima** dell'`await`: `window.open()` invocata dopo una promise viene
bloccata dai browser come popup. Se l'apertura fallisce o restituisce una
finestra su cui non si può scrivere, si ripiega sulla navigazione nella scheda
corrente — l'ordine parte comunque.

Messaggio generato:

```
🛒 *Nuovo Ordine #ORD-2026-001*
----------------------------------
• Felpa Oversize Nera - Taglia: L - Q.tà: 2 - Prezzo: 129,80 €
• Cappello in Feltro - Taglia: Unica - Q.tà: 1 - Prezzo: Prezzo da concordare in chat
----------------------------------
📦 Spedizione: Gratuita
💰 *Totale Stimato: 129,80 € (+ voci da concordare)*

Ciao! Vorrei confermare questo ordine.
```

I segmenti con valori vuoti spariscono: su un prodotto senza taglia non resta un
"Taglia:" orfano.

---

## 3. Design

Tailwind v4, nessun file di configurazione: il tema vive in `@theme` dentro
`app/globals.css` e genera le utility (`bg-brand`, `rounded-card`).

Impostazione visiva: immagini protagoniste in griglia `aspect-3/4`, una sola
azione per schermata, tipografia essenziale, colonna dati sticky sulla scheda
prodotto, drawer laterale per il carrello. Focus sempre visibile, `Esc` e focus
trap sul drawer, `prefers-reduced-motion` e dark mode automatica.

Il verde è riservato **solo** alla CTA di chat: le azioni neutre (aggiungi al
carrello) sono nere, così la gerarchia resta leggibile.

---

## Requisiti

* Node 20+ (frontend)
* Python 3.10+ (scraper)
