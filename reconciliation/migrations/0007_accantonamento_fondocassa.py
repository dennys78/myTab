from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0006_versamento'),
    ]

    operations = [
        migrations.AddField(
            model_name='versamento',
            name='accantonamento',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Accantonamento Fondo Cassa'),
        ),
        migrations.CreateModel(
            name='FondoCassaMovimento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='Data')),
                ('importo', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Importo')),
                ('descrizione', models.CharField(blank=True, max_length=200, verbose_name='Descrizione')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('versamento', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='fondo_movimenti',
                    to='reconciliation.versamento',
                    verbose_name='Versamento di origine',
                )),
            ],
            options={
                'verbose_name': 'Movimento Fondo Cassa',
                'verbose_name_plural': 'Movimenti Fondo Cassa',
                'ordering': ['-date', '-created_at'],
            },
        ),
    ]
