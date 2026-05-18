from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0008_versamento_note'),
    ]

    operations = [
        migrations.CreateModel(
            name='AcquisitionDraft',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(default='telegram', max_length=30, verbose_name='Origine')),
                ('operator', models.CharField(blank=True, max_length=100, verbose_name='Operatore')),
                ('telegram_chat_id', models.CharField(blank=True, max_length=64, verbose_name='Chat Telegram')),
                ('totale_scassettato', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Totale Scassettato')),
                ('status', models.CharField(choices=[('pending', 'Da verificare'), ('completed', 'Registrata'), ('cancelled', 'Annullata')], default='pending', max_length=20, verbose_name='Stato')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Bozza Acquisizione',
                'verbose_name_plural': 'Bozze Acquisizione',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AcquisitionDraftImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='drafts/%Y/%m/', verbose_name='Foto')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('draft', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='reconciliation.acquisitiondraft')),
            ],
            options={
                'verbose_name': 'Foto Bozza',
                'verbose_name_plural': 'Foto Bozza',
            },
        ),
    ]
