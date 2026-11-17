"""Calcolo delle stecche tabacchi. Non legge i database: lavora sul JSON dell'agente."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP

CENT = Decimal('0.01')
GRAM = Decimal('0.001')
ZERO = Decimal('0')
GIORNI_VALIDI = (5, 7, 10, 14)
DEFAULT_COPERURA = 7
PESO_RECENTE = 7
PESO_MEDIO = 14
DEFAULT_GIORNO_CONSEGNA = 0  # lunedì

FAMIGLIE = (
    'Sigarette',
    'Tabacco riscaldato',
    'Trinciati',
    'Sigari e sigaretti',
    'Altri tabacchi',
)

_CATEGORIA_FAMIGLIA = {
    'SIGARETTE': 'Sigarette',
    'PRODOTTI DA INALAZIONE SENZA COMBUSTIONE (PLI)': 'Tabacco riscaldato',
    'TABACCHI DA INALAZIONE SENZA COMBUSTIONE': 'Tabacco riscaldato',
    'TRINCIATI PER SIGARETTE': 'Trinciati',
    'SIGARI': 'Sigari e sigaretti',
    'SIGARETTI': 'Sigari e sigaretti',
}


def _decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None or value == '':
        return ZERO
    return Decimal(str(value))


def _money(value) -> Decimal:
    return _decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def _kg(value) -> Decimal:
    return _decimal(value).quantize(GRAM, rounding=ROUND_HALF_UP)


def _day(value):
    if isinstance(value, date):
        return value
    text = str(value or '')[:10]
    return date.fromisoformat(text)


def _iso(day: date) -> str:
    return day.isoformat()


def _text_code(value) -> str:
    text = str(value or '').strip()
    if text.endswith('.0') and text[:-2].isdigit():
        return text[:-2]
    return text


def famiglia_da_categoria(categoria) -> str:
    key = ' '.join(str(categoria or '').strip().upper().split())
    return _CATEGORIA_FAMIGLIA.get(key, 'Altri tabacchi')


def unita_ordine(prezzo, prezzo_kg, minimo_grammi):
    """Restituisce (pacchetti_per_unita, kg_per_unita) oppure (None, motivo)."""
    prezzo = _decimal(prezzo)
    prezzo_kg = _decimal(prezzo_kg)
    minimo = _decimal(minimo_grammi)
    if prezzo <= 0 or prezzo_kg <= 0 or minimo <= 0:
        return None, 'parametri mancanti'
    raw = (minimo * prezzo_kg) / (Decimal('1000') * prezzo)
    unita = int(raw.to_integral_value(rounding=ROUND_HALF_UP))
    if unita <= 0:
        return None, 'unità zero'
    return unita, _kg(minimo / Decimal('1000'))


def giorni_alla_consegna(oggi, ultimo_chiuso, data_consegna) -> int:
    oggi = _day(oggi)
    ultimo = _day(ultimo_chiuso)
    consegna = _day(data_consegna)
    inizio = oggi if oggi > ultimo else ultimo + timedelta(days=1)
    return max(0, (consegna - inizio).days)


def inizio_vendite(oggi, ultimo_chiuso):
    oggi = _day(oggi)
    ultimo = _day(ultimo_chiuso)
    return oggi if oggi > ultimo else ultimo + timedelta(days=1)


def prossimo_giorno_consegna(oggi, weekday=DEFAULT_GIORNO_CONSEGNA):
    """Prossimo giorno di consegna Logista dopo oggi (0=lunedì … 6=domenica)."""
    day = _day(oggi)
    target = int(weekday) % 7
    delta = (target - day.weekday()) % 7
    if delta == 0:
        delta = 7
    return day + timedelta(days=delta)


def _peso(ultimo, day) -> int:
    age = (ultimo - day).days
    if age < PESO_RECENTE:
        return 3
    if age < PESO_MEDIO:
        return 2
    return 1


def media_riferimento(vendite, giacenze, giorni_apertura, ultimo, pacchetti_per_unita):
    """Media pesata pacchetti/giorno. Esclude i giorni in cui l'articolo era esaurito."""
    ultimo = _day(ultimo)
    start = ultimo - timedelta(days=27)
    unita = _decimal(pacchetti_per_unita)
    soglia = max(Decimal('2'), unita * Decimal('0.10'))
    sales = {_day(key): _decimal(value) for key, value in (vendite or {}).items()}
    stocks = {_day(key): _decimal(value) for key, value in (giacenze or {}).items()}
    opening = sorted({_day(day) for day in (giorni_apertura or []) if start <= _day(day) <= ultimo})
    numeratore = ZERO
    denominatore = ZERO
    esclusi = 0
    for day in opening:
        venduto = sales.get(day, ZERO)
        precedente = stocks.get(day - timedelta(days=1))
        if precedente is not None and precedente <= soglia and venduto <= max(precedente, ZERO):
            esclusi += 1
            continue
        peso = _peso(ultimo, day)
        numeratore += venduto * peso
        denominatore += Decimal(peso)
    media = (numeratore / denominatore) if denominatore else ZERO
    return media, esclusi


