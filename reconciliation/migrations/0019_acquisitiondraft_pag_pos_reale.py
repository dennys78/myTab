from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0018_userprofile_ai_acquisition_provider'),
    ]

    operations = [
        migrations.AddField(
            model_name='acquisitiondraft',
            name='pag_pos_reale',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=10,
                verbose_name='Totale POS reale (Telegram)',
            ),
        ),
    ]
