from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0019_acquisitiondraft_pag_pos_reale'),
    ]

    operations = [
        migrations.AddField(
            model_name='acquisitiondraft',
            name='extracted_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Estrazione IA il'),
        ),
        migrations.AddField(
            model_name='acquisitiondraft',
            name='extracted_payload',
            field=models.JSONField(blank=True, null=True, verbose_name='Risultato estrazione IA'),
        ),
        migrations.AddField(
            model_name='acquisitiondraft',
            name='extracted_provider',
            field=models.CharField(blank=True, default='', max_length=20, verbose_name='Provider IA estrazione'),
        ),
    ]