def proposta_unita(media, giacenza, pacchetti_per_unita, giorni_copertura, alla_distanza):
    media = _decimal(media)
    giacenza = _decimal(giacenza)
    unita_size = _decimal(pacchetti_per_unita)
    distanza = _decimal(alla_distanza)
    copertura = int(giorni_copertura)
    alla = max(ZERO, giacenza - media * distanza)
    mancano = media * copertura - alla
    soglia = Decimal('0.25') * unita_size
    if unita_size <= 0 or mancano < soglia:
        pezzi = 0
    else:
        pezzi = int((mancano / unita_size).to_integral_value(rounding=ROUND_CEILING))
    if media == 0:
        giorni_fine = None
    else:
        giorni_fine = int((max(ZERO, giacenza) / media).to_integral_value(rounding=ROUND_FLOOR))
    return {
        'alla_consegna': alla,
        'unita': pezzi,
        'giorni_fine': giorni_fine,
    }


def urgenza_data_fine(giorni_fine, giorni_alla, giorni_copertura):
    if giorni_fine is None:
        return 'normale'
    if giorni_fine <= int(giorni_alla):
        return 'rossa'
    if giorni_fine < int(giorni_alla) + int(giorni_copertura) + 3:
        return 'arancione'
    return 'normale'


def calcola_righe(dati_agente, oggi, *, giorni_copertura=DEFAULT_COPERURA, data_consegna=None):
    if int(giorni_copertura) not in GIORNI_VALIDI:
        raise ValueError('I giorni di copertura devono essere 5, 7, 10 o 14.')
    ultimo = (dati_agente or {}).get('ultimo_giorno_chiuso')
    if not ultimo:
        return [], []
    oggi = _day(oggi)
    consegna = _day(data_consegna or prossimo_giorno_consegna(oggi))
    distanza = giorni_alla_consegna(oggi, ultimo, consegna)
    inizio = inizio_vendite(oggi, ultimo)
    aperture = (dati_agente or {}).get('giorni_apertura') or []
    righe = []
    scartati = []
    for articolo in (dati_agente or {}).get('articoli') or []:
        aams = _text_code(articolo.get('aams'))
        unita_size, kg_or_reason = unita_ordine(
            articolo.get('prezzo'), articolo.get('prezzo_kg'), articolo.get('minimo_grammi'),
        )
        if unita_size is None:
            scartati.append({'aams': aams, 'motivo': kg_or_reason})
            continue
        kg_per_unita = kg_or_reason
        media, _esclusi = media_riferimento(
            articolo.get('vendite_giornaliere') or {},
            articolo.get('giacenze_fine_giorno') or {},
            aperture,
            ultimo,
            unita_size,
        )
        proposta = proposta_unita(
            media, articolo.get('giacenza'), unita_size, giorni_copertura, distanza,
        )
        pezzi = proposta['unita']
        prezzo = _money(articolo.get('prezzo'))
        pacchetti = pezzi * unita_size
        giorni_fine = proposta['giorni_fine']
        data_fine = None if giorni_fine is None else inizio + timedelta(days=giorni_fine)
        famiglia = famiglia_da_categoria(articolo.get('categoria'))
        urgenza = urgenza_data_fine(giorni_fine, distanza, giorni_copertura)
        righe.append({
            'aams': aams,
            'descrizione': ' '.join(str(articolo.get('descrizione') or '').split()),
            'famiglia': famiglia,
            'prezzo': prezzo,
            'pacchetti_per_unita': unita_size,
            'kg_per_unita': kg_per_unita,
            'giacenza': _decimal(articolo.get('giacenza')),
            'media': media,
            'giorni_fine': giorni_fine,
            'data_fine': _iso(data_fine) if data_fine else None,
            'urgenza': urgenza,
            'unita_proposte': pezzi,
            'unita': pezzi,
            'pacchetti': pacchetti,
            'kg': _kg(pezzi * kg_per_unita),
            'importo': _money(pacchetti * prezzo),
            'alla_consegna': proposta['alla_consegna'],
            'giorni_alla_consegna': distanza,
        })
    return righe, scartati


def numero_json(value, places=2):
    quantized = _decimal(value).quantize(Decimal('1').scaleb(-places), rounding=ROUND_HALF_UP)
    return float(quantized)


def _valore_riga(riga, key, default=0):
    if isinstance(riga, dict):
        return riga.get(key, default)
    return getattr(riga, key, default)


def totali_ordine(righe):
    attivi = [riga for riga in righe if int(_valore_riga(riga, 'unita') or 0) > 0]
    articoli = len(attivi)
    stecche = 0
    kg = ZERO
    importo = ZERO
    for riga in attivi:
        pezzi = int(_valore_riga(riga, 'unita') or 0)
        stecche += pezzi
        kg_riga = _valore_riga(riga, 'kg', None)
        if kg_riga is None:
            kg_riga = pezzi * _decimal(_valore_riga(riga, 'kg_per_unita'))
        kg += _decimal(kg_riga)
        importo += _decimal(_valore_riga(riga, 'importo') or 0)
    return {
        'articoli': articoli,
        'stecche': stecche,
        'kg': _kg(kg),
        'importo': _money(importo),
    }
