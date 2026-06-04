"""Registrazione versamenti in banca (uscita contanti da cassa verso banca)."""
from decimal import Decimal

from django.db import transaction

from .models import Versamento
from .views import _money


def _get_saldo_cassa(company):
    from .views import _get_saldo_cassa as _saldo
    return _saldo(company)


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
    """
    Registra un solo versamento: uscita da cassa verso banca.
    Il saldo contanti si aggiorna tramite la tabella Versamenti (non Movimenti cassa).
    """
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
        saldo_dopo = float(_get_saldo_cassa(company))
    return versamento, float(saldo_prec), saldo_dopo
