from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('reconciliation', '0028_acquisitiondraft_extract_job'),
    ]

    operations = [
        migrations.AddField(
            model_name='cashclosure',
            name='tabauno_verifiche',
            field=models.JSONField(blank=True, null=True, verbose_name='Verifiche TabaUno'),
        ),
        migrations.CreateModel(
            name='TabaUnoAgent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token_hash', models.CharField(blank=True, default='', max_length=64)),
                ('last_seen', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='tabauno_agent', to='reconciliation.company')),
            ],
            options={
                'verbose_name': 'Agente TabaUno',
                'verbose_name_plural': 'Agenti TabaUno',
            },
        ),
        migrations.CreateModel(
            name='TabaUnoRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('gratta', models.CharField(default='B', max_length=1)),
                ('status', models.CharField(choices=[('pending', 'In coda'), ('processing', 'In lettura'), ('done', 'Pronta'), ('error', 'Errore'), ('expired', 'Scaduta')], default='pending', max_length=16)),
                ('payload', models.JSONField(blank=True, null=True)),
                ('error', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('picked_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tabauno_requests', to='reconciliation.company')),
                ('requested_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tabauno_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Richiesta TabaUno',
                'verbose_name_plural': 'Richieste TabaUno',
                'ordering': ['created_at', 'id'],
            },
        ),
    ]
