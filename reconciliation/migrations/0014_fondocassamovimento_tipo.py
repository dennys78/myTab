from decimal import Decimal

from django.db import migrations, models


def normalizza_tipo_importo(apps, schema_editor):
    FondoCassaMovimento = apps.get_model('reconciliation', 'FondoCassaMovimento')
    for m in FondoCassaMovimento.objects.all():
        imp = Decimal(str(m.importo))
        if imp < 0:
            m.tipo = 'USCITA'
            m.importo = abs(imp)
        else:
            m.tipo = 'ENTRATA'
            m.importo = abs(imp)
        m.save(update_fields=['tipo', 'importo'])


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0013_movimentocassa'),
    ]

    operations = [
        migrations.AddField(
            model_name='fondocassamovimento',
            name='tipo',
            field=models.CharField(
                choices=[('ENTRATA', 'Entrata'), ('USCITA', 'Uscita')],
                default='ENTRATA',
                max_length=10,
                verbose_name='Tipo',
            ),
        ),
        migrations.RunPython(normalizza_tipo_importo, migrations.RunPython.noop),
    ]
