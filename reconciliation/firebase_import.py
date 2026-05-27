"""Mappatura documenti Firestore collection `registrazioni` → modelli myTaba."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.utils.dateparse import parse_date

from .models import CashClosure, CashClosureItem, Company, Department

FIREBASE_SOURCE_PREFIX = 'firebase:'

# Chiavi note nell'app Firebase "Gestione incassi tabaccheria"
DEPT_FIELD_LABELS = {
    'datiGV': 'GRATTA E VINCI',
    'datiLottomatica': 'LOTTOMATICA',
    'datiSisal': 'SISAL',
    'datiTabacchi': 'TABACCHI',
}


def _money(value, default=Decimal('0.00')):
    if value in (None, ''):
        return default
    try:
        return Decimal(str(value)).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError, TypeError):
        return default


def _parse_firestore_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, 'timestamp'):
        try:
            return datetime.fromtimestamp(value.timestamp()).date()
        except (TypeError, ValueError, OSError):
            pass
    if isinstance(value, str):
        parsed = parse_date(value[:10])
        if parsed:
            return parsed
    return None


def _dept_label_from_field(field_name: str) -> str:
    if field_name in DEPT_FIELD_LABELS:
        return DEPT_FIELD_LABELS[field_name]
    if field_name.startswith('dati') and len(field_name) > 4:
        return field_name[4:].upper()
    return field_name.upper()


def _extract_department_items(doc_data: dict) -> list[dict]:
    items = []
    for key, raw in doc_data.items():
        if not key.startswith('dati') or not isinstance(raw, dict):
            continue
        entrate = _money(raw.get('entrate'))
        uscite = _money(raw.get('uscite'))
        if entrate == 0 and uscite == 0:
            continue
        items.append({
            'descrizione': _dept_label_from_field(key),
            'entrate': entrate,
            'uscite': uscite,
            'balance': entrate - uscite,
        })
    return items


def map_registrazione_document(doc_id: str, doc_data: dict) -> dict | None:
    """Converte un documento Firestore in payload per CashClosure + items."""
    closure_date = _parse_firestore_date(doc_data.get('dataIncasso'))
    if not closure_date:
        return None

    saldi = doc_data.get('saldiFinali') or {}
    if not isinstance(saldi, dict):
        saldi = {}

    items = _extract_department_items(doc_data)
    totale_reparti = sum((i['balance'] for i in items), Decimal('0.00'))

    contanti = _money(saldi.get('contanti'))
    pag_pos = _money(saldi.get('pagPos'))
    cassa_auto = _money(saldi.get('cassaAuto'))
    distrib = _money(saldi.get('distrib'))
    reso_cont = _money(saldi.get('resoCont', saldi.get('reso_cont')))
    reso_auto = _money(saldi.get('resoAuto', saldi.get('reso_auto')))

    totale_generale = _money(doc_data.get('totaleGenerale', doc_data.get('totale_generale')), totale_reparti)
    if totale_generale == 0 and totale_reparti != 0:
        totale_generale = totale_reparti

    totale_cassetto = _money(
        doc_data.get('totaleCassetto', doc_data.get('totale_cassetto')),
        contanti,
    )

    note = (doc_data.get('note') or '').strip()

    return {
        'firebase_id': doc_id,
        'date': closure_date,
        'operator': 'Import Firebase',
        'submitted_by': f'{FIREBASE_SOURCE_PREFIX}{doc_id}',
        'note': note,
        'summary': {
            'contanti': contanti,
            'pag_pos': pag_pos,
            'cassa_auto': cassa_auto,
            'reso_cont': reso_cont,
            'reso_auto': reso_auto,
            'distrib': distrib,
            'totale_generale': totale_generale,
            'totale_cassetto': totale_cassetto,
            'differenza': _money(doc_data.get('differenza')),
        },
        'items': items,
    }


def import_mapped_closure(company: Company, mapped: dict, *, dry_run: bool = False) -> str:
    """
    Importa una chiusura. Ritorna: created | skipped | dry_run
    """
    firebase_key = mapped['submitted_by']
    if CashClosure.objects.filter(company=company, submitted_by=firebase_key).exists():
        return 'skipped'

    if dry_run:
        return 'dry_run'

    known_depts = list(Department.objects.filter(company=company).values_list('name', flat=True))
    summary = mapped['summary']

    closure = CashClosure.objects.create(
        company=company,
        date=mapped['date'],
        operator=mapped['operator'],
        submitted_by=firebase_key,
        contanti=summary['contanti'],
        pag_pos=summary['pag_pos'],
        cassa_auto=summary['cassa_auto'],
        reso_cont=summary['reso_cont'],
        reso_auto=summary['reso_auto'],
        distrib=summary['distrib'],
        totale_generale=summary['totale_generale'],
        totale_cassetto=summary['totale_cassetto'],
        differenza=summary['differenza'],
    )

    for item in mapped['items']:
        dept_name = item['descrizione'].strip().upper()
        if dept_name not in known_depts:
            Department.objects.get_or_create(company=company, name=dept_name)
            known_depts.append(dept_name)
        CashClosureItem.objects.create(
            closure=closure,
            department_name=dept_name,
            incomes=item['entrate'],
            expenses=abs(item['uscite']),
            balance=item['balance'],
        )

    return 'created'
