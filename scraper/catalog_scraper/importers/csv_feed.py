"""Lettura di un listino da CSV (foglio di calcolo esportato).

È il caso di chi compila i prodotti a mano: una riga per articolo, i nomi
delle colonne dichiarati nel `mapping` della configurazione.

Le celle che contengono più valori — foto, taglie — si separano con il
carattere indicato in `feed.list_separator` (di default `|`).
Il risultato viene poi trattato esattamente come un feed JSON.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

from ..config import FeedConfig

logger = logging.getLogger(__name__)

# Delimitatori plausibili: Excel italiano esporta con il punto e virgola.
_DELIMITERS = ";,\t|"


def detect_delimiter(sample: str, configured: str = "") -> str:
    """Delimitatore del CSV, dichiarato o dedotto dalla prima riga."""
    if configured:
        return configured
    try:
        return csv.Sniffer().sniff(sample, delimiters=_DELIMITERS).delimiter
    except csv.Error:
        # Sniffer fallisce su file con una sola colonna: si conta a mano.
        prima_riga = sample.splitlines()[0] if sample.splitlines() else ""
        conteggi = {d: prima_riga.count(d) for d in _DELIMITERS}
        migliore = max(conteggi, key=lambda d: conteggi[d])
        return migliore if conteggi[migliore] else ","


def split_cell(value: Any, separator: str) -> list[str]:
    """Cella multivalore -> lista. Accetta anche la virgola come ripiego."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]

    text = str(value).strip()
    if not text:
        return []

    pezzi = text.split(separator) if separator in text else text.split(",")
    return [p.strip() for p in pezzi if p.strip()]


def load_rows(feed: FeedConfig) -> list[dict[str, Any]]:
    """Legge il CSV e normalizza le celle multivalore in liste.

    Restituisce righe nella stessa forma di un feed JSON, così a valle il
    percorso è identico.
    """
    percorso = Path(feed.file)
    # utf-8-sig: Excel antepone un BOM che altrimenti finisce nel primo header.
    testo = percorso.read_text(encoding="utf-8-sig", errors="replace")

    delimiter = detect_delimiter(testo[:2000], feed.delimiter)
    logger.info("CSV %s: delimitatore '%s'", percorso.name, delimiter)

    lettore = csv.DictReader(testo.splitlines(), delimiter=delimiter)
    mapping = feed.mapping

    # Colonne che vanno lette come elenchi invece che come singoli valori.
    colonne_lista = {
        c for c in (mapping.images, mapping.variants, mapping.variants_out) if c
    }

    righe: list[dict[str, Any]] = []
    for grezza in lettore:
        riga: dict[str, Any] = {}
        for chiave, valore in grezza.items():
            if chiave is None:
                continue
            nome = chiave.strip()
            if nome in colonne_lista:
                riga[nome] = split_cell(valore, feed.list_separator)
            else:
                riga[nome] = valore.strip() if isinstance(valore, str) else valore

        # Le taglie esaurite arrivano da una colonna a parte: qui diventano
        # elementi con disponibilità falsa, così il modello resta uno solo.
        #
        # Una taglia elencata in entrambe le colonne conta una volta sola ed è
        # esaurita: è l'errore di compilazione più probabile, e vale la
        # lettura prudente.
        if mapping.variants_out and mapping.variants:
            disponibili = riga.get(mapping.variants) or []
            esaurite = riga.get(mapping.variants_out) or []

            normalizza = lambda t: str(t).strip().lower()  # noqa: E731
            esaurite_norm = {normalizza(t) for t in esaurite}
            gia_elencate = {normalizza(t) for t in disponibili}

            elenco = list(disponibili) + [t for t in esaurite if normalizza(t) not in gia_elencate]

            riga[mapping.variants] = [
                {mapping.variant_label: taglia, "__in_stock": normalizza(taglia) not in esaurite_norm}
                for taglia in elenco
            ]

        righe.append(riga)

    logger.info("CSV %s: %d righe lette", percorso.name, len(righe))
    return righe
