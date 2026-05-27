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
    """
    Estrae reparti da strutture Firestore variabili:
    - chiavi tipo `datiGV`, `datiSisal`, ...
    - mappe top-level con campi `entrate`/`uscite`
    - liste top-level con elementi {descrizione,nome,label}+entrate/uscite
    """
    by_dept = {}

    def add_item(label: str, payload: dict):
        entrate = _money(payload.get('entrate'))
        uscite = _money(payload.get('uscite'))
        if entrate == 0 and uscite == 0:
            return
        raw_label = (
            payload.get('descrizioneReparto')
            or payload.get('descrizione')
            or payload.get('nome')
            or payload.get('label')
            or label
        )
        dept = _dept_label_from_field(str(raw_label)).strip().upper()
        if not dept:
            return
        current = by_dept.get(dept)
        if not current:
            by_dept[dept] = {
                'descrizione': dept,
                'entrate': entrate,
                'uscite': uscite,
            }
            return
        current['entrate'] += entrate
        current['uscite'] += uscite

    def walk(value, label_hint):
        if isinstance(value, dict):
            if 'entrate' in value and 'uscite' in value:
                add_item(label_hint, value)
            for child_key, child_value in value.items():
                child_label = child_key if child_key not in ('entrate', 'uscite') else label_hint
                walk(child_value, child_label)
        elif isinstance(value, list):
            for row in value:
                if isinstance(row, dict):
                    row_label = (
                        row.get('descrizioneReparto')
                        or row.get('descrizione')
                        or row.get('nome')
                        or row.get('label')
                        or label_hint
                    )
                    walk(row, str(row_label))

    for key, raw in doc_data.items():
        walk(raw, key)

    ordered = []
    for dept in sorted(by_dept.keys()):
        item = by_dept[dept]
        ordered.append({
            'descrizione': item['descrizione'],
            'entrate': item['entrate'],
            'uscite': item['uscite'],
            'balance': item['entrate'] - item['uscite'],
        })
    return ordered


def debug_department_candidates(doc_data: dict) -> list[dict]:
    """
    Restituisce i candidati reparto individuati nel documento con path e valori
    entrate/uscite per debugging struttura Firestore.
    """
    out = []

    def visit(value, path, label_hint):
        if isinstance(value, dict):
            has_amounts = 'entrate' in value or 'uscite' in value
            if has_amounts:
                label = (
                    value.get('descrizioneReparto')
                    or value.get('descrizione')
                    or value.get('nome')
                    or value.get('label')
                    or label_hint
                )
                out.append({
                    'path': path,
                    'label': str(label),
                    'entrate': value.get('entrate'),
                    'uscite': value.get('uscite'),
                    'keys': list(value.keys())[:15],
                })
            for k, child in value.items():
                child_path = f'{path}.{k}' if path else k
                visit(child, child_path, k)
        elif isinstance(value, list):
            for idx, row in enumerate(value):
                visit(row, f'{path}[{idx}]', label_hint)

    visit(doc_data, '', 'REPARTO')
    return out


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


def import_mapped_closure(
    company: Company,
    mapped: dict,
    *,
    dry_run: bool = False,
    update_existing: bool = False,
) -> str:
    """
    Importa una chiusura. Ritorna: created | skipped | dry_run
    """
    firebase_key = mapped['submitted_by']
    existing = CashClosure.objects.filter(company=company, submitted_by=firebase_key).first()
    if existing and not update_existing:
        return 'skipped'

    if dry_run:
        return 'dry_run_updated' if existing else 'dry_run'

    known_depts = list(Department.objects.filter(company=company).values_list('name', flat=True))
    summary = mapped['summary']

    if existing:
        closure = existing
        closure.date = mapped['date']
        closure.operator = mapped['operator']
        closure.contanti = summary['contanti']
        closure.pag_pos = summary['pag_pos']
        closure.cassa_auto = summary['cassa_auto']
        closure.reso_cont = summary['reso_cont']
        closure.reso_auto = summary['reso_auto']
        closure.distrib = summary['distrib']
        closure.totale_generale = summary['totale_generale']
        closure.totale_cassetto = summary['totale_cassetto']
        closure.differenza = summary['differenza']
        closure.save()
        closure.items.all().delete()
    else:
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

    return 'updated' if existing else 'created'
