"""Applica import da report esterni (Lottomatica, Sisal, Gratta e Vinci) sulle chiusure per data."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction

from .models import CashClosure, CashClosureItem, Company, Department

# Reparti aggiornati dai report esterni (Contabile, Premi pagati, Movimento Sisal)
REPORT_DEPARTMENTS = {
    'lottomatica': 'LOTTOMATICA',
    'gratta': 'GRATTA E VINCI',
    'sisal': 'SISAL',
    'mooney': 'MOONEY',
}


def parse_amount(value, default: Decimal | None = None) -> Decimal:
    """Accetta 378.00 e 378,00 (formato italiano)."""
    if default is None:
        default = Decimal('0.00')
    if value in (None, ''):
        return default
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value).replace(',', '.')).quantize(Decimal('0.01'))
        except (InvalidOperation, ValueError):
            return default
    s = str(value).strip().replace(' ', '').replace(',', '.')
    if not s:
        return default
    try:
        return Decimal(s).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        return default


def _dept_name(key: str) -> str:
    key = (key or '').strip().lower()
    if key not in REPORT_DEPARTMENTS:
        raise ValueError(f'Reparto non supportato: {key}. Usa: {", ".join(REPORT_DEPARTMENTS)}')
    return REPORT_DEPARTMENTS[key]


def get_or_create_closure(company: Company, closure_date: date, operator: str = 'Import Report') -> CashClosure:
    closure = CashClosure.objects.filter(company=company, date=closure_date).first()
    if closure:
        return closure
    return CashClosure.objects.create(
        company=company,
        date=closure_date,
        operator=operator,
        submitted_by='report-overlay',
    )


def _recalc_closure_totals(closure: CashClosure) -> None:
    items = closure.items.all()
    totale_entrate = sum((i.incomes for i in items), Decimal('0'))
    totale_uscite = sum((i.expenses for i in items), Decimal('0'))
    closure.totale_generale = totale_entrate - totale_uscite
  # totale_cassetto non ricalcolato qui (resta da saldiFinali / import base)
    closure.save(update_fields=['totale_generale'])


def apply_department_overlay(
    closure: CashClosure,
    department: str,
    entrate: Decimal,
    uscite: Decimal,
) -> CashClosureItem:
    dept = department.strip().upper()
    balance = entrate - uscite

    known = list(Department.objects.filter(company=closure.company).values_list('name', flat=True))
    if dept not in known:
        Department.objects.get_or_create(company=closure.company, name=dept)

    CashClosureItem.objects.filter(closure=closure, department_name=dept).delete()
    return CashClosureItem.objects.create(
        closure=closure,
        department_name=dept,
        incomes=entrate,
        expenses=uscite,
        balance=balance,
    )


def apply_overlays_for_date(
    company: Company,
    closure_date: date,
    overlays: dict[str, dict[str, Decimal]],
    operator: str = 'Import Report',
) -> CashClosure:
    """
    overlays esempio:
    {
      'lottomatica': {'entrate': Decimal('378'), 'uscite': Decimal('190.04')},
      'gratta': {'uscite': Decimal('211')},  # solo uscite, sovrascrive reparto
      'sisal': {'entrate': Decimal('66'), 'uscite': Decimal('43.12')},
    }
    """
    with transaction.atomic():
        closure = get_or_create_closure(company, closure_date, operator=operator)
        for key, amounts in overlays.items():
            dept = _dept_name(key)
            entrate = parse_amount(amounts.get('entrate', 0))
            uscite = parse_amount(amounts.get('uscite', 0))
            if entrate == 0 and uscite == 0:
                continue
            apply_department_overlay(closure, dept, entrate, uscite)
        _recalc_closure_totals(closure)
    return closure
