from decimal import Decimal

from django.db import migrations


def _tag(versamento_id):
    return f'[[versamento:{versamento_id}]]'


def backfill_versamento_movimenti_uscita(apps, schema_editor):
    Versamento = apps.get_model('reconciliation', 'Versamento')
    MovimentoCassa = apps.get_model('reconciliation', 'MovimentoCassa')

    for v in Versamento.objects.all().iterator():
        tag = _tag(v.id)
        if MovimentoCassa.objects.filter(company_id=v.company_id, note__startswith=tag).exists():
            continue
        user_note = (v.note or '').strip()
        base = 'Versamento in banca'
        note = f'{tag} {base} — {user_note}' if user_note else f'{tag} {base}'
        MovimentoCassa.objects.create(
            company_id=v.company_id,
            date=v.date,
            operator=(v.operator or '')[:100],
            tipo='USCITA',
            importo=v.importo_versato,
            saldo_precedente=v.saldo_precedente or Decimal('0'),
            note=note,
            ricorda_promemoria=bool(v.ricorda_promemoria),
        )


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0025_userprofile_notifications'),
    ]

    operations = [
        migrations.RunPython(backfill_versamento_movimenti_uscita, migrations.RunPython.noop),
    ]
