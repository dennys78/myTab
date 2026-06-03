from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0024_ricevuta_numero_progressivo'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='receive_notifications',
            field=models.BooleanField(default=True, verbose_name='Ricevi notifiche push e Telegram'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='telegram_chat_id',
            field=models.CharField(blank=True, max_length=64, verbose_name='Chat Telegram collegata'),
        ),
    ]
