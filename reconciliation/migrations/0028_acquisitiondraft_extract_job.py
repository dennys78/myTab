from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0027_remove_versamento_duplicate_movimenti'),
    ]

    operations = [
        migrations.AddField(
            model_name='acquisitiondraft',
            name='extract_job_status',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', 'Non avviata'),
                    ('queued', 'In coda'),
                    ('processing', 'In elaborazione'),
                    ('ready', 'Pronta'),
                    ('error', 'Errore'),
                ],
                default='',
                max_length=20,
                verbose_name='Stato job estrazione IA',
            ),
        ),
        migrations.AddField(
            model_name='acquisitiondraft',
            name='extract_error',
            field=models.TextField(blank=True, default='', verbose_name='Errore estrazione IA'),
        ),
    ]
