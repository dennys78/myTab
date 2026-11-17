from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('reconciliation', '0030_gratta_preordine'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tabaunorequest',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('chiusura', 'Chiusura'),
                    ('preordine_gratta', 'Preordine gratta'),
                    ('preordine_tabacchi', 'Preordine tabacchi'),
                ],
                default='chiusura',
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name='TabacchiPreordine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creato_il', models.DateTimeField(auto_now_add=True)),
                ('data_consegna', models.DateField()),
                ('giorni_copertura', models.PositiveSmallIntegerField(default=7)),
                ('stato', models.CharField(
                    choices=[('bozza', 'Bozza'), ('esportato', 'Esportato'), ('annullato', 'Annullato')],
                    default='bozza',
                    max_length=32,
                )),
                ('totale', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('kg', models.DecimalField(decimal_places=3, default=0, max_digits=12)),
                ('aggiornato_il', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='tabacchi_preordini',
                    to='reconciliation.company',
                )),
                ('creato_da', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='tabacchi_preordini',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('request', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='preordini_tabacchi',
                    to='reconciliation.tabaunorequest',
                )),
            ],
            options={
                'verbose_name': 'Preordine tabacchi',
                'verbose_name_plural': 'Preordini tabacchi',
                'ordering': ['-creato_il', '-id'],
            },
        ),
        migrations.CreateModel(
            name='TabacchiPreordineRiga',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('aams', models.CharField(max_length=32)),
                ('descrizione', models.CharField(blank=True, default='', max_length=200)),
                ('famiglia', models.CharField(blank=True, default='', max_length=64)),
                ('prezzo', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('pacchetti_per_unita', models.PositiveIntegerField(default=0)),
                ('kg_per_unita', models.DecimalField(decimal_places=3, default=0, max_digits=10)),
                ('giacenza', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('media', models.DecimalField(decimal_places=4, default=0, max_digits=12)),
                ('data_fine', models.DateField(blank=True, null=True)),
                ('unita_proposte', models.PositiveIntegerField(default=0)),
                ('unita', models.PositiveIntegerField(default=0)),
                ('corretto_a_mano', models.BooleanField(default=False)),
                ('importo', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('preordine', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='righe',
                    to='reconciliation.tabacchipreordine',
                )),
            ],
            options={
                'verbose_name': 'Riga preordine tabacchi',
                'verbose_name_plural': 'Righe preordine tabacchi',
                'ordering': ['aams', 'id'],
            },
        ),
    ]
