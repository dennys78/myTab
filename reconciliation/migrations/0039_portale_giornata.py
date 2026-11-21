from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0038_parziali_cassa_tipo'),
    ]

    operations = [
        migrations.CreateModel(
            name='PortaleGiornata',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data', models.DateField()),
                ('contabile_lotto', models.JSONField(blank=True, null=True)),
                ('premi_lotterie', models.JSONField(blank=True, null=True)),
                ('letto_alle', models.DateTimeField(blank=True, null=True)),
                ('errore', models.TextField(blank=True, default='')),
                ('aggiornato_il', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='portale_giornate',
                    to='reconciliation.company',
                )),
            ],
            options={
                'verbose_name': 'Giornata portale Lotterie',
                'verbose_name_plural': 'Giornate portale Lotterie',
                'ordering': ['-data', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='portalegiornata',
            constraint=models.UniqueConstraint(
                fields=('company', 'data'),
                name='portale_giornata_company_data_uniq',
            ),
        ),
    ]
