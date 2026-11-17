from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0032_tabacchi_scorta_pct'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tabacchipreordine',
            name='scorta_pct',
            field=models.PositiveSmallIntegerField(default=200),
        ),
    ]
