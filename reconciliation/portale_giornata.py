"""Prospetti giornalieri portale Lotterie: lettura, salvataggio, riconciliazione, testo Telegram."""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from .incassi_parziali import formatta_euro, formatta_ora
from .models import PortaleGiornata, TabaUnoRequest
from .portale_service import (
    PortaleServiceError,
    get_contabile_lotto,
    get_premi_pagati,
)

logger = logging.getLogger(__name__)

CENT = Decimal('0.01')
GIOCHI_LABEL = (
    ('lotto', 'Lotto'),
    ('diecielotto', '10eLotto'),
    ('millionday', 'MillionDAY'),
    ('fai3fai4', 'Fai3 Fai4'),
)


def _money(value) -> Decimal:
    if value is None or value == '':
        return Decimal('0').quantize(CENT)
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def _float(value) -> float:
    return float(_money(value))


def _parse_day(value) -> date | None:
    text = str(value or '').strip()[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _voce_match(voce: dict, *, codici: set[str], substr: tuple[str, ...]) -> bool:
    code = str(voce.get('reparto') or '').strip()
    desc = str(voce.get('descrizione') or '').upper()
    if code in codici:
        return True
    return any(s in desc for s in substr)


def importo_tabauno_lotto(voci) -> float | None:
    """Entrate settore 301 INCASSO LOTTO/10&LOTTO (o fallback LOTTOMATICA.entrate)."""
    for voce in voci or []:
        if _voce_match(voce, codici={'301'}, substr=('INCASSO LOTTO',)):
            return abs(_float(voce.get('entrate')))
    for voce in voci or []:
        if str(voce.get('descrizione') or '').upper() == 'LOTTOMATICA':
            return abs(_float(voce.get('entrate')))
    return None


def importo_tabauno_gratta_vincite(voci) -> float | None:
    """|Settore 300 VINCITE GRATTA E VINCI| (con regola B finisce in uscite GRATTA)."""
    for voce in voci or []:
        if _voce_match(voce, codici={'300'}, substr=('VINCITE GRATTA',)):
            entrate = _float(voce.get('entrate'))
            uscite = _float(voce.get('uscite'))
            return abs(uscite or entrate)
    for voce in voci or []:
        if str(voce.get('descrizione') or '').upper() in {'GRATTA E VINCI', 'GRATTA'}:
            uscite = _float(voce.get('uscite'))
            if uscite:
                return abs(uscite)
    return None


def tabauno_voci_per_data(company, day: date) -> list | None:
    row = (
        TabaUnoRequest.objects.filter(
            company=company,
            date=day,
            tipo=TabaUnoRequest.TIPO_CHIUSURA,
            status=TabaUnoRequest.DONE,
        )
        .order_by('-completed_at', '-id')
        .first()
    )
    if not row or not isinstance(row.payload, dict):
        return None
    voci = row.payload.get('voci')
    return voci if isinstance(voci, list) else None


def riconcilia(contabile: dict | None, premi: dict | None, voci_tabauno) -> dict:
    portale_lotto = _float((contabile or {}).get('entrate')) if contabile else None
    portale_premi = None
    if premi and isinstance(premi.get('totale'), dict):
        portale_premi = _float(premi['totale'].get('importo'))
    elif premi is not None:
        portale_premi = 0.0

    taba_lotto = importo_tabauno_lotto(voci_tabauno) if voci_tabauno is not None else None
    taba_gratta = importo_tabauno_gratta_vincite(voci_tabauno) if voci_tabauno is not None else None

    def riga(etichetta, portale, tabauno):
        if portale is None or tabauno is None:
            return {
                'etichetta': etichetta,
                'portale': portale,
                'tabauno': tabauno,
                'differenza': None,
                'stato': 'mancante',
            }
        diff = float(_money(portale) - _money(tabauno))
        return {
            'etichetta': etichetta,
            'portale': float(_money(portale)),
            'tabauno': float(_money(tabauno)),
            'differenza': diff,
            'stato': 'ok' if abs(diff) < 0.005 else 'differenza',
        }

    return {
        'lotto_entrate': riga('Lotto entrate (301)', portale_lotto, taba_lotto),
        'gratta_premi': riga('Premi Gratta pagati (300)', portale_premi, taba_gratta),
        'tabauno_disponibile': voci_tabauno is not None,
    }


def testo_telegram(giornata: PortaleGiornata | None, *, motivo: str | None = None) -> str:
    if motivo:
        return f'🎱 Lotto/premi non disponibili: {motivo}'
    if not giornata:
        return '🎱 Lotto/premi non disponibili: nessun dato'
    if giornata.errore and not giornata.contabile_lotto and not giornata.premi_lotterie:
        return f'🎱 Lotto/premi non disponibili: {giornata.errore}'

    linee = []
    contabile = giornata.contabile_lotto if isinstance(giornata.contabile_lotto, dict) else None
    premi = giornata.premi_lotterie if isinstance(giornata.premi_lotterie, dict) else None

    if contabile:
        ora = formatta_ora(contabile.get('richiesto_alle')) or '—'
        linee.append(f'🎱 <b>Lotto</b> (portale, {ora})')
        linee.append(
            f'Entrate <b>{formatta_euro(contabile.get("entrate"))}</b> · '
            f'Vincite <b>{formatta_euro(contabile.get("uscite"))}</b> · '
            f'Saldo <b>{formatta_euro(contabile.get("saldo"))}</b>'
        )
        parti = []
        giochi = contabile.get('giochi') or {}
        for chiave, label in GIOCHI_LABEL:
            info = giochi.get(chiave) or {}
            parti.append(f'{label} {formatta_euro(info.get("giocate")).replace(" €", "")}')
        linee.append(' · '.join(parti))
    else:
        linee.append('🎱 <b>Lotto</b>: non disponibile')

    if premi:
        totale = premi.get('totale') or {}
        qta = int(totale.get('qta') or 0)
        linee.append(
            f'🎟️ <b>Premi Gratta pagati</b>: <b>{formatta_euro(totale.get("importo"))}</b> ({qta})'
        )
    else:
        linee.append('🎟️ <b>Premi Gratta pagati</b>: non disponibili')

    if giornata.errore:
        linee.append(f'⚠️ {giornata.errore}')
    return '\n'.join(linee)


def serializza_giornata(giornata: PortaleGiornata, voci_tabauno=None) -> dict:
    if voci_tabauno is None:
        voci_tabauno = tabauno_voci_per_data(giornata.company, giornata.data)
    ric = riconcilia(giornata.contabile_lotto, giornata.premi_lotterie, voci_tabauno)
    letto = giornata.letto_alle
    if letto and timezone.is_aware(letto):
        letto_iso = timezone.localtime(letto).isoformat(timespec='seconds')
    elif letto:
        letto_iso = letto.isoformat(timespec='seconds')
    else:
        letto_iso = ''
    return {
        'data': giornata.data.isoformat(),
        'contabile_lotto': giornata.contabile_lotto,
        'premi_lotterie': giornata.premi_lotterie,
        'letto_alle': letto_iso,
        'errore': giornata.errore or '',
        'riconciliazione': ric,
        'lotto': _vista_lotto(giornata.contabile_lotto),
        'premi_lotterie_vista': _vista_premi(giornata.premi_lotterie),
    }


def _vista_lotto(contabile):
    if not isinstance(contabile, dict):
        return None
    return {
        'entrate': contabile.get('entrate'),
        'uscite': contabile.get('uscite'),
        'aggio': contabile.get('aggio'),
        'saldo': contabile.get('saldo'),
        'giochi': contabile.get('giochi') or {},
        'richiesto_alle': contabile.get('richiesto_alle') or '',
    }


def _vista_premi(premi):
    if not isinstance(premi, dict):
        return None
    totale = premi.get('totale') or {'qta': 0, 'importo': 0}
    return {
        'totale': totale,
        'giochi': premi.get('giochi') or [],
        'richiesto_alle': premi.get('richiesto_alle') or '',
    }


def payload_n8n(giornata: PortaleGiornata) -> dict:
    dati = serializza_giornata(giornata)
    lotto = dati.get('lotto') or {}
    premi = dati.get('premi_lotterie_vista') or {
        'totale': {'qta': 0, 'importo': 0},
        'giochi': [],
        'richiesto_alle': '',
    }
    out = {
        'data': dati['data'],
        'lotto': lotto,
        'premi_lotterie': premi,
        'riconciliazione': dati['riconciliazione'],
        'testo': testo_telegram(giornata),
    }
    if dati.get('errore'):
        out['errore'] = dati['errore']
    return out


def leggi_portale(company, day: date, *, tabauno_payload: dict | None = None) -> PortaleGiornata:
    """Chiama i due endpoint, salva/aggiorna PortaleGiornata. Errori non sollevati verso la chiusura."""
    day = day if isinstance(day, date) else _parse_day(day)
    if not day:
        raise ValueError('Data non valida')

    data_iso = day.isoformat()
    contabile = None
    premi = None
    errori = []

    try:
        contabile = get_contabile_lotto(data_iso)
    except PortaleServiceError as exc:
        errori.append(f'Contabile Lotto: {exc.messaggio}')
        logger.info('portale contabile fallito company=%s data=%s: %s', company.id, data_iso, exc.messaggio)

    try:
        premi = get_premi_pagati(data_iso)
    except PortaleServiceError as exc:
        errori.append(f'Premi Lotterie: {exc.messaggio}')
        logger.info('portale premi fallito company=%s data=%s: %s', company.id, data_iso, exc.messaggio)

    row, _created = PortaleGiornata.objects.get_or_create(company=company, data=day)
    if contabile is not None:
        row.contabile_lotto = contabile
    if premi is not None:
        row.premi_lotterie = premi
    row.letto_alle = timezone.now()
    row.errore = '; '.join(errori)
    row.save()
    return row


def prova_leggi_portale_su_chiusura(company, day: date) -> None:
    """Hook chiusura TabaUno: un errore non deve bloccare."""
    try:
        leggi_portale(company, day)
    except Exception:
        logger.exception('lettura portale su chiusura fallita company=%s data=%s', company.id, day)
