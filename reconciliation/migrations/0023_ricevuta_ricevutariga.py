from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0022_cliente_valorebollato'),
    ]

    operations = [
        migrations.CreateModel(
            name='Ricevuta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='Data ricevuta')),
                ('operator', models.CharField(max_length=100, verbose_name='Operatore')),
                ('note', models.TextField(blank=True, verbose_name='Note')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='ricevute', to='reconciliation.cliente', verbose_name='Cliente')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ricevute', to='reconciliation.company', verbose_name='Azienda')),
            ],
            options={
                'verbose_name': 'Ricevuta',
                'verbose_name_plural': 'Ricevute',
                'ordering': ['-date', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='RicevutaRiga',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('valore_bollato', 'Valori bollati'), ('contributo_unificato', 'Contributo unificato')], max_length=32, verbose_name='Tipo articolo')),
                ('descrizione', models.CharField(max_length=255, verbose_name='Descrizione')),
                ('importo_unitario', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Importo unitario')),
                ('quantita', models.PositiveIntegerField(default=1, verbose_name='Quantità')),
                ('ricevuta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='righe', to='reconciliation.ricevuta', verbose_name='Ricevuta')),
                ('valore_bollato', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='righe_ricevuta', to='reconciliation.valorebollato', verbose_name='Voce catalogo')),
            ],
            options={
                'verbose_name': 'Riga ricevuta',
                'verbose_name_plural': 'Righe ricevuta',
                'ordering': ['id'],
            },
        ),
    ]
