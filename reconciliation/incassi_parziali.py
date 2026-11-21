"""Incassi parziali della giornata aperta (settori configurati) — lettura TabaUno on-demand."""

from __future__ import annotations

import time
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import TabaUnoRequest
from .tabauno_portal import agent_is_online, expire_requests

# Chiave API · codice TabaUno · emoji · etichetta
SETTORI = (
    ('tabacchi', '01', '🚬', 'Tabacchi'),
    ('gratta', '90', '🎟️', 'Gratta e Vinci'),  # solo vendite; vincite 300 escluse
    ('caffe', '02', '☕', 'Caffè'),
    ('rosticceria', '09', '🍕', 'Rosticceria'),
    ('pasticceria', '03', '🥐', 'Pasticceria'),
)
SETTORI_BY_CODICE = {codice: (chiave, emoji, label) for chiave, codice, emoji, label in SETTORI}
SETTORI_BY_CHIAVE = {chiave: (codice, emoji, label) for chiave, codice, emoji, label in SETTORI}

LETTURA_TIMEOUT = 60
LETTURA_POLL = 1.5
GIORNI_IT = ('lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom')
CENT = Decimal('0.01')


class ParzialiError(Exception):
    def __init__(self, messaggio: str, *, status: int = 503):
        super().__init__(messaggio)
        self.messaggio = messaggio
        self.status = status


def _money(value) -> Decimal:
    if value is None or value == '':
        return Decimal('0').quantize(CENT)
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def formatta_euro(value) -> str:
    n = _money(value)
    intero, frac = f'{n:.2f}'.split('.')
    # Migliaia con punto (IT)
    sign = ''
    if intero.startswith('-'):
        sign = '-'
        intero = intero[1:]
    parti = []
    while intero:
        parti.append(intero[-3:])
        intero = intero[:-3]
    return f'{sign}{".".join(reversed(parti))},{frac} €'


def formatta_data_corta(day: date) -> str:
    return f'{GIORNI_IT[day.weekday()]} {day.day:02d}/{day.month:02d}'


def formatta_gg_mm(day: date) -> str:
    return f'{day.day:02d}/{day.month:02d}'


def formatta_ora(value) -> str:
    if not value:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime('%H:%M')
    text = str(value).strip()
    dt = parse_datetime(text)
    if dt:
        if timezone.is_aware(dt):
            dt = timezone.localtime(dt)
        return dt.strftime('%H:%M')
    if 'T' in text:
        text = text.split('T', 1)[1]
    parti = text.replace('.', ':').split(':')
    if len(parti) >= 2 and parti[0].isdigit() and parti[1].isdigit():
        return f'{int(parti[0]):02d}:{int(parti[1]):02d}'
    return text[:5]


def _parse_day(value) -> date | None:
    text = str(value or '').strip()[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def accoda_parziali(company, user=None) -> tuple[TabaUnoRequest, bool]:
    expire_requests()
    existing = TabaUnoRequest.objects.filter(
        company=company,
        tipo=TabaUnoRequest.TIPO_PARZIALI_CASSA,
        status__in=(TabaUnoRequest.PENDING, TabaUnoRequest.PROCESSING),
    ).order_by('created_at', 'id').first()
    if existing:
        return existing, False
    row = TabaUnoRequest.objects.create(
        company=company,
        date=timezone.localdate(),
        tipo=TabaUnoRequest.TIPO_PARZIALI_CASSA,
        parametri={},
        requested_by=user,
    )
    return row, True


def attendi_lettura(row: TabaUnoRequest, timeout: float = LETTURA_TIMEOUT) -> TabaUnoRequest | None:
    scadenza = time.monotonic() + timeout
    while True:
        expire_requests()
        row.refresh_from_db()
        if row.status == TabaUnoRequest.DONE:
            return row if isinstance(row.payload, dict) else None
        if row.status in (TabaUnoRequest.ERROR, TabaUnoRequest.EXPIRED):
            return None
        if time.monotonic() >= scadenza:
            return None
        time.sleep(LETTURA_POLL)


def normalizza_payload(payload: dict, *, oggi: date | None = None) -> dict:
    """Da payload agente a struttura API: settori per chiave + totale + flag."""
    oggi = oggi or timezone.localdate()
    raw_settori = payload.get('settori') or []
    by_codice = {}
    for riga in raw_settori:
        codice = str(riga.get('codice') or '').strip()
        if not codice:
            continue
        by_codice[codice] = {
            'importo': float(_money(riga.get('importo'))),
            'n': int(riga.get('n') or 0),
            'descrizione': riga.get('descrizione') or '',
        }

    settori = {}
    totale = Decimal('0')
    for chiave, codice, emoji, label in SETTORI:
        info = by_codice.get(codice) or {'importo': 0.0, 'n': 0, 'descrizione': label}
        importo = _money(info['importo'])
        settori[chiave] = {
            'codice': codice,
            'emoji': emoji,
            'label': label,
            'importo': float(importo),
            'n': int(info.get('n') or 0),
        }
        totale += importo

    data_cassa = _parse_day(payload.get('data'))
    cassa_non_oggi = bool(data_cassa and data_cassa != oggi)
    nessuna_vendita = int(payload.get('righe_totali') or 0) == 0 and all(
        settori[k]['n'] == 0 for k in settori
    )

    return {
        'data': (data_cassa or oggi).isoformat(),
        'oggi': oggi.isoformat(),
        'ultima_ora': formatta_ora(payload.get('ultima_ora')),
        'letto_alle': payload.get('letto_alle') or '',
        'righe_totali': int(payload.get('righe_totali') or 0),
        'settori': settori,
        'totale': float(totale),
        'cassa_non_oggi': cassa_non_oggi,
        'nessuna_vendita': nessuna_vendita,
    }


def testo_telegram(dati: dict) -> str:
    oggi = _parse_day(dati.get('oggi')) or timezone.localdate()
    data_cassa = _parse_day(dati.get('data')) or oggi
    linee = [
        f'💶 <b>Incassi di oggi – {formatta_data_corta(oggi)}</b>',
    ]
    if dati.get('cassa_non_oggi'):
        linee[0] += f'\n⚠️ cassa del {formatta_gg_mm(data_cassa)} non ancora chiusa'
    elif dati.get('ultima_ora'):
        linee[0] += f' (ultima vendita {dati["ultima_ora"]})'

    if dati.get('nessuna_vendita'):
        linee.append('Nessuna vendita registrata dalla chiusura precedente.')
        return '\n'.join(linee)

    for chiave, _codice, emoji, label in SETTORI:
        info = (dati.get('settori') or {}).get(chiave) or {}
        linee.append(f'{emoji} {label}: <b>{formatta_euro(info.get("importo"))}</b>')
    linee.append(f'Totale settori: <b>{formatta_euro(dati.get("totale"))}</b>')
    return '\n'.join(linee)


def messaggio_indisponibile(motivo: str) -> list[str]:
    return [f'⚠️ <b>Incassi non disponibili</b>\n{motivo}']


def leggi_parziali(company, timeout: float = LETTURA_TIMEOUT, user=None) -> dict:
    """Accoda lettura parziali_cassa, attende, restituisce dict normalizzato."""
    if not agent_is_online(company):
        raise ParzialiError('PC negozio offline', status=409)
    row, _created = accoda_parziali(company, user=user)
    row = attendi_lettura(row, timeout=timeout)
    if row is None or not isinstance(getattr(row, 'payload', None), dict):
        raise ParzialiError('Lettura non riuscita', status=503)
    return normalizza_payload(row.payload)
