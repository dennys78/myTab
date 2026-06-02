from django.db import migrations, models


def set_progressive_number(apps, schema_editor):
    Ricevuta = apps.get_model('reconciliation', 'Ricevuta')
    for row in Ricevuta.objects.all().order_by('company_id', 'date', 'id'):
        row.numero_progressivo = row.id
        row.save(update_fields=['numero_progressivo'])


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0023_ricevuta_ricevutariga'),
    ]

    operations = [
        migrations.AddField(
            model_name='ricevuta',
            name='numero_progressivo',
            field=models.PositiveIntegerField(default=1, verbose_name='Numero progressivo'),
        ),
        migrations.RunPython(set_progressive_number, migrations.RunPython.noop),
    ]
