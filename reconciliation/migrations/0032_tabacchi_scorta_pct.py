from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0031_tabacchi_preordine'),
    ]

    operations = [
        migrations.AddField(
            model_name='tabacchipreordine',
            name='scorta_pct',
            field=models.PositiveSmallIntegerField(default=100),
        ),
    ]
