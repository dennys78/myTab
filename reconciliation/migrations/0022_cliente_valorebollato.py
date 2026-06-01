from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0021_push_subscription_draft_viewed'),
    ]

    operations = [
        migrations.CreateModel(
            name='Cliente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ragione_sociale', models.CharField(max_length=255, verbose_name='Ragione sociale')),
                ('indirizzo', models.TextField(blank=True, verbose_name='Indirizzo')),
                ('cf_piva', models.CharField(blank=True, max_length=32, verbose_name='CF/PIVA')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='Email')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='clienti', to='reconciliation.company', verbose_name='Azienda')),
            ],
            options={
                'verbose_name': 'Cliente',
                'verbose_name_plural': 'Clienti',
                'ordering': ['ragione_sociale', 'id'],
            },
        ),
        migrations.CreateModel(
            name='ValoreBollato',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('descrizione', models.CharField(max_length=255, verbose_name='Descrizione')),
                ('importo', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Importo')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='valori_bollati', to='reconciliation.company', verbose_name='Azienda')),
            ],
            options={
                'verbose_name': 'Valore bollato',
                'verbose_name_plural': 'Valori bollati',
                'ordering': ['descrizione', 'id'],
            },
        ),
    ]
