from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('reconciliation', '0029_tabauno_request'),
    ]

    operations = [
        migrations.AddField(
            model_name='tabaunorequest',
            name='tipo',
            field=models.CharField(
                choices=[('chiusura', 'Chiusura'), ('preordine_gratta', 'Preordine gratta')],
                default='chiusura',
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='tabaunorequest',
            name='parametri',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.CreateModel(
            name='GrattaPreordine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creato_il', models.DateTimeField(auto_now_add=True)),
                ('data_consegna', models.DateField()),
                ('giorni_copertura', models.PositiveSmallIntegerField(default=7)),
                ('stato', models.CharField(choices=[('bozza', 'Bozza'), ('inviato_n8n', 'Inviato al bot'), ('carrello_pronto', 'Carrello pronto'), ('confermato', 'Confermato'), ('inviato_portale', 'Inviato al portale'), ('annullato', 'Annullato'), ('errore', 'Errore')], default='bozza', max_length=32)),
                ('totale', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('messaggio_stato', models.TextField(blank=True, default='')),
                ('payload_inviato', models.JSONField(blank=True, null=True)),
                ('callback_token_hash', models.CharField(blank=True, default='', max_length=64)),
                ('aggiornato_il', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gratta_preordini', to='reconciliation.company')),
                ('creato_da', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gratta_preordini', to=settings.AUTH_USER_MODEL)),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='preordini_gratta', to='reconciliation.tabaunorequest')),
            ],
            options={
                'verbose_name': 'Preordine gratta',
                'verbose_name_plural': 'Preordini gratta',
                'ordering': ['-creato_il', '-id'],
            },
        ),
        migrations.CreateModel(
            name='GrattaPreordineRiga',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('id_articolo', models.CharField(max_length=80)),
                ('codice', models.CharField(max_length=32)),
                ('descrizione', models.CharField(blank=True, default='', max_length=200)),
                ('prezzo', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('biglietti_pacco', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('valore_pacco', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('giacenza', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('media', models.DecimalField(decimal_places=4, default=0, max_digits=12)),
                ('giorni_esauriti', models.PositiveSmallIntegerField(default=0)),
                ('settimane', models.JSONField(blank=True, default=list)),
                ('pacchi_proposti', models.PositiveIntegerField(default=0)),
                ('pacchi', models.PositiveIntegerField(default=0)),
                ('corretto_a_mano', models.BooleanField(default=False)),
                ('importo', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('escluso', models.BooleanField(default=False)),
                ('preordine', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='righe', to='reconciliation.grattapreordine')),
            ],
            options={
                'verbose_name': 'Riga preordine gratta',
                'verbose_name_plural': 'Righe preordine gratta',
                'ordering': ['codice', 'id'],
            },
        ),
    ]
