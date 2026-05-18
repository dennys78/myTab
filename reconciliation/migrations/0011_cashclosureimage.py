from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0010_cashclosure_submitted_by'),
    ]

    operations = [
        migrations.CreateModel(
            name='CashClosureImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='closures/%Y/%m/', verbose_name='Foto Incasso')),
                ('source', models.CharField(blank=True, max_length=30, verbose_name='Origine')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('closure', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='reconciliation.cashclosure', verbose_name='Chiusura Cassa')),
            ],
            options={
                'verbose_name': 'Foto Incasso',
                'verbose_name_plural': 'Foto Incasso',
                'ordering': ['created_at'],
            },
        ),
    ]
