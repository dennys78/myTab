from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0012_versamento_ricorda_promemoria'),
    ]

    operations = [
        migrations.CreateModel(
            name='MovimentoCassa',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='Data Movimento')),
                ('operator', models.CharField(max_length=100, verbose_name='Operatore')),
                ('tipo', models.CharField(choices=[('ENTRATA', 'Entrata'), ('USCITA', 'Uscita')], max_length=10, verbose_name='Tipo')),
                ('importo', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Importo')),
                ('saldo_precedente', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Saldo Precedente')),
                ('note', models.TextField(blank=True, verbose_name='Note')),
                ('ricorda_promemoria', models.BooleanField(default=False, verbose_name='Ricorda come promemoria')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Movimento Cassa',
                'verbose_name_plural': 'Movimenti Cassa',
                'ordering': ['-date', '-created_at'],
            },
        ),
    ]
