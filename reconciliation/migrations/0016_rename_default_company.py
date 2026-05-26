from django.db import migrations


def rename_default_company(apps, schema_editor):
    Company = apps.get_model('reconciliation', 'Company')
    updated = Company.objects.filter(denominazione='Azienda predefinita').update(
        denominazione='Tabaccheria del corso',
    )
    if not updated:
        first = Company.objects.order_by('id').first()
        if first and first.denominazione != 'Tabaccheria del corso':
            first.denominazione = 'Tabaccheria del corso'
            first.save(update_fields=['denominazione'])


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0015_company_multi_tenant'),
    ]

    operations = [
        migrations.RunPython(rename_default_company, migrations.RunPython.noop),
    ]
