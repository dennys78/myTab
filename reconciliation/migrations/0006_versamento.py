from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0005_cashclosure_cassetto_differenza'),
    ]

    operations = [
        migrations.CreateModel(
            name='Versamento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='Data Versamento')),
                ('operator', models.CharField(max_length=100, verbose_name='Operatore')),
                ('importo_versato', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Importo Versato')),
                ('saldo_precedente', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Saldo Precedente')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Versamento',
                'verbose_name_plural': 'Versamenti',
                'ordering': ['-date', '-created_at'],
            },
        ),
    ]
