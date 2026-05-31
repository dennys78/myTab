from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('reconciliation', '0020_acquisitiondraft_extracted_payload'),
    ]

    operations = [
        migrations.AddField(
            model_name='acquisitiondraft',
            name='telegram_reminder_sent_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Promemoria Telegram il'),
        ),
        migrations.AddField(
            model_name='acquisitiondraft',
            name='viewed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Vista in app il'),
        ),
        migrations.CreateModel(
            name='PushSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint', models.TextField()),
                ('p256dh', models.CharField(max_length=255)),
                ('auth', models.CharField(max_length=64)),
                ('user_agent', models.CharField(blank=True, default='', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='push_subscriptions', to='reconciliation.company')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='push_subscriptions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Sottoscrizione Push',
                'verbose_name_plural': 'Sottoscrizioni Push',
                'unique_together': {('user', 'endpoint')},
            },
        ),
    ]
