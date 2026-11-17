"""Calcolo dei pacchi gratta. Non legge i database: lavora sul JSON dell'agente."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

CENT = Decimal('0.01')
ZERO = Decimal('0')
GIORNI_VALIDI = (3, 5, 7, 9)
DEFAULT_COPERURA = 7
MINIMO_ORDINE = Decimal('900')
AGGIO = Decimal('0.08')
CODICI_ESCLUSI_DEFAULT = ('3050',)
PESO_RECENTE = 7
PESO_MEDIO = 14


def _decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None or value == '':
        return ZERO
    return Decimal(str(value))


def _money(value) -> Decimal:
    return _decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def _day(value):
    if isinstance(value, date):
        return value
    text = str(value or '')[:10]
    return date.fromisoformat(text)


def _iso(day: date) -> str:
    return day.isoformat()


def giorni_alla_consegna(oggi, ultimo_chiuso, data_consegna) -> int:
    oggi = _day(oggi)
    ultimo = _day(ultimo_chiuso)
    consegna = _day(data_consegna)
    inizio = oggi if oggi > ultimo else ultimo + timedelta(days=1)
    return max(0, (consegna - inizio).days)


def _peso(ultimo, day) -> int:
    age = (ultimo - day).days
    if age < PESO_RECENTE:
        return 3
    if age < PESO_MEDIO:
        return 2
    return 1


def media_riferimento(vendite, giacenze, giorni_apertura, ultimo, biglietti_pacco):
    """Media pesata biglietti/giorno. Esclude i giorni in cui il gioco era esaurito."""
    ultimo = _day(ultimo)
    start = ultimo - timedelta(days=27)
    biglietti = _decimal(biglietti_pacco)
    soglia = max(Decimal('3'), biglietti * Decimal('0.05'))
    sales = {_day(key): _decimal(value) for key, value in (vendite or {}).items()}
    stocks = {_day(key): _decimal(value) for key, value in (giacenze or {}).items()}
    opening = sorted({_day(day) for day in (giorni_apertura or []) if start <= _day(day) <= ultimo})
    numeratore = ZERO
    denominatore = ZERO
    esclusi = 0
    for day in opening:
        venduto = sales.get(day, ZERO)
        precedente = stocks.get(day - timedelta(days=1))
        if precedente is not None and precedente <= soglia and venduto <= precedente:
            esclusi += 1
            continue
        peso = _peso(ultimo, day)
        numeratore += venduto * peso
        denominatore += peso
    media = (numeratore / denominatore) if denominatore else ZERO
    return media, esclusi


def settimane_vendite(vendite, ultimo):
    """S1 è la settimana che finisce in U, poi S2, S3, S4."""
    ultimo = _day(ultimo)
    sales = {_day(key): _decimal(value) for key, value in (vendite or {}).items()}
    totali = []
    for index in range(4):
        end = ultimo - timedelta(days=7 * index)
        start = end - timedelta(days=6)
        totali.append(int(sum(
            (qty for day, qty in sales.items() if start <= day <= end),
            ZERO,
        )))
    return totali


def proposta_pacchi(media, giacenza, biglietti_pacco, giorni_copertura, alla_distanza):
    media = _decimal(media)
    giacenza = _decimal(giacenza)
    biglietti = _decimal(biglietti_pacco)
    distanza = _decimal(alla_distanza)
    copertura = int(giorni_copertura)
    alla = max(ZERO, giacenza - media * distanza)
    servono = media * copertura
    mancano = servono - alla
    soglia = Decimal('0.25') * biglietti
    if biglietti <= 0 or mancano < soglia:
        pacchi = 0
    else:
        pacchi = int((mancano / biglietti).to_integral_value(rounding=ROUND_CEILING))
    if media == 0:
        coperti = None
    else:
        coperti = alla / media
    if pacchi > 0:
        gruppo = 'ordinare'
    elif coperti is not None and coperti < (copertura + 3):
        gruppo = 'occhio'
    else:
        gruppo = 'coperti'
    return {
        'alla_consegna': alla,
        'pacchi': pacchi,
        'giorni_coperti': coperti,
        'gruppo': gruppo,
    }


def calcola_righe(dati_agente, oggi, *, giorni_copertura=DEFAULT_COPERURA, data_consegna=None, codici_esclusi=None):
    if int(giorni_copertura) not in GIORNI_VALIDI:
        raise ValueError('I giorni di copertura devono essere 3, 5, 7 o 9.')
    ultimo = (dati_agente or {}).get('ultimo_giorno_chiuso')
    if not ultimo:
        return []
    oggi = _day(oggi)
    consegna = _day(data_consegna or (oggi + timedelta(days=1)))
    distanza = giorni_alla_consegna(oggi, ultimo, consegna)
    esclusi = {_text_code(code) for code in (codici_esclusi if codici_esclusi is not None else CODICI_ESCLUSI_DEFAULT)}
    aperture = (dati_agente or {}).get('giorni_apertura') or []
    righe = []
    for gioco in (dati_agente or {}).get('giochi') or []:
        codice = _text_code(gioco.get('codice'))
        biglietti = _decimal(gioco.get('biglietti_pacco'))
        media, giorni_esauriti = media_riferimento(
            gioco.get('vendite_giornaliere') or {},
            gioco.get('giacenze_fine_giorno') or {},
            aperture,
            ultimo,
            biglietti,
        )
        proposta = proposta_pacchi(
            media, gioco.get('giacenza'), biglietti, giorni_copertura, distanza,
        )
        fuori = codice in esclusi
        pacchi = 0 if fuori else proposta['pacchi']
        if fuori and pacchi == 0:
            if proposta['giorni_coperti'] is not None and proposta['giorni_coperti'] < (int(giorni_copertura) + 3):
                gruppo = 'occhio'
            else:
                gruppo = 'coperti'
        else:
            gruppo = 'ordinare' if pacchi > 0 else proposta['gruppo']
        valore = _money(gioco.get('valore_pacco'))
        righe.append({
            'id_articolo': str(gioco.get('id_articolo') or ''),
            'codice': codice,
            'descrizione': str(gioco.get('descrizione') or '').strip(),
            'prezzo': _money(gioco.get('prezzo')),
            'biglietti_pacco': biglietti,
            'valore_pacco': valore,
            'giacenza': _decimal(gioco.get('giacenza')),
            'media': media,
            'giorni_esauriti': giorni_esauriti,
            'settimane': settimane_vendite(gioco.get('vendite_giornaliere') or {}, ultimo),
            'pacchi_proposti': pacchi,
            'pacchi': pacchi,
            'giorni_coperti': proposta['giorni_coperti'],
            'gruppo': gruppo,
            'importo': _money(pacchi * valore),
            'escluso': fuori,
            'alla_consegna': proposta['alla_consegna'],
            'giorni_alla_consegna': distanza,
        })
    return righe


def _text_code(value) -> str:
    text = str(value or '').strip()
    if text.endswith('.0') and text[:-2].isdigit():
        return text[:-2]
    return text


def codici_esclusi_da_testo(raw):
    if raw is None or str(raw).strip() == '':
        return list(CODICI_ESCLUSI_DEFAULT)
    import json
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return list(CODICI_ESCLUSI_DEFAULT)
    if not isinstance(parsed, list):
        return list(CODICI_ESCLUSI_DEFAULT)
    return [_text_code(item) for item in parsed if _text_code(item)]


def aggio_stimato(totale) -> Decimal:
    return _money(_decimal(totale) * AGGIO)


def sotto_minimo(totale) -> bool:
    return _decimal(totale) < MINIMO_ORDINE


def numero_json(value):
    """Numero JSON con i centesimi, senza stringhe."""
    quantized = _money(value)
    return float(quantized)


def corpo_n8n(preordine, righe, *, azienda_id, azienda_nome, creato_da, data_ordine, letto_alle, callback_url, callback_token=None):
    """Contratto verso n8n. callback_token si omette nello scaricamento di prova."""
    selezionate = [riga for riga in righe if int(riga.pacchi or 0) > 0]
    voci = []
    pacchi = 0
    importo = ZERO
    for riga in selezionate:
        pezzi = int(riga.pacchi)
        biglietti = int(_decimal(riga.biglietti_pacco))
        valore = _money(riga.valore_pacco)
        riga_importo = _money(pezzi * valore)
        pacchi += pezzi
        importo += riga_importo
        voci.append({
            'codice': riga.codice,
            'id_articolo': riga.id_articolo,
            'descrizione': riga.descrizione,
            'prezzo': numero_json(riga.prezzo),
            'pacchi': pezzi,
            'biglietti_pacco': biglietti,
            'biglietti': pezzi * biglietti,
            'valore_pacco': numero_json(valore),
            'importo': numero_json(riga_importo),
            'pacchi_proposti': int(riga.pacchi_proposti or 0),
            'corretto_a_mano': bool(riga.corretto_a_mano),
        })
    importo = _money(importo)
    callback = {'url': callback_url}
    if callback_token:
        callback['token'] = callback_token
    return {
        'versione': 1,
        'preordine_id': preordine.id,
        'azienda': {'id': azienda_id, 'nome': azienda_nome},
        'creato_da': creato_da or '',
        'data_ordine': _iso(_day(data_ordine)),
        'data_consegna': _iso(_day(preordine.data_consegna)),
        'giorni_copertura': int(preordine.giorni_copertura),
        'dati_tabauno_del': letto_alle or '',
        'righe': voci,
        'totale': {
            'giochi': len(voci),
            'pacchi': pacchi,
            'importo': numero_json(importo),
            'aggio_stimato': numero_json(aggio_stimato(importo)),
        },
        'callback': callback,
    }
