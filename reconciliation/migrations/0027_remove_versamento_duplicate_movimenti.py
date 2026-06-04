from django.db import migrations


def remove_versamento_linked_movimenti(apps, schema_editor):
    MovimentoCassa = apps.get_model('reconciliation', 'MovimentoCassa')
    MovimentoCassa.objects.filter(note__startswith='[[versamento:').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0026_versamento_movimento_uscita'),
    ]

    operations = [
        migrations.RunPython(remove_versamento_linked_movimenti, migrations.RunPython.noop),
    ]
