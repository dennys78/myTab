"""Comandi Telegram per fondo cassa: aggiungi / preleva."""

from __future__ import annotations

import re
from decimal import Decimal

from django.db import transaction

from .models import FondoCassaMovimento, MovimentoCassa
from .views import _get_fondo_cassa, _get_saldo_cassa, _money

AGGIUNGI_FONDO_RE = re.compile(
    r'(?i)^aggiungi\s+a\s+fondo\s*\(?\s*([\d.,\s€]+)\s*\)?\s*$',
)
PRELEVA_FONDO_RE = re.compile(
    r'(?i)^preleva\s+da\s+fondo\s*\(?\s*([\d.,\s€]+)\s*\)?\s*$',
)

FONDO_SALDO_QUERY_RE = re.compile(r'(?i)^(?:saldo\s+)?fondo(?:\s+cassa)?\s*$')

FONDO_AGGIUNGI_CASSA_NOTE = 'Trasferimento a fondo cassa'
FONDO_ENTRATA_DESC = 'Trasferimento da contanti'
FONDO_USCITA_DESC = 'Prelievo da fondo cassa'

OPERATOR_HELP_TEXT = (
    'Comandi operatore myTab (Telegram)\n\n'
    '── Chiusura cassa ──\n'
    '1) Invia una o più foto del foglio incasso\n'
    '2) Scrivi il totale POS reale (es. 1240,00)\n'
    '3) Scrivi l\'importo scassettato\n'
    '→ La bozza compare in myTab per la registrazione.\n\n'
    '── Versamento in banca ──\n'
    'Versati importo\n'
    'Esempio: Versati 2343,20\n'
    'Poi conferma la data odierna (sì) oppure gg/mm.\n\n'
    '── Entrata in cassa ──\n'
    'Descrizione importo\n'
    'Esempio: Distributore 505\n'
    'Registra un\'entrata con data del messaggio.\n\n'
    '── Fondo cassa ──\n'
    'aggiungi a fondo importo\n'
    'Esempio: aggiungi a fondo 200\n'
    'Preleva dai contanti in cassa e versa sul fondo.\n\n'
    'preleva da fondo importo\n'
    'Esempio: preleva da fondo 50\n'
    'Decrementa solo il fondo cassa.\n\n'
    '── Saldi ──\n'
    '/saldo oppure «saldo cassa» — contanti in cassa\n'
    '«saldo fondo» — totale fondo cassa\n\n'
    '── Altro ──\n'
    '/aiuto — questo messaggio\n'
    '/annulla — annulla operazione in corso'
)


def _parse_amount_token(text):
    cleaned = (text or '').strip().replace('€', '').replace(' ', '')
    if not re.fullmatch(r'\d{1,9}([.,]\d{1,2})?', cleaned):
        raise ValueError('Importo non valido')
    if ',' in cleaned:
        return float(cleaned.replace('.', '').replace(',', '.'))
    return float(cleaned)


def _money_text(value):
    return f'€ {float(value):.2f}'.replace('.', ',')


def parse_fondo_command(text):
    """
    Ritorna ('aggiungi'|'preleva', importo) oppure None.
    Solleva ValueError se il comando è riconosciuto ma l'importo non è valido.
    """
    raw = (text or '').strip()
    if not raw:
        return None

    for pattern, kind in ((AGGIUNGI_FONDO_RE, 'aggiungi'), (PRELEVA_FONDO_RE, 'preleva')):
        match = pattern.match(raw)
        if not match:
            continue
        try:
            importo = _parse_amount_token(match.group(1))
        except ValueError as exc:
            raise ValueError(
                'Importo non valido.\n\n'
                f'Esempio: {"aggiungi a fondo 200" if kind == "aggiungi" else "preleva da fondo 50"}'
            ) from exc
        if importo <= 0:
            raise ValueError('L\'importo deve essere maggiore di zero.')
        return kind, importo
    return None


def is_fondo_saldo_query(text):
    return bool(FONDO_SALDO_QUERY_RE.match((text or '').strip()))


def save_aggiungi_fondo_from_telegram(company, operator, importo, movimento_date, *, source='Telegram'):
    if not company:
        raise RuntimeError('Nessuna azienda configurata per il bot Telegram.')

    importo_dec = Decimal(str(importo)).quantize(Decimal('0.01'))
    if importo_dec <= 0:
        raise ValueError('Importo deve essere maggiore di zero')

    saldo_cassa = _get_saldo_cassa(company)
    if importo_dec > saldo_cassa:
        raise ValueError(
            f'Contanti in cassa insufficienti ({_money_text(saldo_cassa)} disponibili).'
        )

    operator_label = (operator or source or 'Telegram')[:100]
    with transaction.atomic():
        saldo_prec = _get_saldo_cassa(company)
        movimento = MovimentoCassa.objects.create(
            company=company,
            date=movimento_date,
            operator=operator_label,
            tipo=MovimentoCassa.TIPO_USCITA,
            importo=_money(importo_dec),
            saldo_precedente=saldo_prec,
            note=FONDO_AGGIUNGI_CASSA_NOTE,
            ricorda_promemoria=False,
        )
        fondo = FondoCassaMovimento.objects.create(
            company=company,
            date=movimento_date,
            tipo=FondoCassaMovimento.TIPO_ENTRATA,
            importo=_money(importo_dec),
            descrizione=f'{FONDO_ENTRATA_DESC} ({source})',
        )

    return {
        'movimento': movimento,
        'fondo': fondo,
        'saldo_cassa': float(_get_saldo_cassa(company)),
        'fondo_cassa': float(_get_fondo_cassa(company)),
    }


def save_preleva_fondo_from_telegram(company, operator, importo, movimento_date, *, source='Telegram'):
    if not company:
        raise RuntimeError('Nessuna azienda configurata per il bot Telegram.')

    importo_dec = Decimal(str(importo)).quantize(Decimal('0.01'))
    if importo_dec <= 0:
        raise ValueError('Importo deve essere maggiore di zero')

    fondo_attuale = _get_fondo_cassa(company)
    if importo_dec > fondo_attuale:
        raise ValueError(
            f'Fondo cassa insufficiente ({_money_text(fondo_attuale)} disponibili).'
        )

    operator_label = (operator or source or 'Telegram')[:100]
    fondo = FondoCassaMovimento.objects.create(
        company=company,
        date=movimento_date,
        tipo=FondoCassaMovimento.TIPO_USCITA,
        importo=_money(importo_dec),
        descrizione=f'{FONDO_USCITA_DESC} ({source}) — {operator_label}',
    )
    return {
        'fondo': fondo,
        'saldo_cassa': float(_get_saldo_cassa(company)),
        'fondo_cassa': float(_get_fondo_cassa(company)),
    }
