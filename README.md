# Dropshipping — catalogo WooCommerce con chiusura ordine in chat

Architettura e-commerce "chat-first": WooCommerce serve come catalogo e motore
prodotti, ma carrello e checkout sono disaccoppiati. L'ordine si chiude su
WhatsApp (o Telegram) con un messaggio già scritto che contiene prodotto,
prezzo, taglia e link.

Due componenti indipendenti:

| Componente | Percorso | Cosa fa |
|---|---|---|
| **Data ingestion** | `scraper/` | Estrae il catalogo da una pagina a griglia e lo porta in WooCommerce via CSV o REST API |
| **Frontend Woo** | `wp-content/plugins/woo-chat-lead-gen/` | Disattiva carrello/pagamenti e sostituisce "Aggiungi al carrello" con il CTA chat |
| Alternative | `snippets/` | Versione compatta per `functions.php` + mockup Tailwind |

---

## 1. Modulo di scraping & data ingestion (Python)

```
scraper/
├── catalog_scraper/
│   ├── config.py          # schema YAML tipizzato (selettori, HTTP, credenziali)
│   ├── fetchers.py        # requests | selenium, rate limiting, robots.txt
│   ├── parser.py          # HTML -> Product (BeautifulSoup, selettori da config)
│   ├── scraper.py         # paginazione, dedup, arricchimento da scheda prodotto
│   ├── models.py          # Product / Variant (contratto fra parser ed exporter)
│   ├── exporters/
│   │   ├── csv_exporter.py  # CSV nativo "Prodotti > Importa" di WooCommerce
│   │   └── woo_api.py       # REST API v3, upsert idempotente per SKU
│   └── cli.py
├── config.example.yaml
└── tests/                 # 21 test su fixture HTML statiche
```

**Nessun selettore è hard-coded**: cambiare sito sorgente significa scrivere un
nuovo YAML, mai toccare il codice.

### Installazione

```bash
cd scraper
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml   # poi adatta i selettori CSS
```

### Uso

```bash
# 1. Verifica i selettori su una pagina salvata in locale (nessuna richiesta di rete)
python -m catalog_scraper -c config.yaml --html-file pagina-salvata.html -v

# 2. Scraping completo -> CSV pronto per l'importatore WooCommerce
python -m catalog_scraper -c config.yaml -o output/catalogo.csv

# 3. Import diretto via REST API (prima in prova)
export WOO_CONSUMER_KEY=ck_xxx WOO_CONSUMER_SECRET=cs_xxx
python -m catalog_scraper -c config.yaml --push --dry-run
python -m catalog_scraper -c config.yaml --push --no-csv
```

Opzioni utili: `--json dump.json` (dump grezzo), `--limit 10` (prova su pochi
prodotti), `-v` (log di debug).

### Cosa estrae

Titolo, categoria, prezzo pieno e scontato, **immagini multiple** (gestisce
`srcset`, `<picture>` e lazy-loading `data-src`), **varianti/taglie** con
disponibilità e prezzo per taglia, SKU, descrizione breve e lunga.

* **Paginazione**: `?page=N`, link "successiva", o pagina singola.
* **JS/infinite scroll**: `http.engine: selenium` + `http.scroll: true`.
* **Idempotenza**: senza SKU sorgente ne genera uno deterministico
  (`DS-<slug>-<hash url>`), così rilanciare l'import aggiorna invece di duplicare.
* **Prodotti variabili**: il CSV genera una riga `variable` + una riga
  `variation` per taglia; la REST API crea il prodotto padre e sincronizza le
  varianti in batch, cancellando quelle sparite dal catalogo.

### Test

```bash
cd scraper && python -m pytest -q     # 21 passed
```

### Uso responsabile

Lo scraper rispetta `robots.txt` (`http.respect_robots`, attivo di default) e
applica un ritardo fra le richieste (`http.delay`). Prima di puntarlo su un
sito di terzi verifica di averne diritto: termini di servizio, copyright su
foto e testi, eventuale accordo con il fornitore. Per i cataloghi dropshipping
il canale corretto è quasi sempre il feed/API del fornitore, non l'HTML.

---

## 2. Frontend WooCommerce (PHP / JS)

Plugin `Woo Chat Lead Gen` — `wp-content/plugins/woo-chat-lead-gen/`.

### Installazione

1. Copia la cartella `woo-chat-lead-gen` in `wp-content/plugins/` (o caricala
   come ZIP).
2. Attiva il plugin.
3. **WooCommerce → Chat Lead Gen**: inserisci il numero in formato
   internazionale senza `+` (es. `393401234567`) e salva.

### a) Carrello e pagamenti disattivati

Il blocco è server-side, non solo estetico (`class-wclg-catalog-mode.php`):

| Hook | Effetto |
|---|---|
| `woocommerce_add_to_cart_validation` → `false` | rifiuta form, link `?add-to-cart=`, AJAX e blocchi |
| `template_redirect` | carrello e checkout reindirizzano allo shop |
| `woocommerce_available_payment_gateways` → `[]` | nessun gateway disponibile |
| `woocommerce_widget_cart_is_hidden` → `true` | niente mini-carrello nei temi |

