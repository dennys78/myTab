"""Versamenti in banca: record Versamento + movimento cassa in uscita."""
from decimal import Decimal

from django.db import transaction

from .models import MovimentoCassa, Versamento
from .views import _money


def _get_saldo_cassa(company):
    from .views import _get_saldo_cassa as _saldo
    return _saldo(company)

VERSAMENTO_MOVIMENTO_TAG_PREFIX = '[[versamento:'


def versamento_movimento_tag(versamento_id):
    return f'{VERSAMENTO_MOVIMENTO_TAG_PREFIX}{versamento_id}]]'


def versamento_movimento_note(versamento):
    user_note = (versamento.note or '').strip()
    base = 'Versamento in banca'
    tag = versamento_movimento_tag(versamento.id)
    if user_note:
        return f'{tag} {base} — {user_note}'
    return f'{tag} {base}'


def _movimento_for_versamento(versamento):
    tag = versamento_movimento_tag(versamento.id)
    return MovimentoCassa.objects.filter(
        company_id=versamento.company_id,
        note__startswith=tag,
    ).first()


def sync_movimento_uscita_for_versamento(versamento):
    """Crea o aggiorna il movimento di uscita collegato al versamento."""
    company = versamento.company
    operator = (versamento.operator or '')[:100]
    importo = _money(versamento.importo_versato)
    note = versamento_movimento_note(versamento)
    existing = _movimento_for_versamento(versamento)

    if existing:
        existing.date = versamento.date
        existing.operator = operator
        existing.tipo = MovimentoCassa.TIPO_USCITA
        existing.importo = importo
        existing.note = note
        existing.ricorda_promemoria = bool(versamento.ricorda_promemoria)
        existing.save(
            update_fields=['date', 'operator', 'tipo', 'importo', 'note', 'ricorda_promemoria'],
        )
        return existing

    saldo_prec = _get_saldo_cassa(company)
    return MovimentoCassa.objects.create(
        company=company,
        date=versamento.date,
        operator=operator,
        tipo=MovimentoCassa.TIPO_USCITA,
        importo=importo,
        saldo_precedente=saldo_prec,
        note=note,
        ricorda_promemoria=bool(versamento.ricorda_promemoria),
    )


def delete_movimento_for_versamento(versamento):
    tag = versamento_movimento_tag(versamento.id)
    MovimentoCassa.objects.filter(company_id=versamento.company_id, note__startswith=tag).delete()


def register_versamento(
    company,
    *,
    operator,
    importo_versato,
    versamento_date,
    note='',
    accantonamento=Decimal('0.00'),
    ricorda_promemoria=False,
):
    """Registra versamento e movimento di uscita; ritorna (versamento, saldo_prima, saldo_dopo)."""
    if not company:
        raise RuntimeError('Nessuna azienda configurata.')

    importo_dec = _money(importo_versato)
    if importo_dec <= 0:
        raise ValueError('Importo deve essere maggiore di zero')

    acc = _money(accantonamento)
    if acc < 0 or acc > importo_dec:
        raise ValueError('Accantonamento non valido')

    operator_label = (operator or '')[:100]
    with transaction.atomic():
        saldo_prec = _get_saldo_cassa(company)
        versamento = Versamento.objects.create(
            company=company,
            date=versamento_date,
            operator=operator_label,
            importo_versato=importo_dec,
            accantonamento=acc,
            saldo_precedente=saldo_prec,
            note=(note or '').strip(),
            ricorda_promemoria=bool(ricorda_promemoria),
        )
        sync_movimento_uscita_for_versamento(versamento)
        saldo_dopo = float(_get_saldo_cassa(company))
    return versamento, float(saldo_prec), saldo_dopo
