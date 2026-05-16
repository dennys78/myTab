from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0004_appsetting'),
    ]

    operations = [
        migrations.AddField(
            model_name='cashclosure',
            name='totale_cassetto',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Totale Cassetto'),
        ),
        migrations.AddField(
            model_name='cashclosure',
            name='differenza',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Differenza'),
        ),
    ]