### b) e c) Pulsante chat con messaggio precompilato

* **Griglia catalogo**: `woocommerce_loop_add_to_cart_link` sostituisce il
  pulsante. Sui prodotti con varianti punta alla scheda (lì si sceglie la
  taglia); in alternativa può aprire direttamente la chat.
* **Scheda prodotto**:
  * prodotti *semplici* → si rimuove `woocommerce_template_single_add_to_cart`;
  * prodotti *variabili/raggruppati* → il form resta (serve il menu taglie) e
    si "ingoiano" via output buffering solo quantità e bottone nativo, con
    fallback che ristampa il buffer se un tema salta gli hook.
* **Link generato**:
  `https://api.whatsapp.com/send?phone=IL_MIO_NUMERO&text=…`
  Il testo è codificato con `rawurlencode` (RFC 3986): gli a capo diventano
  `%0A` e gli spazi `%20`. `urlencode` produrrebbe `+`, che WhatsApp
  mostrerebbe letteralmente nel messaggio.

Esempio di messaggio generato:

```
Ciao! 👋 Vorrei ordinare questo articolo:

*Felpa Oversize Nera*
Taglia: M
Quantità: 2
Prezzo: € 64,90
Codice: FLP-OVR-NER

https://shop.test/prodotto/felpa-oversize-nera/
```

Il template è modificabile dalle impostazioni. Segnaposto disponibili:
`{product}` `{price}` `{variant}` `{sku}` `{qty}` `{url}` `{shop}`.
**Le righe con soli segnaposto vuoti spariscono**: su un prodotto senza taglie
non resta un "Taglia:" orfano.

`{variant}` contiene i valori scelti uniti da ` / ` (es. `M / Nero`); con più
attributi conviene cambiare l'etichetta della riga in `Variante: {variant}`.

### Aggiornamento dinamico (JS)

`assets/js/wclg-frontend.js` si aggancia agli eventi di
`wc-add-to-cart-variation.js` (`found_variation`, `reset_data`) e ricostruisce
l'href a ogni cambio di taglia, aggiornando anche **prezzo della variante** e
**SKU della variante**. Il selettore di quantità è indipendente dal carrello e
alimenta solo il messaggio. Senza JS il link resta valido con i dati del
prodotto padre (progressive enhancement).

Al click viene emesso `wclg_chat_click` su `window.dataLayer` (GA4/GTM) e un
evento DOM `wclg:click`.

### Estendere senza toccare il plugin

```php
// Aggiunge un segnaposto {colore} al messaggio
add_filter( 'wclg_message_vars', function ( $vars, $product ) {
    $vars['colore'] = $product->get_attribute( 'pa_colore' );
    return $vars;
}, 10, 2 );
```

Altri filtri: `wclg_message_text`, `wclg_chat_url`, `wclg_button_label`,
`wclg_reassurance_text`, `wclg_cart_redirect_url`, `wclg_settings`.

Shortcode: `[wclg_chat_button id="123" label="Ordina ora"]`.

### Versione compatta

`snippets/functions-php-snippet.php` — ~200 righe autoconsistenti da incollare
nel `functions.php` di un tema **child**. Stessa logica, senza pannello
impostazioni: si configura con due costanti in cima al file.

---

## 3. UI/UX

`assets/css/wclg-frontend.css` (namespace `.wclg-*`, tutto in custom
properties, nessuna regola globale):

* scheda prodotto a due colonne da 900px, con la colonna dati **sticky**;
* galleria e miniature in `grid` fluida con `aspect-ratio` — niente float dei temi;
* griglia catalogo `auto-fill / minmax(230px, 1fr)`;
* CTA da 54px, area tap conforme alle linee guida mobile, `:focus-visible` visibile;
* barra CTA fissa su mobile che **rispecchia il link principale** (quindi anche
  la taglia scelta), mostrata via `IntersectionObserver` quando il CTA esce dallo schermo;
* supporto `prefers-reduced-motion` e `prefers-color-scheme: dark`.

Per ridefinire la palette dal tema basta sovrascrivere le variabili:

```css
:root { --wclg-accent: #0a7c66; --wclg-radius: 8px; }
```

Equivalente in utility class: `snippets/tailwind-product-page.html`.

---

## Flusso completo

```
pagina catalogo sorgente
        │  catalog_scraper (BeautifulSoup / Selenium)
        ▼
   Product[]  ──► CSV WooCommerce  ──► Prodotti > Importa
        │
        └────────► REST API v3 (upsert per SKU) ──► prodotti + varianti
                                                          │
                                                          ▼
                                          WooCommerce in modalità catalogo
                                                          │
                                     CTA "Ordina via WhatsApp" con messaggio
                                     precompilato (prodotto, prezzo, taglia)
                                                          ▼
                                                   conversazione = lead
```

## Requisiti

* Python 3.10+ (scraper)
* WordPress 6.0+, WooCommerce 7.0+, PHP 7.4+ (plugin, compatibile HPOS)
