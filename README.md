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
├── config.py      # schema YAML tipizzato (selettori CSS, HTTP, ricarico)
├── inspect.py     # suggerisce i selettori CSS di una pagina
├── fetchers.py    # requests | selenium | file://, rate limiting, robots.txt
├── parser.py      # HTML -> Product (BeautifulSoup)
├── scraper.py     # paginazione, dedup, arricchimento da scheda prodotto
├── pricing.py     # ricarico sul prezzo fornitore
├── models.py      # Product / Variant
└── exporters/json_exporter.py   # catalogo JSON per il frontend
```

**Nessun selettore è hard-coded**: cambiare fornitore significa scrivere un
nuovo YAML, mai toccare il codice.

### Configurare un nuovo fornitore

```bash
cd scraper
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

**1. Salva una pagina del catalogo** dal browser (`Salva con nome > Pagina web,
completa`) e chiedi allo scraper quali selettori usare:

```bash
python -m catalog_scraper.inspect --html-file catalogo.html
```

Trova i nodi che contengono un prezzo, risale gli antenati e individua la
struttura che si ripete: quella è la card prodotto. Stampa un blocco YAML già
pronto **e un'anteprima dei dati estratti**, così vedi subito se ha indovinato.

```yaml
selectors:
  product_card: "article.product-item"
  title: ".product-item__title"
  url: ".product-item__link"
  price: ".amount"
  image: ".product-item__img"
```

**2. Le taglie stanno nella scheda prodotto**, non nella griglia: apri un
prodotto, salva l'HTML, cerca il `<select>` o i bottoni taglia e compila il
blocco `detail:`. Il placeholder ("Seleziona una taglia") viene scartato da
solo, e le opzioni `disabled` diventano varianti esaurite.

**3. Prova tutto** prima di toccare la rete:

```bash
cp config.example.yaml config.yaml     # incolla i selettori trovati
python -m catalog_scraper -c config.yaml --html-file catalogo.html --dry-run -v
```

**4. Genera il catalogo** che il frontend legge:

```bash
python -m catalog_scraper -c config.yaml
```

### Prova offline già pronta

`config.fornitore.yaml` punta a due fixture che simulano un fornitore reale
(griglia con prezzi netti, scheda con taglie e galleria). Esegue l'intera catena
senza rete, grazie al supporto `file://` del fetcher:

```bash
FIXTURES_DIR=$(pwd)/tests/fixtures \
  python -m catalog_scraper -c config.fornitore.yaml -o /tmp/prova.json --dry-run
```

```
[dry-run] Felpa Heavy Cotton        costo 24.50   -> vendita 49.90  | 5 varianti | 4 immagini
[dry-run] Pantalone Cargo Ripstop   costo 31.00   -> vendita 62.90  | 5 varianti | 4 immagini
[dry-run] Giacca Bomber Nylon       costo 58.00   -> vendita 104.90 | 5 varianti | 4 immagini
```

Usalo come modello: sostituisci gli URL `file://` con quelli del fornitore e i
selettori con quelli suggeriti da `inspect`.

### Ricarico sul prezzo del fornitore

Il prezzo estratto dal sito sorgente è un **costo**. Il blocco `pricing:` lo
trasforma in prezzo di vendita:

```yaml
pricing:
  markup_percent: 100          # 100 = raddoppia, 60 = +60%
  category_markup:
    Giacche: 80                # percentuali diverse per categoria
  rounding: charm              # 49,00 -> 49,90
  min_price: 0
  include_cost_in_output: false
```

Da riga di comando: `--markup 60` sovrascrive `markup_percent` (gli override per
categoria restano attivi).

Il ricarico si applica a prezzo pieno, prezzo scontato e prezzi delle singole
taglie con la stessa percentuale, così l'eventuale sconto mantiene la
proporzione. L'arrotondamento `charm` non scende **mai** sotto il prezzo
calcolato: meglio un centesimo in più che margine eroso.

> **Il costo del fornitore non finisce nel JSON.** Quel file viene incluso nel
> bundle del sito ed è leggibile da chiunque apra il browser: pubblicarlo
> significherebbe mostrare i tuoi margini ai clienti e ai concorrenti. Resta in
> `Product.extra` e compare solo se attivi `include_cost_in_output`, che serve
> per analisi interne — non per il file pubblicato.

Estrae titolo, categoria, prezzo pieno e scontato, **immagini multiple**
(`srcset`, `<picture>`, lazy-load `data-src`) e **varianti/taglie** con
disponibilità e prezzo per taglia. Un prodotto senza prezzo diventa
automaticamente "da concordare in chat".

**Aggiornare il catalogo**: rilancia lo scraper, committa `data/products.json`,
Vercel ricostruisce da solo. Il deploy è il momento in cui il catalogo cambia —
niente cache da invalidare.

```bash
cd scraper && python -m pytest -q     # 51 test su fixture HTML statiche
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
