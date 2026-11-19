"""Statistiche giacenze: quali articoli finiscono prima della prossima consegna (vendite ultime 4 settimane)."""

from __future__ import annotations

from datetime import timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from .tabacchi_preordine import (
    ZERO,
    _day,
    _decimal,
    _iso,
    _text_code,
    famiglia_da_categoria,
    giorni_alla_consegna,
    inizio_vendite,
    is_dispositivo,
    media_riferimento,
    numero_json,
    prossimo_giorno_consegna,
    unita_ordine,
    unita_ordine_dispositivo,
)

SETTIMANE = 4
MARGINE_GIORNI = 2

ESAURITO = 'esaurito'
PRIMA_CONSEGNA = 'prima_consegna'
RISCHIO = 'rischio'
OK = 'ok'
FERMO = 'fermo'
STATI = (ESAURITO, PRIMA_CONSEGNA, RISCHIO, OK, FERMO)
ETICHETTE_STATO = {
    ESAURITO: 'Esaurito',
    PRIMA_CONSEGNA: 'Finisce prima dell’ordine',
    RISCHIO: 'Rischio',
    OK: 'Copre',
    FERMO: 'Fermo',
}


def vendite_settimanali(vendite, ultimo) -> list[Decimal]:
    """Totali delle 4 settimane che terminano all'ultimo giorno chiuso, dalla più vecchia alla più recente."""
    ultimo = _day(ultimo)
    totali = [ZERO] * SETTIMANE
    for key, value in (vendite or {}).items():
        giorni_fa = (ultimo - _day(key)).days
        if 0 <= giorni_fa < SETTIMANE * 7:
            totali[SETTIMANE - 1 - giorni_fa // 7] += _decimal(value)
    return totali


def trend_pct(settimane) -> int | None:
    """Ultima settimana rispetto alla media delle tre precedenti."""
    precedenti = settimane[:-1]
    base = sum(precedenti, ZERO) / Decimal(len(precedenti))
    if base <= 0:
        return None
    return int(((settimane[-1] - base) / base * 100).to_integral_value())


def stato_giacenza(giacenza, media, giorni_alla, margine=MARGINE_GIORNI) -> str:
    giacenza = _decimal(giacenza)
    media = _decimal(media)
    if media <= 0:
        return FERMO
    if giacenza <= 0:
        return ESAURITO
    giorni_fine = giacenza / media
    if giorni_fine <= giorni_alla:
        return PRIMA_CONSEGNA
    if giorni_fine < giorni_alla + margine:
        return RISCHIO
    return OK


def _unita(articolo) -> int:
    if is_dispositivo(articolo):
        return unita_ordine_dispositivo(articolo.get('pacstecca'))[0]
    unita, _kg = unita_ordine(articolo.get('prezzo'), articolo.get('prezzo_kg'), articolo.get('minimo_grammi'))
    return unita or 0


def calcola_giacenze(dati_agente, oggi, consegna=None, data_proiezione=None, *, giorno_consegna=0):
    """Proietta le giacenze alla data scelta e segnala chi finisce prima della prossima consegna."""
    dati = dati_agente or {}
    ultimo = dati.get('ultimo_giorno_chiuso')
    oggi = _day(oggi)
    consegna = _day(consegna) if consegna else prossimo_giorno_consegna(oggi, giorno_consegna)
    proiezione = _day(data_proiezione) if data_proiezione else consegna
    if proiezione < oggi:
        proiezione = oggi
    if not ultimo:
        return {
            'consegna': _iso(consegna),
            'data_proiezione': _iso(proiezione),
            'giorni_alla_consegna': 0,
            'giorni_alla_proiezione': 0,
            'righe': [],
            'riepilogo': _riepilogo([]),
        }
    distanza_consegna = giorni_alla_consegna(oggi, ultimo, consegna)
    distanza_proiezione = giorni_alla_consegna(oggi, ultimo, proiezione)
    inizio = inizio_vendite(oggi, ultimo)
    aperture = dati.get('giorni_apertura') or []
    righe = []
    for articolo in dati.get('articoli') or []:
        vendite = articolo.get('vendite_giornaliere') or {}
        media, esclusi = media_riferimento(
            vendite,
            articolo.get('giacenze_fine_giorno') or {},
            aperture,
            ultimo,
            _unita(articolo),
        )
        giacenza = _decimal(articolo.get('giacenza'))
        settimane = vendite_settimanali(vendite, ultimo)
        if media > 0:
            giorni_fine = int((max(ZERO, giacenza) / media).to_integral_value(rounding=ROUND_FLOOR))
            data_fine = inizio + timedelta(days=giorni_fine)
        else:
            giorni_fine = None
            data_fine = None
        alla_consegna = giacenza - media * distanza_consegna
        alla_data = giacenza - media * distanza_proiezione
        mancanti = int((-alla_consegna).to_integral_value(rounding=ROUND_CEILING)) if alla_consegna < 0 else 0
        mancanti_alla_data = int((-alla_data).to_integral_value(rounding=ROUND_CEILING)) if alla_data < 0 else 0
        righe.append({
            'aams': _text_code(articolo.get('aams')),
            'descrizione': ' '.join(str(articolo.get('descrizione') or '').split()),
            'famiglia': famiglia_da_categoria(articolo.get('categoria')),
            'tipo': 'dispositivo' if is_dispositivo(articolo) else 'tabacco',
            'giacenza': numero_json(giacenza, 1),
            'media': float(media),
            'giorni_esauriti': esclusi,
            'venduto_4_settimane': numero_json(sum(settimane, ZERO), 1),
            'settimane': [numero_json(valore, 1) for valore in settimane],
            'trend_pct': trend_pct(settimane),
            'giorni_fine': giorni_fine,
            'data_fine': _iso(data_fine) if data_fine else None,
            'alla_consegna': numero_json(alla_consegna, 1),
            'alla_data': numero_json(alla_data, 1),
            'mancanti': mancanti,
            'mancanti_alla_data': mancanti_alla_data,
            'stato': stato_giacenza(giacenza, media, distanza_consegna),
        })
    righe.sort(key=lambda riga: (
        STATI.index(riga['stato']) if riga['stato'] in STATI else 99,
        riga['giorni_fine'] if riga['giorni_fine'] is not None else 10**9,
        riga['descrizione'],
    ))
    return {
        'consegna': _iso(consegna),
        'data_proiezione': _iso(proiezione),
        'giorni_alla_consegna': distanza_consegna,
        'giorni_alla_proiezione': distanza_proiezione,
        'righe': righe,
        'riepilogo': _riepilogo(righe),
    }


def _riepilogo(righe) -> dict:
    conteggi = {stato: 0 for stato in STATI}
    for riga in righe:
        conteggi[riga['stato']] += 1
    return conteggi
